# open -a Ollama
# conda run -n forecasting-env python -m experiments.proposal_experiments.e1_new_device.e1_runner


# 3 Läufe derselben Zeitreihe: SYS1 (Referenz, adaptionsfrei), SYS2 (Regel), SYS3 (LLM)

import logging
from pathlib import Path

import pandas as pd

from experiments.proposal_experiments.e_config import E1Config
from experiments.proposal_experiments.e1_new_device.e1_scenarios import build_device_scenario
from experiments.proposal_experiments.shared import build_decision_times, load_target_series
from src.common.column_naming import channel_data_column
from src.common.timestamps import parse_utc_timestamp
from src.config.project_config import ProjectConfig, ensure_project_directories
from src.llm.llm_run_artifacts import load_prompt
from src.llm.llm_runner import PROMPT_DIRECTORY
from src.pipeline.comparison_harness import run_comparison
from src.pipeline.cycle_variants import SYS_VARIANTS
from src.pipeline.io import next_sequential_number

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path(__file__).parent / "output"


class E1Runner:
    def __init__(
        self,
        project_config: ProjectConfig | None = None,
        e1_config: E1Config | None = None,
    ) -> None:
        self.project_config = project_config or ProjectConfig()
        self.e1_config = e1_config or E1Config()

    def _read_device_hourly(self) -> pd.Series:
        device_data = pd.read_csv(OUTPUT_DIR / "e1_device_hourly.csv", parse_dates=["timestamp"], index_col="timestamp")

        return device_data[channel_data_column(self.e1_config.device_meter_key, "hourly")]

    def run(self) -> None:
        cutover_time = parse_utc_timestamp(self.e1_config.cutover_time, "E1Config.cutover_time")
        ensure_project_directories(self.project_config)

        mains_series, target_imputed, _meter_key = load_target_series(self.project_config)
        device_hourly = self._read_device_hourly()

        decision_times = build_decision_times(
            cutover_time, cutover_time,
            margin_before_days=self.e1_config.margin_before_days, margin_after_days=self.e1_config.margin_after_days
        )

        scenario = build_device_scenario(
            mains_series, device_hourly, self.e1_config.device_meter_key,
            cutover_time=cutover_time, coldstart_hours=self.e1_config.coldstart_hours,
            decision_times=decision_times, target_imputed=target_imputed
        )

        sys3_config = SYS_VARIANTS["SYS3"]
        assert sys3_config.llm_config is not None
        
        llm_prompt = load_prompt(PROMPT_DIRECTORY / f"prompt_{sys3_config.llm_config.prompt_version}.txt")

        e1_run_number = next_sequential_number(OUTPUT_DIR, prefix="e1")
        e1_run_directory = OUTPUT_DIR / f"e1_{e1_run_number:03d}"
        e1_run_directory.mkdir(parents=True, exist_ok=False)

        configs = {
            "SYS1": SYS_VARIANTS["SYS1"],
            "SYS2": SYS_VARIANTS["SYS2"],
            "SYS3": sys3_config,
        }
        

        logger.info("Running E1 (cutover=%s) over %d decision times...", cutover_time, len(decision_times))
        run_comparison(scenario, configs, e1_run_directory, self.project_config.project_root, run_id=e1_run_directory.name, llm_prompt=llm_prompt)

        logger.info("E1 completed, see %s.", e1_run_directory)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    E1Runner().run()


if __name__ == "__main__":
    main()