import json
import logging
from collections.abc import Mapping
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd

from experiments.common.standard_config import LOCAL_TIMEZONE, PROJECT_CONFIG
from src.config.config_forecasting import (
    ComparisonConfig,
    CycleConfig,
    ForecastingConfig,
    ProphetVariantConfig,
)
from src.forecasting.forecasting import run_forecast_comparison
from src.llm.llm_run_artifacts import load_prompt
from src.llm.llm_runner import PROMPT_DIRECTORY
from src.common.timestamps import analyzed_day_text
from src.pipeline.comparison_harness import ScenarioData, run_comparison
from src.pipeline.io import read_jsonl

COMPARISON_CONFIG = ComparisonConfig()
# so benennt run_comparison seine Ausgaben
COMPARISON_SUMMARY_FILE = "comparison_summary.csv"
ANOMALY_FILE = "anomaly.csv"
LLM_OUTPUTS_FILE = "llm_outputs.jsonl"
STRUCTURED_STATES_FILE = "structured_states.jsonl"
FORECASTS_FILE = "forecasts.csv"
RUN_META_FILE = "run_meta.json"


def read_llm_prompt(prompt_version: str) -> str:
    return load_prompt(PROMPT_DIRECTORY / f"prompt_{prompt_version}.txt")


def run_scenario(
    scenario: ScenarioData,
    configs: Mapping[str, CycleConfig],
    output_directory: Path,
    *,
    run_id: str,
    llm_prompt: str | None = None,
    calendar_tool_prompt: str | None = None,
) -> pd.DataFrame:
    # sonst eine Logzeile je Zyklus und System, bei K1 wären das gut 5.000
    logging.getLogger("src.pipeline.comparison_harness").setLevel(logging.WARNING)

    return run_comparison(
        scenario,
        configs,
        output_directory,
        PROJECT_CONFIG.project_root,
        local_timezone=LOCAL_TIMEZONE,
        run_id=run_id,
        llm_prompt=llm_prompt,
        calendar_tool_prompt=calendar_tool_prompt,
        max_consecutive_llm_failures=COMPARISON_CONFIG.max_consecutive_llm_failures,
        max_total_llm_failures=COMPARISON_CONFIG.max_total_llm_failures,
        calendar_lookback_days=COMPARISON_CONFIG.calendar_lookback_days,
        calendar_lookahead_days=COMPARISON_CONFIG.calendar_lookahead_days,
    )


