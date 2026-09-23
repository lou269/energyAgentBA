# conda activate forecasting-env
# python -m experiments.component_studies.k5_adaptation_strategies.k5_masking_runner
# danach: python -m experiments.component_studies.k5_adaptation_strategies.k5_masking_analysis

# Teil 2: peak/low-Tage nur für Prophet ausblenden. SYS2 zeichnet die Entscheidungen auf, das Orakel spielt sie ohne und mit Ausblenden nach

import logging
from dataclasses import asdict
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd

from experiments.component_studies.k3_anomaly_detection.k3_config import K3Config
from experiments.component_studies.k3_anomaly_detection.k3_scenarios import build_k3_scenarios
from experiments.component_studies.k5_adaptation_strategies.k5_config import K5_CYCLE_CONFIG, K5_DECISION_CONFIG, K5_MASKING_VARIANTS
from experiments.component_studies.k5_adaptation_strategies.k5_evaluation import label_oracle_results
from experiments.component_studies.k5_adaptation_strategies.k5_masking_evaluation import read_sys2_decisions
from experiments.component_studies.k5_adaptation_strategies.k5_oracle import replay_actions, replay_masked_days, run_oracle
from src.common.target_series import read_preprocessed_target
from src.config.config_forecasting import ComparisonConfig, ForecastingConfig
from src.config.project_config import ProjectConfig
from src.pipeline.comparison_harness import run_comparison
from src.pipeline.io import create_experiment_run, df_to_csv

logger = logging.getLogger(__name__)


class K5MaskingRunner:
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
            self.project_config.k5_output_dir, "k5_mask",
            {"k3_config": asdict(self.k3_config), "masking_variants": K5_MASKING_VARIANTS},
        )

        comparison_config = ComparisonConfig()
        streak_tolerance_window_days = K5_CYCLE_CONFIG.numerical_analysis_config.streak_tolerance_window_days
        decisions: list[pd.DataFrame] = []
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

            for kind, scenario in scenarios.items():
                logger.info("K5 masking %s_%s", kind, cutover_date)

                # wie in K3 braucht es vom Harness-Output nur die Summary
                with TemporaryDirectory() as scratch:
                    run_comparison(
                        scenario, {"SYS2": K5_DECISION_CONFIG}, Path(scratch), self.project_config.project_root,
                        local_timezone=self.project_config.timezone,
                        run_id=f"{run_directory.name}_{kind}_{cutover_date}",
                        max_consecutive_llm_failures=comparison_config.max_consecutive_llm_failures,
                        max_total_llm_failures=comparison_config.max_total_llm_failures,
                        calendar_lookback_days=comparison_config.calendar_lookback_days,
                        calendar_lookahead_days=comparison_config.calendar_lookahead_days,
                    )
                    scenario_decisions = read_sys2_decisions(Path(scratch), kind=kind, cutover_date=cutover_date)

                decisions.append(scenario_decisions)

                for variant, masked_classifications in K5_MASKING_VARIANTS.items():
                    oracle_results = run_oracle(
                        scenario,
                        K5_CYCLE_CONFIG,
                        actions=replay_actions(scenario_decisions),
                        masked_days=replay_masked_days(
                            scenario_decisions, masked_classifications=masked_classifications, local_timezone=self.project_config.timezone
                        ),
                        streak_tolerance_window_days=streak_tolerance_window_days,
                        local_timezone=self.project_config.timezone,
                    )
                    results.append(
                        label_oracle_results(
                            oracle_results,
                            kind=kind,
                            cutover_date=cutover_date,
                            strategy=variant,
                            trigger_day=None,
                            local_timezone=self.project_config.timezone,
                        )
                    )

        df_to_csv(pd.concat(decisions, ignore_index=True), raw_directory, "k5_mask_decisions")
        df_to_csv(pd.concat(results, ignore_index=True), raw_directory, "k5_mask_results")

        logger.info("K5 masking completed, see %s.", run_directory)
        return run_directory


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    logging.getLogger("src.pipeline.comparison_harness").setLevel(logging.WARNING)
    K5MaskingRunner().run()


if __name__ == "__main__":
    main()