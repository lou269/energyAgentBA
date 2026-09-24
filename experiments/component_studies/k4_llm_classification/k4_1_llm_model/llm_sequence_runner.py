# open -a Ollama
# caffeinate -i python -m experiments.component_studies.k4_llm_classification.k4_1_llm_model.llm_sequence_runner

import logging
from dataclasses import asdict

from experiments.component_studies.k4_llm_classification.k4_1_llm_model.llm_model_config import (
    LLMModelExperimentConfig,
    build_sequence_configs,
)
from experiments.proposal_experiments.e1_new_device.e1_scenarios import (
    build_device_scenario,
    load_device_hourly,
)
from experiments.proposal_experiments.e_config import E1Config
from experiments.proposal_experiments.shared import (
    build_decision_times,
    crop_history_for_coldstart,
)
from src.common.target_series import load_target_series
from src.common.timestamps import local_midnight_utc
from src.config.config_forecasting import (
    ComparisonConfig,
    ForecastingConfig,
    SYS_VARIANTS,
)
from src.config.project_config import ProjectConfig, ensure_project_directories
from src.llm.llm_run_artifacts import load_prompt
from src.llm.llm_runner import PROMPT_DIRECTORY
from src.pipeline.comparison_harness import run_comparison
from src.pipeline.io import create_experiment_run

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

    def run(self) -> None:
        cutover_time = local_midnight_utc(
            self.e1_config.cutover_date, self.project_config.timezone
        )
        ensure_project_directories(self.project_config)

        mains_series, target_imputed, target_value_implausible, _meter_key = (
            load_target_series(self.project_config)
        )
        devices_hourly = load_device_hourly(
            self.project_config.e1_output_dir / self.e1_config.device_selection_subdir,
            self.e1_config.device_meter_keys,
        )

        decision_times = build_decision_times(
            cutover_time,
            cutover_time,
            margin_before_days=self.e1_config.margin_before_days,
            margin_after_days=self.e1_config.margin_after_days,
            local_timezone=self.project_config.timezone,
        )

        mains_series = crop_history_for_coldstart(
            mains_series,
            coldstart_days=self.forecast_config.cycle_coldstart_days,
            first_decision_time=decision_times[0],
            local_timezone=self.project_config.timezone,
        )

        scenario = build_device_scenario(
            mains_series,
            devices_hourly,
            self.e1_config.device_meter_keys,
            cutover_time=cutover_time,
            coldstart_days=self.forecast_config.cycle_coldstart_days,
            decision_times=decision_times,
            target_imputed=target_imputed,
            value_implausible=target_value_implausible,
        )

        configs = build_sequence_configs(
            self.experiment_config.model_variants,
            self.experiment_config.base_llm_config,
        )

        if self.experiment_config.include_rule_based_baseline:
            configs["BASELINE"] = SYS_VARIANTS["SYS2"]

        llm_prompt = load_prompt(
            PROMPT_DIRECTORY
            / f"prompt_{self.experiment_config.base_llm_config.prompt_version}.txt"
        )

        run_directory, raw_directory = create_experiment_run(
            self.project_config.k4_output_dir,
            "k4_seq",
            {
                "experiment_config": asdict(self.experiment_config),
                "e1_config": asdict(self.e1_config),
            },
        )

        comparison_config = ComparisonConfig()

        logger.info(
            "Running K4 model-sequence comparison (cutover=%s) over %d decision times, %d configs...",
            cutover_time,
            len(decision_times),
            len(configs),
        )

        run_comparison(
            scenario,
            configs,
            raw_directory,
            self.project_config.project_root,
            local_timezone=self.project_config.timezone,
            run_id=run_directory.name,
            llm_prompt=llm_prompt,
            max_consecutive_llm_failures=comparison_config.max_consecutive_llm_failures,
            max_total_llm_failures=comparison_config.max_total_llm_failures,
            calendar_lookback_days=comparison_config.calendar_lookback_days,
            calendar_lookahead_days=comparison_config.calendar_lookahead_days,
        )

        logger.info("K4 model-sequence comparison completed, see %s.", run_directory)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    LLMSequenceRunner().run()


if __name__ == "__main__":
    main()
