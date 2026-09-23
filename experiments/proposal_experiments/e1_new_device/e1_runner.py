# open -a Ollama
# conda run -n forecasting-env python -m experiments.proposal_experiments.e1_new_device.e1_runner
# conda run -n forecasting-env python -m experiments.proposal_experiments.e1_new_device.e1_runner --control


# 3 Läufe derselben Zeitreihe: SYS1 (Referenz, adaptionsfrei), SYS2 (Regel), SYS3 (LLM)

import argparse
import logging
from dataclasses import asdict

from experiments.proposal_experiments.e_config import E1Config
from experiments.proposal_experiments.e1_new_device.e1_scenarios import build_device_scenario, load_device_hourly
from experiments.proposal_experiments.shared import build_decision_times, crop_history_for_coldstart, load_target_series
from src.common.timestamps import local_midnight_utc
from src.config.project_config import ProjectConfig, ensure_project_directories
from src.llm.llm_run_artifacts import load_prompt
from src.llm.llm_runner import PROMPT_DIRECTORY
from src.pipeline.comparison_harness import run_comparison
from src.config.config_forecasting import ComparisonConfig, ForecastingConfig, SYS_VARIANTS
from src.pipeline.io import create_experiment_run

logger = logging.getLogger(__name__)


class E1Runner:
    def __init__(
        self,
        project_config: ProjectConfig | None = None,
        e1_config: E1Config | None = None,
        forecast_config: ForecastingConfig | None = None
    ) -> None:
        self.project_config = project_config or ProjectConfig()
        self.e1_config = e1_config or E1Config()
        self.forecast_config = forecast_config or ForecastingConfig()

    def run(self, apply_device_injection: bool = True) -> None:
        cutover_time = local_midnight_utc(self.e1_config.cutover_date, self.project_config.timezone)
        ensure_project_directories(self.project_config)

        mains_series, target_imputed, target_value_implausible, _meter_key = load_target_series(self.project_config)
        device_hourly = load_device_hourly(self.e1_config.device_meter_key)

        decision_times = build_decision_times(
            cutover_time, cutover_time,
            margin_before_days=self.e1_config.margin_before_days, margin_after_days=self.e1_config.margin_after_days,
            local_timezone=self.project_config.timezone,
        )

        mains_series = crop_history_for_coldstart(
            mains_series, coldstart_days=self.forecast_config.cycle_coldstart_days, first_decision_time=decision_times[0],
            local_timezone=self.project_config.timezone,
        )

        scenario = build_device_scenario(
            mains_series, device_hourly, self.e1_config.device_meter_key,
            cutover_time=cutover_time, coldstart_days=self.forecast_config.cycle_coldstart_days,
            decision_times=decision_times, target_imputed=target_imputed,
            value_implausible=target_value_implausible,
            apply_device_injection=apply_device_injection,
        )

        sys3_config = SYS_VARIANTS["SYS3"]
        assert sys3_config.llm_config is not None

        llm_prompt = load_prompt(PROMPT_DIRECTORY / f"prompt_{sys3_config.llm_config.prompt_version}.txt")


        run_prefix = "e1" if apply_device_injection else "e1_control"
        e1_run_directory, raw_directory = create_experiment_run(
            self.project_config.e1_output_dir, run_prefix, {"e1_config": asdict(self.e1_config)},
        )

        configs = {
            "SYS1": SYS_VARIANTS["SYS1"],
            "SYS2": SYS_VARIANTS["SYS2"],
            "SYS3": sys3_config,
        }
        

        comparison_config = ComparisonConfig()

        logger.info(
            "Running E1 (cutover=%s, apply_device_injection=%s) over %d decision times...", cutover_time, apply_device_injection, len(decision_times),
        )
        run_comparison(
            scenario, configs, raw_directory, self.project_config.project_root,
            local_timezone=self.project_config.timezone,
            run_id=e1_run_directory.name, llm_prompt=llm_prompt,
            max_consecutive_llm_failures=comparison_config.max_consecutive_llm_failures,
            max_total_llm_failures=comparison_config.max_total_llm_failures,
            calendar_lookback_days=comparison_config.calendar_lookback_days,
            calendar_lookahead_days=comparison_config.calendar_lookahead_days,
        )

        logger.info("E1 completed, see %s.", e1_run_directory)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--control", action="store_true",
        help="Kontrolllauf: unveränderte Mains-Reihe statt der Geräte-Injektion, identische decision_times",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    E1Runner().run(apply_device_injection=not args.control)


if __name__ == "__main__":
    main()