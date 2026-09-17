# open -a Ollama
# conda run -n forecasting-env python -m experiments.proposal_experiments.e2_absence.e2_runner


# Fünf Läufe: SYS1 (Referenz, adaptionsfrei) + SYS2 (Regel) und SYS3 (LLM) je einmal ohne (CTX0) und mit (CTX1) Kalenderkontext.

import logging
from pathlib import Path

import pandas as pd

from experiments.proposal_experiments.e_config import E2Config
from experiments.proposal_experiments.e2_absence.e2_scenarios import build_ctx_scenarios
from experiments.proposal_experiments.e2_absence.e2_selection import load_calendar_events, resolve_absence_window, select_channels_for_subtraction
from experiments.proposal_experiments.shared import build_decision_times, load_target_series, subtract_channels_in_window
from src.config.project_config import ProjectConfig, ensure_project_directories
from src.llm.llm_run_artifacts import load_prompt
from src.llm.llm_runner import PROMPT_DIRECTORY
from src.pipeline.comparison_harness import run_comparison
from src.config.config_forecasting import ComparisonConfig, SYS_VARIANTS
from src.pipeline.io import next_sequential_number

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path(__file__).parent / "output"


class E2Runner:
    def __init__(
        self,
        project_config: ProjectConfig | None = None,
        e2_config: E2Config | None = None,
    ) -> None:
        self.project_config = project_config or ProjectConfig()
        self.e2_config = e2_config or E2Config()

    def _read_absence_channel_selection(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        ranking_file = OUTPUT_DIR / "absence_channel_ranking.csv"
        data_file = OUTPUT_DIR / "absence_channel_data_hourly.csv"

        ranking = pd.read_csv(ranking_file)
        data_hourly = pd.read_csv(data_file, parse_dates=["timestamp"], index_col="timestamp")

        return ranking, data_hourly

    def run(self) -> None:
        ensure_project_directories(self.project_config)

        mains_series, target_imputed, _meter_key = load_target_series(self.project_config)

        calendar_events = load_calendar_events(self.e2_config.calendar_events_file)
        window_start, window_end = resolve_absence_window(calendar_events, self.e2_config.active_absence_event_id)
        decision_times = build_decision_times(
            window_start,
            window_end,
            margin_before_days=self.e2_config.decision_time_margin_before_days,
            margin_after_days=self.e2_config.decision_time_margin_after_days,
        )

        ranking, appliance_data_hourly = self._read_absence_channel_selection()
        selected_channels = select_channels_for_subtraction(ranking, min_coverage_share=self.e2_config.min_coverage_share_for_subtraction)

        logger.info("Subtracting %d channel(s) for the absence week: %s", len(selected_channels), ", ".join(selected_channels))

        absence_adjusted_series = subtract_channels_in_window(
            mains_series,
            appliance_data_hourly,
            selected_channels,
            window_start=window_start,
            window_end=window_end,
        )

        ctx0_scenario, ctx1_scenario = build_ctx_scenarios(
            absence_adjusted_series,
            coldstart_hours=self.e2_config.coldstart_hours,
            decision_times=decision_times,
            calendar_events=calendar_events,
            target_imputed=target_imputed,
        )

        sys3_config = SYS_VARIANTS["SYS3"]
        assert sys3_config.llm_config is not None
        llm_prompt = load_prompt(PROMPT_DIRECTORY / f"prompt_{sys3_config.llm_config.prompt_version}.txt")

        e2_run_number = next_sequential_number(OUTPUT_DIR, prefix="e2")
        e2_run_directory = OUTPUT_DIR / f"e2_{e2_run_number:03d}"
        e2_run_directory.mkdir(parents=True, exist_ok=False)

        ctx0_dir = e2_run_directory / "ctx0"
        ctx1_dir = e2_run_directory / "ctx1"

        ctx0_configs = {
            "SYS1": SYS_VARIANTS["SYS1"],
            "SYS2_CTX0": SYS_VARIANTS["SYS2"],
            "SYS3_CTX0": sys3_config
        }
        ctx1_configs = {
            "SYS2_CTX1": SYS_VARIANTS["SYS2"],
            "SYS3_CTX1": sys3_config
        }

        comparison_config = ComparisonConfig()

        logger.info("Running E2/CTX0 (no calendar context) over %d decision times...", len(decision_times))
        ctx0_result = run_comparison(
            ctx0_scenario, ctx0_configs, ctx0_dir, self.project_config.project_root,
            local_timezone=self.project_config.timezone,
            run_id=f"{e2_run_directory.name}_ctx0", llm_prompt=llm_prompt,
            max_consecutive_llm_failures=comparison_config.max_consecutive_llm_failures,
            max_total_llm_failures=comparison_config.max_total_llm_failures,
            calendar_lookback_hours=comparison_config.calendar_lookback_hours,
            calendar_lookahead_hours=comparison_config.calendar_lookahead_hours,
        )

        logger.info("Running E2/CTX1 (with calendar context) over %d decision times...", len(decision_times))
        ctx1_result = run_comparison(
            ctx1_scenario, ctx1_configs, ctx1_dir, self.project_config.project_root,
            local_timezone=self.project_config.timezone,
            run_id=f"{e2_run_directory.name}_ctx1", llm_prompt=llm_prompt,
            max_consecutive_llm_failures=comparison_config.max_consecutive_llm_failures,
            max_total_llm_failures=comparison_config.max_total_llm_failures,
            calendar_lookback_hours=comparison_config.calendar_lookback_hours,
            calendar_lookahead_hours=comparison_config.calendar_lookahead_hours,
        )

        combined = pd.concat([ctx0_result, ctx1_result], ignore_index=True)
        combined_output_file = e2_run_directory / "e2_comparison_summary.csv"
        combined.to_csv(combined_output_file, index=False)


        logger.info("E2 completed: %d rows written to %s", len(combined), combined_output_file)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    E2Runner().run()
    
if __name__ == "__main__":
    main()