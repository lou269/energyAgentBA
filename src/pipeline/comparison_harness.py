
from collections.abc import Mapping
from dataclasses import dataclass
import logging
from pathlib import Path
from typing import cast

import numpy as np
import pandas as pd

from src.context.calendar_context import build_calendar_context
from src.context.calendar_schema import CalendarContext
from src.llm.client import LLMClient, OllamaClient
from src.llm.inference import LLMInferenceError
from src.pipeline.daily_cycle import CycleConfig, CycleResult, CycleState, run_cycle
from src.pipeline.io import df_to_csv

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ScenarioData:
    target_series: pd.Series
    coldstart_hours: int
    decision_times: tuple[pd.Timestamp, ...]
    calendar_events: tuple[Mapping[str, object], ...]
    calendar_source_available: bool
    calendar_source: str


def build_scenario_from_split_manifest(
    treated_hourly: pd.DataFrame,
    split_manifest: pd.DataFrame,
    target_column: str,
) -> ScenarioData:
    # train bleibt die feste Coldstart-Historie (wie bisher bei forecast_runner.py's fixed_history), 
    # eigentlicher Zyklus läuft über validation+test - täglich
    hourly_splits = split_manifest.loc[split_manifest["frequency"].eq("hourly")].set_index("split")

    coldstart_hours = int(cast(int, hourly_splits.loc["train", "row_count"]))
    cycle_start = cast(pd.Timestamp, hourly_splits.loc["validation", "start"])
    cycle_end = cast(pd.Timestamp, hourly_splits.loc["test", "end"])

    target_series = treated_hourly.loc[:cycle_end, target_column]
    # state.history endet bereits bei cycle_start - 1h (Train-Ende) - der erste decision_time muss min 1h danach liegen, 
    # sonst ist new_observations in run_comparison leer
    decision_times = tuple(pd.date_range(start=cycle_start + pd.Timedelta(hours=1), end=cycle_end, freq="24h"))

    return ScenarioData(
        target_series=target_series,
        coldstart_hours=coldstart_hours,
        decision_times=decision_times,
        calendar_events=(),
        calendar_source_available=False,
        calendar_source="none",
    )


