# conda activate forecasting-env
# python -m experiments.k3_adaptation.k3_runner [strategies|masking]
# danach: python -m experiments.k3_adaptation.k3_report [strategies|masking] [run_directory]

# strategies: Adaptionsaktion mit festem Trigger (Orakel), none / cut / step_regressor auf dem Standard-Szenario scaled
# masking: peak/low-Tage nur für Prophet ausblenden. SYS2 zeichnet die Entscheidungen auf, das Orakel spielt sie ohne und mit Ausblenden nach

import logging
import sys
from dataclasses import asdict
from pathlib import Path

import pandas as pd

from experiments.common.harness import run_scenario_in_scratch
from experiments.common.standard_config import PROJECT_CONFIG, STANDARD_CONFIG
from experiments.common.standard_scenarios import build_standard_scenarios
from experiments.k3_adaptation.k3_config import (
    MASKING_DECISIONS_FILE,
    MASKING_RESULTS_FILE,
    MASKING_RUN_PREFIX,
    RESULTS_FILE,
    RUN_PREFIX,
    K3Config,
    K3Strategy,
)
from experiments.k3_adaptation.k3_evaluation import (
    label_oracle_results,
    read_sys2_decisions,
)
from experiments.k3_adaptation.k3_oracle import (
    replay_actions,
    replay_masked_days,
    run_oracle,
    trigger_actions,
)
from src.config.config_forecasting import SYS_VARIANTS
from src.pipeline.io import create_experiment_run, df_to_csv

logger = logging.getLogger(__name__)


def run_strategies(k3_config: K3Config) -> Path:
    cycle_config = SYS_VARIANTS[k3_config.cycle_system]
    run_directory, raw_directory = create_experiment_run(
        PROJECT_CONFIG.k3_output_dir,
        RUN_PREFIX,
        {
            "standard_config": asdict(STANDARD_CONFIG),
            "k3_config": asdict(k3_config),
            "seed": cycle_config.forecasting_config.seed,
        },
    )

    runs: list[tuple[K3Strategy, int | None]] = [("none", None)]
    for action in k3_config.strategies:
        for day in k3_config.trigger_days:
            runs.append((action, day))
    results: list[pd.DataFrame] = []

    for cutover_id in k3_config.cutovers[STANDARD_CONFIG.split]:
        cutover_date = STANDARD_CONFIG.cutover_date(cutover_id)
        for kind, scenario in build_standard_scenarios(
            cutover_date,
            k3_config.kinds,
        ).items():
            for strategy, trigger_day in runs:
                logger.info(
                    "K3 %s_%s, %s, trigger day %s",
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

    logger.info("K3 completed, see %s.", run_directory)
    return run_directory


def run_masking(k3_config: K3Config) -> Path:
    cycle_config = SYS_VARIANTS[k3_config.cycle_system]
    run_directory, raw_directory = create_experiment_run(
        PROJECT_CONFIG.k3_output_dir,
        MASKING_RUN_PREFIX,
        {
            "standard_config": asdict(STANDARD_CONFIG),
            "k3_config": asdict(k3_config),
            "seed": cycle_config.forecasting_config.seed,
        },
    )
    # replay spielt nur die Resets nach, mask blendet zusätzlich die Tage aus
    masking_variants = {"replay": (), "mask": k3_config.masked_classifications}
    decisions: list[pd.DataFrame] = []
    results: list[pd.DataFrame] = []

    for cutover_id in k3_config.cutovers[STANDARD_CONFIG.split]:
        cutover_date = STANDARD_CONFIG.cutover_date(cutover_id)
        for kind, scenario in build_standard_scenarios(
            cutover_date,
            k3_config.masking_kinds,
        ).items():
            logger.info("K3 masking %s_%s", kind, cutover_date)

            summary, _anomaly = run_scenario_in_scratch(
                scenario,
                {k3_config.decision_system: SYS_VARIANTS[k3_config.decision_system]},
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

    logger.info("K3 masking completed, see %s.", run_directory)
    return run_directory


def main() -> None:
    part = sys.argv[1] if len(sys.argv) > 1 else "strategies"
    logging.basicConfig(level=logging.INFO)

    if part == "strategies":
        run_strategies(K3Config())
    else:
        run_masking(K3Config())


if __name__ == "__main__":
    main()
