# conda activate nilmtk-env
# python -m experiments.e1_new_device.e1_device_check
# läuft in nilmtk-env, darf deshalb nichts aus forecasting/pipeline importieren

from __future__ import annotations

import logging

from experiments.common.nilmtk_channels import (
    load_nilmtk_context,
    select_appliance_channels,
)
from experiments.common.standard_config import PROJECT_CONFIG, STANDARD_CONFIG
from experiments.e1_new_device.e1_config import DEVICES_HOURLY_FILE, E1Config
from src.pipeline.io import df_to_csv

logger = logging.getLogger(__name__)


def run(e1_config: E1Config) -> None:
    output_directory = PROJECT_CONFIG.e1_output_dir / e1_config.device_selection_subdir

    context = load_nilmtk_context(STANDARD_CONFIG.split)

    logger.info(
        "Ranking all appliance channels over %s to %s...",
        context.window_start,
        context.window_end,
    )

    selection = select_appliance_channels(
        context, context.window_start, context.window_end
    )

    output_directory.mkdir(parents=True, exist_ok=True)
    df_to_csv(selection.ranking, output_directory, "e1_device_ranking")
    df_to_csv(
        selection.data_hourly.reset_index(), output_directory, DEVICES_HOURLY_FILE
    )

    logger.info(
        "Largest share: %s, see %s.",
        selection.ranking["meter_key"].iloc[0],
        output_directory,
    )


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    run(E1Config())


if __name__ == "__main__":
    main()
