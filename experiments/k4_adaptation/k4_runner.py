# conda activate forecasting-env
# python -m experiments.k4_adaptation.k4_runner [strategies|masking]
# danach: python -m experiments.k4_adaptation.k4_report [strategies|masking] [run_directory]

# strategies: Adaptionsaktion mit festem Trigger (Orakel), none / cut / step_regressor auf den Standard-Szenarien control/step/scaled
# masking: peak/low-Tage nur für Prophet ausblenden. SYS2 zeichnet die Entscheidungen auf, das Orakel spielt sie ohne und mit Ausblenden nach

import logging
import sys
from dataclasses import asdict
from pathlib import Path

import pandas as pd

from experiments.common.harness import run_scenario_in_scratch
from experiments.common.standard_config import PROJECT_CONFIG, STANDARD_CONFIG
from experiments.common.standard_scenarios import build_standard_scenarios
from experiments.k4_adaptation.k4_config import (
    MASKING_DECISIONS_FILE,
    MASKING_RESULTS_FILE,
    MASKING_RUN_PREFIX,
    RESULTS_FILE,
    RUN_PREFIX,
    K4Config,
    K4Strategy,
)
from experiments.k4_adaptation.k4_evaluation import (
    label_oracle_results,
    read_sys2_decisions,
)
from experiments.k4_adaptation.k4_oracle import (
    replay_actions,
    replay_masked_days,
    run_oracle,
    trigger_actions,
)
from src.config.config_forecasting import SYS_VARIANTS
from src.pipeline.io import create_experiment_run, df_to_csv

logger = logging.getLogger(__name__)


def run_strategies(k4_config: K4Config) -> Path:
    cycle_config = SYS_VARIANTS[k4_config.cycle_system]
    run_directory, raw_directory = create_experiment_run(
        PROJECT_CONFIG.k4_output_dir,
        RUN_PREFIX,
        {
            "standard_config": asdict(STANDARD_CONFIG),
            "k4_config": asdict(k4_config),
            "seed": cycle_config.forecasting_config.seed,
        },
    )

    runs: list[tuple[K4Strategy, int | None]] = [("none", None)]
    for action in k4_config.strategies:
        for day in k4_config.trigger_days:
            runs.append((action, day))
    results: list[pd.DataFrame] = []

    for cutover_date in STANDARD_CONFIG.cutover_dates:
        for kind, scenario in build_standard_scenarios(
            cutover_date,
            k4_config.kinds,
            margin_before_days=STANDARD_CONFIG.monitoring_before_cutover_days,
            margin_after_days=STANDARD_CONFIG.margin_after_days,
        ).items():
            for strategy, trigger_day in runs:
                logger.info(
                    "K4 %s_%s, %s, trigger day %s",
                    kind,
                    cutover_date,
                    strategy,
                    trigger_day,
                )

                oracle_results = run_oracle(
                    scenario,
                    cycle_config,
                    trigger_actions(strategy, cutover_date, trigger_day),
                )
                results.append(
                    label_oracle_results(
                        oracle_results,
                        kind=kind,
                        cutover_date=cutover_date,
                        strategy=strategy,
                        trigger_day=trigger_day,
                    )
                )

    df_to_csv(pd.concat(results, ignore_index=True), raw_directory, RESULTS_FILE)

    logger.info("K4 completed, see %s.", run_directory)
    return run_directory


def run_masking(k4_config: K4Config) -> Path:
    cycle_config = SYS_VARIANTS[k4_config.cycle_system]
    run_directory, raw_directory = create_experiment_run(
        PROJECT_CONFIG.k4_output_dir,
        MASKING_RUN_PREFIX,
        {
            "standard_config": asdict(STANDARD_CONFIG),
            "k4_config": asdict(k4_config),
            "seed": cycle_config.forecasting_config.seed,
        },
    )
    # replay spielt nur die Resets nach, mask blendet zusätzlich die Tage aus
    masking_variants = {"replay": (), "mask": k4_config.masked_classifications}
    decisions: list[pd.DataFrame] = []
    results: list[pd.DataFrame] = []

    for cutover_date in STANDARD_CONFIG.cutover_dates:
        for kind, scenario in build_standard_scenarios(
            cutover_date,
            k4_config.masking_kinds,
            margin_before_days=STANDARD_CONFIG.monitoring_before_cutover_days,
            margin_after_days=STANDARD_CONFIG.margin_after_days,
        ).items():
            logger.info("K4 masking %s_%s", kind, cutover_date)

            summary, _anomaly = run_scenario_in_scratch(
                scenario,
                {k4_config.decision_system: SYS_VARIANTS[k4_config.decision_system]},
                run_id=f"{run_directory.name}_{kind}_{cutover_date}",
            )
            scenario_decisions = read_sys2_decisions(
                summary, kind=kind, cutover_date=cutover_date
            )
            decisions.append(scenario_decisions)

            for variant, masked_classifications in masking_variants.items():
                oracle_results = run_oracle(
                    scenario,
                    cycle_config,
                    replay_actions(scenario_decisions),
                    replay_masked_days(scenario_decisions, masked_classifications),
                )
                results.append(
                    label_oracle_results(
                        oracle_results,
                        kind=kind,
                        cutover_date=cutover_date,
                        strategy=variant,
                        trigger_day=None,
                    )
                )

    df_to_csv(
        pd.concat(decisions, ignore_index=True), raw_directory, MASKING_DECISIONS_FILE
    )
    df_to_csv(
        pd.concat(results, ignore_index=True), raw_directory, MASKING_RESULTS_FILE
    )

    logger.info("K4 masking completed, see %s.", run_directory)
    return run_directory


def main() -> None:
    part = sys.argv[1] if len(sys.argv) > 1 else "strategies"
    logging.basicConfig(level=logging.INFO)

    if part == "strategies":
        run_strategies(K4Config())
    else:
        run_masking(K4Config())


if __name__ == "__main__":
    main()
