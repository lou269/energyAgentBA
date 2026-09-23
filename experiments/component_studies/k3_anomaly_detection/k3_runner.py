# conda activate forecasting-env
# python -m experiments.component_studies.k3_anomaly_detection.k3_runner
# danach: python -m experiments.component_studies.k3_anomaly_detection.k3_analysis

# Referenzfenster der Anomalieerkennung, je Cutover control/step, einmal isoliert und einmal im Kreislauf mit Adaption (rule, ohne LLM)

import logging
from dataclasses import asdict
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd

from experiments.component_studies.k3_anomaly_detection.k3_config import K3_MODES, K3Config
from experiments.component_studies.k3_anomaly_detection.k3_evaluation import read_scenario_results
from experiments.component_studies.k3_anomaly_detection.k3_scenarios import build_k3_scenarios
from src.common.target_series import read_preprocessed_target
from src.config.config_forecasting import ComparisonConfig, ForecastingConfig
from src.config.project_config import ProjectConfig
from src.pipeline.comparison_harness import run_comparison
from src.pipeline.io import create_experiment_run, df_to_csv

logger = logging.getLogger(__name__)


class K3Runner:
    def __init__(
        self,
        project_config: ProjectConfig | None = None,
        k3_config: K3Config | None = None,
        forecast_config: ForecastingConfig | None = None,
    ) -> None:
        self.project_config = project_config or ProjectConfig()
        self.k3_config = k3_config or K3Config()
        self.forecast_config = forecast_config or ForecastingConfig()

    def run(self) -> Path:
        mains_series, target_imputed, target_value_implausible = read_preprocessed_target(self.project_config)

        run_directory, raw_directory = create_experiment_run(
            self.project_config.k3_output_dir, "k3", {"k3_config": asdict(self.k3_config)},
        )

        comparison_config = ComparisonConfig()
        scenario_results: list[pd.DataFrame] = []

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

            for mode, variants in K3_MODES.items():
                for kind, scenario in scenarios.items():
                    scenario_name = f"{kind}_{cutover_date}"
                    logger.info("K3 %s, %s", scenario_name, mode)

                    # run_comparison schreibt Forecasts, States und Manifeste mit, K3 braucht davon nur Anomalie- und Summary-Zeilen
                    with TemporaryDirectory() as scratch:
                        run_comparison(
                            scenario, variants, Path(scratch), self.project_config.project_root,
                            local_timezone=self.project_config.timezone,
                            run_id=f"{run_directory.name}_{scenario_name}_{mode}",
                            max_consecutive_llm_failures=comparison_config.max_consecutive_llm_failures,
                            max_total_llm_failures=comparison_config.max_total_llm_failures,
                            calendar_lookback_days=comparison_config.calendar_lookback_days,
                            calendar_lookahead_days=comparison_config.calendar_lookahead_days,
                        )
                        scenario_results.append(
                            read_scenario_results(
                                Path(scratch),
                                mode=mode,
                                kind=kind,
                                cutover_date=cutover_date,
                                local_timezone=self.project_config.timezone,
                            )
                        )

        df_to_csv(pd.concat(scenario_results, ignore_index=True), raw_directory, "k3_results")

        logger.info("K3 completed, see %s.", run_directory)
        return run_directory


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    # eine Zeile pro Zyklus und Variante wären hier gut 5.000 Zeilen
    logging.getLogger("src.pipeline.comparison_harness").setLevel(logging.WARNING)
    K3Runner().run()


if __name__ == "__main__":
    main()