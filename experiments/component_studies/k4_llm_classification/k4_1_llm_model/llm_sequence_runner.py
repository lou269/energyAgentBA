# open -a Ollama
# caffeinate -i python -m experiments.component_studies.k4_llm_classification.k4_1_llm_model.llm_sequence_runner

import logging

import pandas as pd

from experiments.component_studies.k4_llm_classification.k4_1_llm_model.llm_model_config import (
    K4_SEQUENCE_OUTPUT_ROOT, LLMModelExperimentConfig, build_sequence_configs,
)
from experiments.proposal_experiments.e1_new_device.e1_runner import OUTPUT_DIR as E1_OUTPUT_DIR
from experiments.proposal_experiments.e1_new_device.e1_scenarios import build_device_scenario
from experiments.proposal_experiments.e_config import E1Config
from experiments.proposal_experiments.shared import build_decision_times, crop_history_for_coldstart, load_target_series
from src.common.column_naming import channel_data_column
from src.common.timestamps import parse_utc_timestamp
from src.config.config_forecasting import ComparisonConfig, ForecastingConfig, SYS_VARIANTS
from src.config.project_config import ProjectConfig, ensure_project_directories
from src.llm.llm_run_artifacts import load_prompt
from src.llm.llm_runner import PROMPT_DIRECTORY
from src.pipeline.comparison_harness import run_comparison
from src.pipeline.io import next_sequential_number

logger = logging.getLogger(__name__)


class LLMSequenceRunner:

    def __init__(
        self,
        project_config: ProjectConfig | None = None,
        e1_config: E1Config | None = None,
        forecast_config: ForecastingConfig | None = None,
        experiment_config: LLMModelExperimentConfig | None = None,
    ) -> None:
        self.project_config = project_config or ProjectConfig()
        self.e1_config = e1_config or E1Config()
        self.forecast_config = forecast_config or ForecastingConfig()
        self.experiment_config = experiment_config or LLMModelExperimentConfig()

    def _read_device_hourly(self) -> pd.Series:
        device_data = pd.read_csv(E1_OUTPUT_DIR / "e1_device_hourly.csv", parse_dates=["timestamp"], index_col="timestamp")

        return device_data[channel_data_column(self.e1_config.device_meter_key, "hourly")]

    def run(self) -> None:
        cutover_time = parse_utc_timestamp(self.e1_config.cutover_time, "E1Config.cutover_time")
        ensure_project_directories(self.project_config)

        mains_series, target_imputed, target_value_implausible, _meter_key = load_target_series(self.project_config)
        device_hourly = self._read_device_hourly()

        decision_times = build_decision_times(
            cutover_time, cutover_time,
            margin_before_days=self.e1_config.margin_before_days, margin_after_days=self.e1_config.margin_after_days,
            local_timezone=self.project_config.timezone,
        )

        mains_series = crop_history_for_coldstart(
            mains_series, coldstart_hours=self.forecast_config.cycle_coldstart_hours, first_decision_time=decision_times[0],
        )

        scenario = build_device_scenario(
            mains_series, device_hourly, self.e1_config.device_meter_key,
            cutover_time=cutover_time, coldstart_hours=self.forecast_config.cycle_coldstart_hours,
            decision_times=decision_times, target_imputed=target_imputed,
            value_implausible=target_value_implausible,
        )
        
        configs = build_sequence_configs(self.experiment_config.model_variants, self.experiment_config.base_llm_config)

        if self.experiment_config.include_rule_based_baseline:
            configs["BASELINE"] = SYS_VARIANTS["SYS2"]

        llm_prompt = load_prompt(PROMPT_DIRECTORY / f"prompt_{self.experiment_config.base_llm_config.prompt_version}.txt")

        run_number = next_sequential_number(K4_SEQUENCE_OUTPUT_ROOT, prefix="k4_seq")
        run_directory = K4_SEQUENCE_OUTPUT_ROOT / f"k4_seq_{run_number:03d}"
        run_directory.mkdir(parents=True, exist_ok=False)

        comparison_config = ComparisonConfig()

        logger.info(
            "Running K4 model-sequence comparison (cutover=%s) over %d decision times, %d configs...", cutover_time, len(decision_times), len(configs),
        )

        run_comparison(
            scenario, configs, run_directory, self.project_config.project_root,
            local_timezone=self.project_config.timezone,
            run_id=run_directory.name, llm_prompt=llm_prompt,
            max_consecutive_llm_failures=comparison_config.max_consecutive_llm_failures,
            max_total_llm_failures=comparison_config.max_total_llm_failures,
            calendar_lookback_hours=comparison_config.calendar_lookback_hours,
            calendar_lookahead_hours=comparison_config.calendar_lookahead_hours,
        )

        logger.info("K4 model-sequence comparison completed, see %s.", run_directory)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    LLMSequenceRunner().run()


if __name__ == "__main__":
    main()