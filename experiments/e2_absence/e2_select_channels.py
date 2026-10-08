# conda activate nilmtk-env
# python -m experiments.e2_absence.e2_select_channels
# läuft in nilmtk-env, darf deshalb nichts aus forecasting/pipeline importieren

from __future__ import annotations

import logging

from experiments.common.nilmtk_channels import (
    load_nilmtk_context,
    select_appliance_channels,
)
from experiments.common.standard_config import PROJECT_CONFIG, STANDARD_CONFIG
from experiments.e2_absence.e2_config import (
    CHANNEL_DATA_FILE,
    CHANNEL_RANKING_FILE,
    E2Config,
)
from experiments.e2_absence.e2_selection import (
    channels_meeting_thresholds,
    load_calendar_events,
    resolve_absence_window,
)
from src.pipeline.io import df_to_csv

logger = logging.getLogger(__name__)


def run(e2_config: E2Config) -> None:
    context = load_nilmtk_context(STANDARD_CONFIG.split)
    calendar_events = load_calendar_events(e2_config.calendar_events_file)

    # je Urlaub getrennt, die Abdeckung der Kanäle hängt am Fenster
    for event_id in e2_config.absence_event_ids:
        output_directory = (
            PROJECT_CONFIG.e2_output_dir / e2_config.channel_selection_subdir(event_id)
        )
        window_start, window_end = resolve_absence_window(calendar_events, event_id)

        logger.info(
            "Selecting auxiliary appliance channels for house %d, %s from %s to %s...",
            context.house,
            event_id,
            window_start,
            window_end,
        )

        selection = select_appliance_channels(context, window_start, window_end)

        ranking = selection.ranking.copy()
        ranking["is_selected"] = channels_meeting_thresholds(
            ranking, min_coverage_share=e2_config.min_coverage_share_for_subtraction
        )

        output_directory.mkdir(parents=True, exist_ok=True)
        df_to_csv(ranking, output_directory, CHANNEL_RANKING_FILE)
        df_to_csv(
            selection.data_hourly.reset_index(), output_directory, CHANNEL_DATA_FILE
        )

        logger.info(
            "Done: %d ranked candidate(s), see %s.",
            len(selection.ranking),
            output_directory / f"{CHANNEL_RANKING_FILE}.csv",
        )


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    run(E2Config())


if __name__ == "__main__":
    main()
