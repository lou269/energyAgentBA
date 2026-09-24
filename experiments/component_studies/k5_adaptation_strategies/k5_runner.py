# conda activate forecasting-env
# python -m experiments.component_studies.k5_adaptation_strategies.k5_runner
# danach: python -m experiments.component_studies.k5_adaptation_strategies.k5_analysis

# Stufe A: Adaptionsaktion mit festem Trigger (Orakel), none / cut / step_regressor auf den K3-Szenarien plus scaled

import logging
from dataclasses import asdict
from itertools import product
from pathlib import Path

import pandas as pd

from experiments.component_studies.k3_anomaly_detection.k3_config import K3Config
from experiments.component_studies.k3_anomaly_detection.k3_scenarios import (
    build_k3_scenarios,
)
from experiments.component_studies.k5_adaptation_strategies.k5_config import (
    K5_CYCLE_CONFIG,
    K5Config,
    K5Strategy,
)
from experiments.component_studies.k5_adaptation_strategies.k5_evaluation import (
    label_oracle_results,
)
from experiments.component_studies.k5_adaptation_strategies.k5_oracle import (
    run_oracle,
    trigger_actions,
)
from experiments.component_studies.k5_adaptation_strategies.k5_scenarios import (
    add_scaled_scenario,
)
from src.common.target_series import read_preprocessed_target
from src.config.config_forecasting import ForecastingConfig
from src.config.project_config import ProjectConfig
from src.pipeline.io import create_experiment_run, df_to_csv

logger = logging.getLogger(__name__)


class K5Runner:
    def __init__(
        self,
        project_config: ProjectConfig | None = None,
        k3_config: K3Config | None = None,
        k5_config: K5Config | None = None,
        forecast_config: ForecastingConfig | None = None,
    ) -> None:
        self.project_config = project_config or ProjectConfig()
        self.k3_config = k3_config or K3Config()
        self.k5_config = k5_config or K5Config()
        self.forecast_config = forecast_config or ForecastingConfig()

    def run(self) -> Path:
        mains_series, target_imputed, target_value_implausible = (
            read_preprocessed_target(self.project_config)
        )

        run_directory, raw_directory = create_experiment_run(
            self.project_config.k5_output_dir,
            "k5",
            {"k3_config": asdict(self.k3_config), "k5_config": asdict(self.k5_config)},
        )

        runs: list[tuple[K5Strategy, int | None]] = [
            ("none", None),
            *product(self.k5_config.strategies, self.k5_config.trigger_days),
        ]
        results: list[pd.DataFrame] = []

        for cutover_date in self.k3_config.cutover_dates:
            scenarios = build_k3_scenarios(
                mains_series,
                cutover_date=cutover_date,
                coldstart_days=self.forecast_config.cycle_coldstart_days,
                monitoring_before_cutover_days=self.k3_config.monitoring_before_cutover_days,
                margin_after_days=self.k3_config.margin_after_days,
                step_injection_w=self.k3_config.step_injection_w,
                local_timezone=self.project_config.timezone,
                target_imputed=target_imputed,
                value_implausible=target_value_implausible,
            )
            scenarios = add_scaled_scenario(
                scenarios,
                cutover_date=cutover_date,
                scale_factor=self.k5_config.scale_factor,
                local_timezone=self.project_config.timezone,
            )

            for kind, scenario in scenarios.items():
                for strategy, trigger_day in runs:
                    logger.info(
                        "K5 %s_%s, %s, trigger day %s",
                        kind,
                        cutover_date,
                        strategy,
                        trigger_day,
                    )

                    oracle_results = run_oracle(
                        scenario,
                        K5_CYCLE_CONFIG,
                        actions=trigger_actions(
                            strategy,
                            cutover_date,
                            trigger_day,
                            self.project_config.timezone,
                        ),
                        streak_tolerance_window_days=K5_CYCLE_CONFIG.numerical_analysis_config.streak_tolerance_window_days,
                        local_timezone=self.project_config.timezone,
                    )
                    results.append(
                        label_oracle_results(
                            oracle_results,
                            kind=kind,
                            cutover_date=cutover_date,
                            strategy=strategy,
                            trigger_day=trigger_day,
                            local_timezone=self.project_config.timezone,
                        )
                    )

        df_to_csv(pd.concat(results, ignore_index=True), raw_directory, "k5_results")

        logger.info("K5 completed, see %s.", run_directory)
        return run_directory


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    K5Runner().run()


if __name__ == "__main__":
    main()
