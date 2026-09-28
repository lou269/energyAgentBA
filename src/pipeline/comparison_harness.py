from collections.abc import Mapping
from dataclasses import asdict, dataclass
from functools import partial
import logging
from pathlib import Path
from time import perf_counter
from typing import cast

import numpy as np
import pandas as pd

from src.common.timestamps import analyzed_day, local_calendar_range, shift_local_days
from src.context.calendar_context import build_calendar_context
from src.context.calendar_schema import CalendarContext
from src.forecasting.evaluation import score_cycle_forecast
from src.llm.client import LLMClient, OllamaClient
from src.llm.inference import LLMAttemptRecord
from src.pipeline.cycle_run_manifest import build_cycle_run_manifest
from src.config.config_forecasting import CycleConfig
from src.pipeline.daily_cycle import CycleResult, CycleState, run_cycle
from src.pipeline.io import (
    append_csv,
    append_jsonl,
    df_to_csv,
    find_run_directory,
    hourly_split_bounds,
    save_json,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ScenarioData:
    target_series: pd.Series
    coldstart_days: int
    decision_times: tuple[pd.Timestamp, ...]
    calendar_events: tuple[Mapping[str, object], ...]
    calendar_source_available: bool
    calendar_source: str
    # optional, da ältere Aufrufer (Tests, experiments/) das Feld nicht kennen - ohne Maske wird mae_w wie
    # bisher berechnet, mit Maske werden ffill-imputierte Zielstunden ausgeschlossen (siehe evaluation.py's
    # target_eligible, dieselbe Regel)
    target_imputed: pd.Series | None = None
    # optional: rohe Plausibilitäts-Flags (plausibility_check.py), fehlt es, bleibt value_implausibl wie bisher nur über NaN in today_mean bestimmt
    value_implausible: pd.Series | None = None


def build_scenario_from_split_manifest(
    treated_hourly: pd.DataFrame,
    split_manifest: pd.DataFrame,
    target_column: str,
    *,
    coldstart_days: int,
    local_timezone: str,
    target_imputed: pd.Series | None = None,
    value_implausible: pd.Series | None = None,
) -> ScenarioData:
    _test_start, cycle_end = hourly_split_bounds(split_manifest, "test")

    target_series = treated_hourly.loc[:cycle_end, target_column]

    cycle_start = shift_local_days(
        target_series.index[0], coldstart_days, local_timezone
    )

    # erster Entscheidungstag direkt nach den coldstart_days, deren letzter Tag kommt im ersten Zyklus als new_observations (coldstart_history)
    decision_times = tuple(
        local_calendar_range(cycle_start, 1, cycle_end, local_timezone)
    )

    return ScenarioData(
        target_series=target_series,
        coldstart_days=coldstart_days,
        decision_times=decision_times,
        calendar_events=(),
        calendar_source_available=False,
        calendar_source="none",
        target_imputed=target_imputed.loc[:cycle_end]
        if target_imputed is not None
        else None,
        value_implausible=value_implausible.loc[:cycle_end]
        if value_implausible is not None
        else None,
    )


FORECAST_COLUMNS = ["target_timestamp", "model_id", "y_pred", "y_lower", "y_upper"]


def run_comparison(
    scenario: ScenarioData,
    configs: Mapping[str, CycleConfig],
    run_directory: Path,
    project_root: Path,
    *,
    local_timezone: str,
    run_id: str | None = None,
    llm_prompt: str | None = None,
    llm_client: LLMClient | None = None,
    max_consecutive_llm_failures: int,
    max_total_llm_failures: int,
    calendar_lookback_days: int,
    calendar_lookahead_days: int,
) -> pd.DataFrame:
    run_started = perf_counter()
    run_id = run_id or run_directory.name
    run_directory.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, object]] = []
    forecast_frames: list[pd.DataFrame] = []
    llm_output_records: list[dict[str, object]] = []

    for config_label, config in configs.items():
        config_directory = run_directory / config_label
        config_directory.mkdir(parents=True, exist_ok=True)

        np.random.seed(config.forecasting_config.seed)

        state = CycleState(
            history=coldstart_history(
                scenario.target_series, scenario.decision_times[0], local_timezone
            ),
            prophet_model=None,
            model_history=None,
            model_fitted_at=None,
        )
        consecutive_llm_failures = 0
        total_llm_failures = 0

        # llm_client kann von außen injiziert werden (z.B. für Tests), sonst baut sich jede  "real"-Config  eigenen OllamaClient und
        # schließt ihn auch wieder selbst
        owns_llm_client = (
            llm_client is None
            and config.llm_mode == "real"
            and config.llm_config is not None
        )
        active_llm_client: LLMClient | None = (
            OllamaClient(timeout_seconds=config.llm_config.request_timeout_seconds)
            if owns_llm_client and config.llm_config is not None
            else llm_client
        )

        config_started = perf_counter()
        days_completed = 0
        retrain_count = 0
        adaption_count = 0
        interrupted = False

        logger.info(
            "=== %s (llm_mode=%s) — %d Zyklustage geplant ===",
            config_label,
            config.llm_mode,
            len(scenario.decision_times),
        )

        try:
            try:
                for decision_time in scenario.decision_times:
                    analyzed_date = analyzed_day(decision_time, local_timezone).date()
                    new_observations = observations_since(
                        scenario.target_series, state.history, decision_time
                    )

                    new_value_implausible = (
                        scenario.value_implausible.loc[
                            new_observations.index[0] : new_observations.index[-1]
                        ]
                        if scenario.value_implausible is not None
                        else None
                    )

                    calendar_lookup = (
                        partial(
                            _build_calendar_context,
                            scenario,
                            decision_time,
                            calendar_tool=False,
                            lookback_days=calendar_lookback_days,
                            lookahead_days=calendar_lookahead_days,
                            local_timezone=local_timezone,
                        )
                        if config.llm_config is not None
                        and config.llm_config.calendar_tool
                        else None
                    )
                    calendar_context = (
                        _build_calendar_context(
                            scenario,
                            decision_time,
                            calendar_tool=calendar_lookup is not None,
                            lookback_days=calendar_lookback_days,
                            lookahead_days=calendar_lookahead_days,
                            local_timezone=local_timezone,
                        )
                        if config.llm_mode != "off"
                        else None
                    )

                    result, state = run_cycle(
                        state,
                        new_observations,
                        decision_time,
                        config,
                        local_timezone=local_timezone,
                        llm_client=active_llm_client,
                        llm_prompt=llm_prompt,
                        calendar_context=calendar_context,
                        calendar_lookup=calendar_lookup,
                        new_value_implausible=new_value_implausible,
                    )

                    if result.llm_error is None:
                        consecutive_llm_failures = 0
                    else:
                        # Ollama liefert ungültige Ausgaben run_cycle lässt den Tag dann ohne Einordnung weiterlaufen, Prognose und MAE gibt es trotzdem
                        consecutive_llm_failures += 1
                        total_llm_failures += 1
                        logger.warning(
                            "LLM inference failed for %s at %s (%d consecutive, %d total): %s",
                            config_label,
                            decision_time,
                            consecutive_llm_failures,
                            total_llm_failures,
                            result.llm_error,
                        )
                        for attempt in result.llm_error.attempts:
                            _append_failed_attempt(
                                run_directory,
                                config_directory,
                                config_label,
                                decision_time,
                                attempt,
                            )
                            logger.warning(
                                "  attempt %d: %s",
                                attempt.attempt_number,
                                attempt.validation_error,
                            )

                    mae_w, mape_pct = score_cycle_forecast(
                        result.forecast,
                        scenario.target_series,
                        scenario.target_imputed,
                        config.forecasting_config.mape_min_eligible_watts,
                    )

                    forecast_slice = result.forecast[FORECAST_COLUMNS].copy()
                    forecast_slice.insert(0, "config", config_label)
                    forecast_slice.insert(1, "decision_time", decision_time)
                    forecast_slice.insert(
                        2,
                        "forecast_day",
                        decision_time.tz_convert(local_timezone).date(),
                    )
                    forecast_frames.append(forecast_slice)
                    append_csv(forecast_slice, config_directory / "forecasts.csv")

                    if result.analysis_row is not None:
                        anomaly_row = result.analysis_row.to_frame().T
                        anomaly_row.insert(0, "config", config_label)
                        anomaly_row.insert(1, "decision_time", decision_time)
                        anomaly_row.insert(2, "analyzed_day", analyzed_date)
                        append_csv(anomaly_row, config_directory / "anomaly.csv")

                    if result.structured_state is not None and (
                        result.llm_output is not None or result.rule_output is not None
                    ):
                        structured_state_record = {
                            "config": config_label,
                            **cast(dict, result.structured_state),
                        }
                        append_jsonl(
                            structured_state_record,
                            config_directory / "structured_states.jsonl",
                        )

                    if result.llm_output is not None:
                        llm_output_record = {
                            "config": config_label,
                            "decision_time": decision_time.isoformat(),
                            **result.llm_output,
                        }
                        llm_output_records.append(llm_output_record)
                        append_jsonl(
                            llm_output_record, config_directory / "llm_outputs.jsonl"
                        )

                    if result.calendar_tool_response is not None:
                        append_jsonl(
                            {
                                "config": config_label,
                                "decision_time": decision_time.isoformat(),
                                **result.calendar_tool_response,
                            },
                            config_directory / "calendar_tool_calls.jsonl",
                        )

                    if result.rule_output is not None:
                        rule_output_record = {
                            "config": config_label,
                            "decision_time": decision_time.isoformat(),
                            **asdict(result.rule_output),
                        }
                        append_jsonl(
                            rule_output_record, config_directory / "rule_outputs.jsonl"
                        )

                    summary_row = {
                        "decision_time": decision_time,
                        "analyzed_day": analyzed_date,
                        "config": config_label,
                        "classification": result.classification,
                        "explanation": _explanation(result),
                        "adaption_action": result.adaption_action.kind
                        if result.adaption_action
                        else "none",
                        "adaption_reason": result.adaption_action.reason
                        if result.adaption_action
                        else "",
                        "retrained": result.retrained,
                        "reference_reset": result.reference_reset,
                        "mae_w": mae_w,
                        "mape_pct": mape_pct,
                        "error": str(result.llm_error)
                        if result.llm_error is not None
                        else "",
                    }
                    rows.append(summary_row)
                    append_csv(
                        pd.DataFrame([summary_row]), config_directory / "summary.csv"
                    )

                    days_completed += 1
                    retrain_count += int(result.retrained)
                    adaption_count += int(
                        result.adaption_action is not None
                        and result.adaption_action.kind != "none"
                    )

                    logger.info(
                        "%s %d/%d (%s): classification=%s adaption=%s retrained=%s",
                        config_label,
                        days_completed,
                        len(scenario.decision_times),
                        analyzed_date,
                        result.classification,
                        summary_row["adaption_action"],
                        result.retrained,
                    )

                    if consecutive_llm_failures >= max_consecutive_llm_failures:
                        logger.error(
                            "Aborting %s after %d consecutive LLM failures at %s - remaining decision times skipped.",
                            config_label,
                            consecutive_llm_failures,
                            decision_time,
                        )
                        break

                    if total_llm_failures >= max_total_llm_failures:
                        logger.error(
                            "Aborting %s after %d total LLM failures (not necessarily consecutive) at %s - remaining decision times skipped.",
                            config_label,
                            total_llm_failures,
                            decision_time,
                        )
                        break
            except KeyboardInterrupt:
                interrupted = True
                logger.warning(
                    "%s terminated by user at %d/%d days. Results are safed at %s",
                    config_label,
                    days_completed,
                    len(scenario.decision_times),
                    config_directory,
                )
                raise
        finally:
            if owns_llm_client and active_llm_client is not None:
                if config.llm_config is not None:
                    try:
                        active_llm_client.unload_model(config.llm_config.model)
                    except Exception as error:
                        logger.warning(
                            "Could not unload %s (%s) from Ollama: %s",
                            config_label,
                            config.llm_config.model,
                            error,
                        )

                active_llm_client.close()

            save_json(
                {
                    "config": config_label,
                    "llm_mode": config.llm_mode,
                    "decision_time_planned": len(scenario.decision_times),
                    "days_completed": days_completed,
                    "retrain_count": retrain_count,
                    "adaption_count": adaption_count,
                    "consecutive_llm_failures": consecutive_llm_failures,
                    "total_llm_failures": total_llm_failures,
                    "interrupted": interrupted,
                    "runtime_seconds": perf_counter() - config_started,
                },
                config_directory / "run_meta.json",
            )

    comparison = pd.DataFrame(rows)
    df_to_csv(comparison, run_directory, "comparison_summary")

    output_paths = {"comparison_summary": run_directory / "comparison_summary.csv"}

    # aggregiert die pro Tag schon berechneten mae_w/mape_pct je Config, Tage mit LLM-Fehlschlag haben auch eine Prognose
    if not comparison.empty:
        evaluation_summary = comparison.groupby("config", as_index=False).agg(
            evaluated_days=("mae_w", "count"),
            mae_w=("mae_w", "mean"),
            mape_pct=("mape_pct", "mean"),
        )
        df_to_csv(evaluation_summary, run_directory, "evaluation_summary")
        output_paths["evaluation_summary"] = run_directory / "evaluation_summary.csv"

    if forecast_frames:
        forecasts = pd.concat(forecast_frames, ignore_index=True)
        df_to_csv(forecasts, run_directory, "forecasts")
        output_paths["forecasts"] = run_directory / "forecasts.csv"

    if llm_output_records:
        llm_outputs_file = run_directory / "llm_outputs.json"
        save_json({"llm_outputs": llm_output_records}, llm_outputs_file)
        output_paths["llm_outputs"] = llm_outputs_file

    llm_failures_file = run_directory / "llm_failures.jsonl"
    decision_times = scenario.decision_times

    manifest = build_cycle_run_manifest(
        project_root=project_root,
        run_id=run_id,
        config_values={label: asdict(config) for label, config in configs.items()},
        coldstart_days=scenario.coldstart_days,
        decision_time_count=len(decision_times),
        decision_time_start=decision_times[0].isoformat() if decision_times else None,
        decision_time_end=decision_times[-1].isoformat() if decision_times else None,
        row_count=len(comparison),
        llm_failure_count=int((comparison["error"] != "").sum())
        if not comparison.empty
        else 0,
        llm_failures_file=llm_failures_file if llm_failures_file.is_file() else None,
        output_paths=output_paths,
        runtime_seconds=perf_counter() - run_started,
    )
    save_json(manifest, run_directory / "run_manifest.json")

    logger.info("Cycle comparison saved to %s.", run_directory)

    return comparison


