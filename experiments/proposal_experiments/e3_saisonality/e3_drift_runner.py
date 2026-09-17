# open -a Ollama
# conda run -n forecasting-env python -m experiments.proposal_experiments.e3_saisonality.e3_drift_runner

# ein Lauf mit SYS3 über einen echten Saisonwechsel, prüft ob long_term-Drift korrekt nicht als new_pattern klassifiziert wird

import logging
from pathlib import Path

from experiments.proposal_experiments.e_config import E3Config
from experiments.proposal_experiments.shared import build_decision_times, load_target_series
from src.common.timestamps import parse_utc_timestamp
from src.config.project_config import ProjectConfig
from src.llm.llm_run_artifacts import load_prompt
from src.llm.llm_runner import PROMPT_DIRECTORY
from src.pipeline.comparison_harness import ScenarioData, run_comparison
from src.config.config_forecasting import ComparisonConfig, SYS_VARIANTS
from src.pipeline.io import next_sequential_number

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path(__file__).parent / "output"


def run() -> None:
    project_config = ProjectConfig()
    e3_config = E3Config()
    comparison_config = ComparisonConfig()

    window_start = parse_utc_timestamp(e3_config.observation_window_start, "observation_window_start")
    window_end = parse_utc_timestamp(e3_config.observation_window_end, "observation_window_end")

    target_series, target_imputed, _meter_key = load_target_series(project_config)

    decision_times = build_decision_times(
        window_start, window_end,
        margin_before_days=e3_config.margin_before_days, margin_after_days=e3_config.margin_after_days,
    )

    scenario = ScenarioData(
        target_series=target_series,
        coldstart_hours=e3_config.coldstart_hours,
        decision_times=decision_times,
        calendar_events=(),
        calendar_source_available=False,
        calendar_source="none",
        target_imputed=target_imputed,
    )

    sys3_config = SYS_VARIANTS["SYS3"]
    assert sys3_config.llm_config is not None
    llm_prompt = load_prompt(PROMPT_DIRECTORY / f"prompt_{sys3_config.llm_config.prompt_version}.txt")

    run_number = next_sequential_number(OUTPUT_DIR, prefix="e3_drift")
    run_directory = OUTPUT_DIR / f"e3_drift_{run_number:03d}"
    run_directory.mkdir(parents=True, exist_ok=False)

    logger.info("Running E3 Teilfrage 2 (%s..%s) über %d Zyklustage...", window_start, window_end, len(decision_times))
    run_comparison(
        scenario, {"SYS3": sys3_config}, run_directory, project_config.project_root,
        local_timezone=project_config.timezone,
        run_id=run_directory.name, llm_prompt=llm_prompt,
        max_consecutive_llm_failures=comparison_config.max_consecutive_llm_failures,
        max_total_llm_failures=comparison_config.max_total_llm_failures,
        calendar_lookback_hours=comparison_config.calendar_lookback_hours,
        calendar_lookahead_hours=comparison_config.calendar_lookahead_hours,
    )

    logger.info("E3 Teilfrage 2 abgeschlossen, siehe %s.", run_directory)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
