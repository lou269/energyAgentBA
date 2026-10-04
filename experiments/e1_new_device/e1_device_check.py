# conda activate nilmtk-env
# python -m experiments.e1_new_device.e1_device_check
# läuft in nilmtk-env, darf deshalb nichts aus forecasting/pipeline importieren

from __future__ import annotations

import logging

from experiments.common.nilmtk_channels import (
    load_nilmtk_context,
    select_appliance_channels,
)
from experiments.common.standard_config import PROJECT_CONFIG
from experiments.e1_new_device.e1_config import DEVICES_HOURLY_FILE, E1Config
from experiments.e1_new_device.e1_evaluation import (
    candidate_cutover_times,
    select_cutover,
    summarize_cutover_windows,
)
from src.common.column_naming import quality_column
from src.pipeline.io import df_to_csv

logger = logging.getLogger(__name__)


def run(e1_config: E1Config) -> None:
    output_directory = PROJECT_CONFIG.e1_output_dir / e1_config.device_selection_subdir

    context = load_nilmtk_context(e1_config.split)

    logger.info(
        "Ranking all appliance channels over %s to %s...",
        context.window_start,
        context.window_end,
    )

    selection = select_appliance_channels(
        context, context.window_start, context.window_end
    )
    device_meter_key = selection.ranking["meter_key"].iloc[0]

    windows = summarize_cutover_windows(
        selection.data_hourly[device_meter_key],
        selection.quality_hourly[quality_column(device_meter_key, "coverage_mask")],
        context.mains,
        candidate_cutover_times(
            context.window_start, context.split_start, context.split_end, e1_config
        ),
        e1_config.margin_after_days,
    )
    windows = select_cutover(windows, e1_config.min_device_coverage)

    output_directory.mkdir(parents=True, exist_ok=True)
    df_to_csv(selection.ranking, output_directory, "e1_device_ranking")
    df_to_csv(windows, output_directory, "e1_cutover_windows")
    # alle Kanäle, damit E1 auch ein anderes Gerät aus dem Ranking nehmen kann
    df_to_csv(
        selection.data_hourly.reset_index(), output_directory, DEVICES_HOURLY_FILE
    )

    selected = windows.loc[windows["selected"]].iloc[0]
    logger.info(
        "Largest share: %s, largest share after cutover %s (%.1f %%), see %s.",
        device_meter_key,
        selected["cutover_date"],
        selected["device_share"] * 100,
        output_directory,
    )


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    run(E1Config())


if __name__ == "__main__":
    main()