def create_cycle_run_id(output_dir: Path, configs: Mapping[str, CycleConfig]) -> str:
    latest_run = find_run_directory(output_dir, prefix="cycle")
    number = (latest_run[0] if latest_run is not None else 0) + 1
    return f"cycle_{number:03d}_{'-'.join(configs)}"


def _explanation(result: CycleResult) -> str:
    if result.llm_output is not None:
        return result.llm_output["explanation"]

    if result.rule_output is not None:
        return result.rule_output.reasoning

    return ""


def _append_failed_attempt(
    run_directory: Path,
    config_directory: Path,
    config_label: str,
    decision_time: pd.Timestamp,
    attempt: LLMAttemptRecord,
) -> None:
    record = {
        "config": config_label,
        "decision_time": decision_time.isoformat(),
        "attempt_number": attempt.attempt_number,
        "validation_error": attempt.validation_error,
        "generation_seconds": attempt.generation_seconds,
        "raw_content": attempt.raw_content,
    }
    append_jsonl(record, config_directory / "llm_failures.jsonl")
    append_jsonl(record, run_directory / "llm_failures.jsonl")


def _build_calendar_context(
    scenario: ScenarioData,
    decision_time: pd.Timestamp,
    *,
    calendar_tool: bool,
    lookback_days: int,
    lookahead_days: int,
    local_timezone: str,
) -> CalendarContext:
    # mit Kalender-Tool steht vor dem Abruf nichts im State, das LLM holt sich die Einträge selbst
    return build_calendar_context(
        [] if calendar_tool else list(scenario.calendar_events),
        source_available=scenario.calendar_source_available and not calendar_tool,
        source="calendar_tool" if calendar_tool else scenario.calendar_source,
        retrieved_at=decision_time,
        decision_time=decision_time,
        window_start=shift_local_days(decision_time, -lookback_days, local_timezone),
        window_end=shift_local_days(decision_time, lookahead_days, local_timezone),
        local_timezone=local_timezone,
    )


def coldstart_history(
    target_series: pd.Series, first_decision_time: pd.Timestamp, local_timezone: str
) -> pd.Series:
    # der erste Zyklus bekommt den vollen Tag vor first_decision_time als new_observations
    history_end = shift_local_days(first_decision_time, -1, local_timezone)
    return target_series.loc[target_series.index < history_end]


def observations_since(
    target_series: pd.Series, history: pd.Series, decision_time: pd.Timestamp
) -> pd.Series:
    return target_series.loc[
        history.index[-1] + pd.Timedelta(hours=1) : decision_time
        - pd.Timedelta(hours=1)
    ]
