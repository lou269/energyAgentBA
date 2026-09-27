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
from src.pipeline.comparison_harness import ScenarioData, run_comparison

COMPARISON_CONFIG = ComparisonConfig()
# so benennt run_comparison seine Ausgaben
COMPARISON_SUMMARY_FILE = "comparison_summary.csv"
ANOMALY_FILE = "anomaly.csv"
LLM_OUTPUTS_FILE = "llm_outputs.jsonl"


def read_llm_prompt(prompt_version: str) -> str:
    return load_prompt(PROMPT_DIRECTORY / f"prompt_{prompt_version}.txt")


def run_scenario(
    scenario: ScenarioData,
    configs: Mapping[str, CycleConfig],
    output_directory: Path,
    *,
    run_id: str,
    llm_prompt: str | None = None,
) -> pd.DataFrame:
    # sonst eine Logzeile je Zyklus und System, bei K2 wären das gut 5.000
    logging.getLogger("src.pipeline.comparison_harness").setLevel(logging.WARNING)

    return run_comparison(
        scenario,
        configs,
        output_directory,
        PROJECT_CONFIG.project_root,
        local_timezone=LOCAL_TIMEZONE,
        run_id=run_id,
        llm_prompt=llm_prompt,
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
) -> tuple[pd.DataFrame, pd.DataFrame]:
    # run_comparison schreibt Forecasts, States und Manifeste mit, K2 und K4 brauchen davon nur Summary und Anomalie-Zeilen
    with TemporaryDirectory() as scratch:
        run_scenario(scenario, configs, Path(scratch), run_id=run_id)

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


def read_llm_outputs(raw_directory: Path) -> pd.DataFrame:
    # alle LLM-Antworten eines Laufs, scenario ist der Ordner über dem System (ctx0 in E2, Szenario in E5)
    rows = []
    for output_file in sorted(raw_directory.rglob(LLM_OUTPUTS_FILE)):
        scenario = output_file.parent.parent.relative_to(raw_directory).as_posix()
        for line in output_file.read_text(encoding="utf-8").splitlines():
            record = json.loads(line)
            rows.append(
                {
                    "scenario": scenario,
                    "config": record["config"],
                    "decision_time": record["decision_time"],
                    "classification": record["classification"],
                    "explanation": record["explanation"],
                }
            )

    return pd.DataFrame(
        rows,
        columns=[
            "scenario",
            "config",
            "decision_time",
            "classification",
            "explanation",
        ],
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
        clip_negative_forecasts=forecast_config.negative_forecast_handling
        == "clip_zero",
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
