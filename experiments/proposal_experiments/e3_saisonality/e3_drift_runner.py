# open -a Ollama
# conda run -n forecasting-env python -m experiments.proposal_experiments.e3_saisonality.e3_drift_runner

# ein Lauf mit SYS3 über einen echten Saisonwechsel, prüft ob long_term-Drift korrekt nicht als new_pattern klassifiziert wird

import logging
from dataclasses import asdict

from experiments.proposal_experiments.e_config import E3Config
from experiments.proposal_experiments.shared import build_decision_times, crop_history_for_coldstart
from src.common.target_series import read_preprocessed_target
from src.common.timestamps import local_midnight_utc
from src.config.project_config import ProjectConfig
from src.llm.llm_run_artifacts import load_prompt
from src.llm.llm_runner import PROMPT_DIRECTORY
from src.pipeline.comparison_harness import ScenarioData, run_comparison
from src.config.config_forecasting import ComparisonConfig, ForecastingConfig, SYS_VARIANTS
from src.pipeline.io import create_experiment_run

logger = logging.getLogger(__name__)


def run() -> None:
    project_config = ProjectConfig()
    e3_config = E3Config()
    comparison_config = ComparisonConfig()
    forecast_config = ForecastingConfig()

    window_start = local_midnight_utc(e3_config.observation_window_start_date, project_config.timezone)
    window_end = local_midnight_utc(e3_config.observation_window_end_date, project_config.timezone)

    target_series, target_imputed, target_value_implausible = read_preprocessed_target(project_config)

    decision_times = build_decision_times(
        window_start, window_end,
        margin_before_days=e3_config.margin_before_days, margin_after_days=e3_config.margin_after_days,
        local_timezone=project_config.timezone,
    )

    target_series = crop_history_for_coldstart(
        target_series, coldstart_days=forecast_config.cycle_coldstart_days, first_decision_time=decision_times[0],
        local_timezone=project_config.timezone,
    )

    scenario = ScenarioData(
        target_series=target_series,
        coldstart_days=forecast_config.cycle_coldstart_days,
        decision_times=decision_times,
        calendar_events=(),
        calendar_source_available=False,
        calendar_source="none",
        target_imputed=target_imputed,
        value_implausible=target_value_implausible,
    )

    sys3_config = SYS_VARIANTS["SYS3"]
    assert sys3_config.llm_config is not None
    llm_prompt = load_prompt(PROMPT_DIRECTORY / f"prompt_{sys3_config.llm_config.prompt_version}.txt")

    run_directory, raw_directory = create_experiment_run(
        project_config.e3_output_dir, "e3_drift", {"e3_config": asdict(e3_config)},
    )

    logger.info("Running E3 Teilfrage 2 (%s..%s) über %d Zyklustage...", window_start, window_end, len(decision_times))
    run_comparison(
        scenario, {"SYS3": sys3_config}, raw_directory, project_config.project_root,
        local_timezone=project_config.timezone,
        run_id=run_directory.name, llm_prompt=llm_prompt,
        max_consecutive_llm_failures=comparison_config.max_consecutive_llm_failures,
        max_total_llm_failures=comparison_config.max_total_llm_failures,
        calendar_lookback_days=comparison_config.calendar_lookback_days,
        calendar_lookahead_days=comparison_config.calendar_lookahead_days,
    )

    logger.info("E3 Teilfrage 2 abgeschlossen, siehe %s.", run_directory)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