def run_scenario_in_scratch(
    scenario: ScenarioData,
    configs: Mapping[str, CycleConfig],
    *,
    run_id: str,
    llm_prompt: str | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    with TemporaryDirectory() as scratch:
        run_scenario(
            scenario, configs, Path(scratch), run_id=run_id, llm_prompt=llm_prompt
        )

        summary = pd.read_csv(Path(scratch) / COMPARISON_SUMMARY_FILE)
        anomaly = read_anomaly_rows(Path(scratch))

    return summary, anomaly


def read_anomaly_rows(output_directory: Path) -> pd.DataFrame:
    # run_comparison legt je Config einen Unterordner mit eigener anomaly.csv an
    return pd.concat(
        [
            pd.read_csv(file)
            for file in sorted(output_directory.glob(f"*/{ANOMALY_FILE}"))
        ],
        ignore_index=True,
    )


def read_calendar_availability(output_directory: Path) -> pd.DataFrame:
    # je eingeordnetem Tag, ob ein Kalender im State stand
    # -> mit Kalender-Tool steht er dort nur, wenn das LLM ihn abgerufen hat
    rows = [
        {
            "config": record["config"],
            "analyzed_day": analyzed_day_text(
                pd.Timestamp(record["decision_time"]), LOCAL_TIMEZONE
            ),
            "calendar_available": record["context"]["source_available"],
        }
        for state_file in sorted(output_directory.glob(f"*/{STRUCTURED_STATES_FILE}"))
        for record in read_jsonl(state_file)
    ]

    return pd.DataFrame(rows, columns=["config", "analyzed_day", "calendar_available"])


def _scenario_of(file: Path, raw_directory: Path) -> str:
    # Ordner über dem System (ctx0 in E2, Szenario in E3)
    return file.parent.parent.relative_to(raw_directory).as_posix()


def read_llm_outputs(raw_directory: Path) -> pd.DataFrame:
    # alle LLM-Antworten eines Laufs, analyzed_day lokal wie in der Auswertung
    rows = []
    for output_file in sorted(raw_directory.rglob(LLM_OUTPUTS_FILE)):
        scenario = _scenario_of(output_file, raw_directory)
        for record in read_jsonl(output_file):
            rows.append(
                {
                    "scenario": scenario,
                    "config": record["config"],
                    "decision_time": record["decision_time"],
                    "analyzed_day": analyzed_day_text(
                        pd.Timestamp(record["decision_time"]), LOCAL_TIMEZONE
                    ),
                    "classification": record["classification"],
                    "explanation": record["explanation"],
                    "user_recommendation": record["user_recommendation"],
                    "uncertainty": record["uncertainty"],
                    "evidence_paths": ";".join(
                        reference["path"] for reference in record["evidence_references"]
                    ),
                }
            )

    return pd.DataFrame(
        rows,
        columns=[
            "scenario",
            "config",
            "decision_time",
            "analyzed_day",
            "classification",
            "explanation",
            "user_recommendation",
            "uncertainty",
            "evidence_paths",
        ],
    )


def read_structured_states(raw_directory: Path) -> pd.DataFrame:
    # alle States eines Laufs, scenario und config wie in read_llm_outputs
    rows = []
    for state_file in sorted(raw_directory.rglob(STRUCTURED_STATES_FILE)):
        scenario = _scenario_of(state_file, raw_directory)
        for record in read_jsonl(state_file):
            rows.append(
                {
                    "scenario": scenario,
                    "config": record.pop("config"),
                    "decision_time": record["decision_time"],
                    "state": record,
                }
            )

    return pd.DataFrame(rows, columns=["scenario", "config", "decision_time", "state"])


def read_run_meta(raw_directory: Path) -> pd.DataFrame:
    # je Szenario-Ordner und System die Laufzeit, scenario wie in read_llm_outputs
    rows = []
    for meta_file in sorted(raw_directory.rglob(RUN_META_FILE)):
        meta = json.loads(meta_file.read_text(encoding="utf-8"))
        rows.append(
            {
                "scenario": _scenario_of(meta_file, raw_directory),
                "config": meta["config"],
                "runtime_seconds": meta["runtime_seconds"],
                "interrupted": meta["interrupted"],
            }
        )

    return pd.DataFrame(
        rows, columns=["scenario", "config", "runtime_seconds", "interrupted"]
    )


def run_forecast_models(
    candidates: tuple[str | ProphetVariantConfig, ...],
    history: pd.Series,
    targets: pd.Series,
    targets_imputed: pd.Series,
    forecast_config: ForecastingConfig,
    *,
    run_id: str,
    experiment_id: str,
    split: str,
    comparison_model_ids: tuple[str, ...],
    reference_model_ids: tuple[str, ...],
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    return run_forecast_comparison(
        candidates,
        history,
        targets,
        targets_imputed,
        run_id=run_id,
        experiment_id=experiment_id,
        split=split,
        horizon_days=forecast_config.horizon_days,
        forecast_origin_step_days=forecast_config.forecast_origin_step_days,
        frequency=forecast_config.frequency,
        local_timezone=LOCAL_TIMEZONE,
        clip_negative_forecasts=forecast_config.clip_negative_forecasts,
        config_version=forecast_config.config_version,
        growth=forecast_config.growth,
        daily_seasonality=forecast_config.daily_seasonality,
        country_holidays=forecast_config.country_holidays,
        log_transform=forecast_config.log_transform,
        interval_width=forecast_config.interval_width,
        uncertainty_samples=forecast_config.uncertainty_samples,
        comparison_model_ids=comparison_model_ids,
        reference_model_ids=reference_model_ids,
        nominal_interval_level=forecast_config.interval_width,
        mape_min_eligible_watts=forecast_config.mape_min_eligible_watts,
    )