def run_comparison(
    scenario: ScenarioData,
    configs: Mapping[str, CycleConfig],
    output_dir: Path,
    *,
    llm_prompt: str | None = None,
    llm_client: LLMClient | None = None,
    max_consecutive_llm_failures: int = 5,
    max_total_llm_failures: int = 15,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []

    for config_label, config in configs.items():
        state = CycleState(
            history=scenario.target_series.iloc[: scenario.coldstart_hours],
            prophet_model=None,
            model_history=None,
            model_fitted_at=None,
            reference_window_end=None,
        )
        consecutive_llm_failures = 0
        total_llm_failures = 0

        # llm_client kann von außen injiziert werden (z.B. für Tests), sonst baut sich jede  "real"-Config  eigenen OllamaClient und
        # schließt ihn auch wieder selbst
        owns_llm_client = llm_client is None and config.llm_mode == "real" and config.llm_config is not None
        active_llm_client: LLMClient | None = (
            OllamaClient(timeout_seconds=config.llm_config.request_timeout_seconds)
            if owns_llm_client and config.llm_config is not None
            else llm_client
        )

        try:
            for decision_time in scenario.decision_times:
                new_observations = scenario.target_series.loc[
                    state.history.index[-1] + pd.Timedelta(hours=1) : decision_time - pd.Timedelta(hours=1)
                ]

                calendar_context = (
                    _build_calendar_context(scenario, decision_time)
                    if config.llm_mode != "off"
                    else None
                )

                try:
                    result, state = run_cycle(
                        state,
                        new_observations,
                        decision_time,
                        config,
                        llm_client=active_llm_client,
                        llm_prompt=llm_prompt,
                        calendar_context=calendar_context,
                    )
                except LLMInferenceError as error:
                    # Ollama liefert gelegentlich ungültige/inkonsistente Ausgaben -> ein einzelner
                    # Fehlschlag soll nicht den ganzen Vergleichslauf (andere Configs/Tage) kosten
                    # state bleibt unverändert, die übersprungenen Stunden landen beim nächsten
                    # Zyklus mit in new_observations
                    consecutive_llm_failures += 1
                    total_llm_failures += 1
                    logger.warning(
                        "LLM inference failed for %s at %s (%d consecutive, %d total): %s",
                        config_label, decision_time, consecutive_llm_failures, total_llm_failures, error,
                    )
                    for attempt in error.attempts:
                        dump_path = _dump_failed_attempt(
                            output_dir, config_label, decision_time, attempt.attempt_number, attempt.raw_content,
                        )
                        logger.warning(
                            "  attempt %d: %s | full response dumped to %s",
                            attempt.attempt_number, attempt.validation_error, dump_path,
                        )

                    rows.append(
                        {
                            "decision_time": decision_time,
                            "config": config_label,
                            "classification": None,
                            "explanation": "",
                            "adaption_action": "none",
                            "adaption_reason": "",
                            "retrained": False,
                            "reference_reset": False,
                            "mae_w": float("nan"),
                            "error": str(error),
                        }
                    )

                  
                    if consecutive_llm_failures >= max_consecutive_llm_failures:
                        logger.error(
                            "Aborting %s after %d consecutive LLM failures at %s - remaining decision times skipped.",
                            config_label, consecutive_llm_failures, decision_time,
                        )
                        break

                    if total_llm_failures >= max_total_llm_failures:
                        logger.error(
                            "Aborting %s after %d total LLM failures (not necessarily consecutive) at %s - remaining decision times skipped.",
                            config_label, total_llm_failures, decision_time,
                        )
                        break

                    continue
                else:
                    consecutive_llm_failures = 0

                actual = scenario.target_series.reindex(result.forecast["target_timestamp"]).to_numpy()
                predicted = result.forecast["y_pred"].to_numpy()
                mae_w = float(np.nanmean(np.abs(actual - predicted)))

                rows.append(
                    {
                        "decision_time": decision_time,
                        "config": config_label,
                        "classification": result.classification,
                        "explanation": _explanation(result),
                        "adaption_action": result.adaption_action.kind if result.adaption_action else "none",
                        "adaption_reason": result.adaption_action.reason if result.adaption_action else "",
                        "retrained": result.retrained,
                        "reference_reset": result.reference_reset,
                        "mae_w": mae_w,
                        "error": "",
                    }
                )
        finally:
            if owns_llm_client and active_llm_client is not None:
                active_llm_client.close()

    comparison = pd.DataFrame(rows)
    df_to_csv(comparison, output_dir, "comparison_summary")
    return comparison


def _explanation(result: CycleResult) -> str:
    if result.llm_output is not None:
        return result.llm_output["explanation"]

    if result.rule_output is not None:
        return result.rule_output.reasoning

    return ""


def _dump_failed_attempt(
    output_dir: Path,
    config_label: str,
    decision_time: pd.Timestamp,
    attempt_number: int,
    raw_content: str,
) -> Path:
    dump_dir = output_dir / "llm_failures"
    dump_dir.mkdir(parents=True, exist_ok=True)

    timestamp_slug = decision_time.strftime("%Y%m%dT%H%M%S")
    dump_path = dump_dir / f"{config_label}_{timestamp_slug}_attempt{attempt_number}.txt"
    dump_path.write_text(raw_content, encoding="utf-8")

    return dump_path


def _build_calendar_context(
    scenario: ScenarioData, 
    decision_time: pd.Timestamp
) -> CalendarContext:
    return build_calendar_context(
        list(scenario.calendar_events),
        source_available=scenario.calendar_source_available,
        source=scenario.calendar_source,
        retrieved_at=decision_time,
        decision_time=decision_time,
        window_start=decision_time - pd.Timedelta(hours=24),
        window_end=decision_time + pd.Timedelta(hours=24),
    )