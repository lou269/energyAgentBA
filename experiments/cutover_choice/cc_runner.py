# conda activate forecasting-env
# python -m experiments.cutover_choice.cc_runner

# Termine der Standard-Cutover für einen neuen Abschnitt: Control-Fenster je Kandidat mit den festen Schwellen
import logging
from dataclasses import asdict
from pathlib import Path

import pandas as pd

from experiments.common.scenarios import load_split_bounds, load_target
from experiments.common.standard_config import (
    COLDSTART_DAYS,
    LOCAL_TIMEZONE,
    PROJECT_CONFIG,
    STANDARD_CONFIG,
)
from experiments.common.standard_scenarios import build_standard_scenarios
from experiments.cutover_choice.cc_config import RESULTS_FILE, RUN_PREFIX, CcConfig
from experiments.cutover_choice.cc_evaluation import (
    candidate_cutovers,
    summarize_window,
)
from experiments.k1_detection.k1_runner import chain_for
from src.common.timestamps import analyzed_day_index
from src.config.config_forecasting import NumericalAnalysisConfig
from src.pipeline.io import create_experiment_run, df_to_csv

logger = logging.getLogger(__name__)


def run(cc_config: CcConfig) -> Path:
    run_directory, raw_directory = create_experiment_run(
        PROJECT_CONFIG.experiment_output_dir / cc_config.output_subdir,
        RUN_PREFIX,
        {
            "standard_config": asdict(STANDARD_CONFIG),
            "cc_config": asdict(cc_config),
        },
    )

    split_start, split_end = load_split_bounds(STANDARD_CONFIG.split)
    cutovers = candidate_cutovers(
        load_target(STANDARD_CONFIG.split)[0].index[0],
        split_start,
        split_end,
        coldstart_days=COLDSTART_DAYS,
        before_days=STANDARD_CONFIG.monitoring_before_cutover_days,
        after_days=STANDARD_CONFIG.margin_after_days,
        step_days=cc_config.step_days,
        local_timezone=LOCAL_TIMEZONE,
    )

    analysis_config = NumericalAnalysisConfig()
    windows = []
    for cutover_date in cutovers:
        logger.info("Cutover-Kandidat %s", cutover_date)
        control = build_standard_scenarios(cutover_date, ("control",))["control"]
        days = analyzed_day_index(
            pd.DatetimeIndex(control.decision_times), LOCAL_TIMEZONE
        ).tz_localize(None)
        chain = chain_for(control.target_series, days, analysis_config, {})
        windows.append(asdict(summarize_window(chain, cutover_date)))

    df_to_csv(pd.DataFrame(windows), raw_directory, RESULTS_FILE)
    logger.info("Cutover-Wahl completed, see %s.", run_directory)
    return run_directory


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    run(CcConfig())


if __name__ == "__main__":
    main()
