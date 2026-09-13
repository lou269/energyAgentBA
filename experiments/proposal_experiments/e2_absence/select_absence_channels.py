# conda run -n nilmtk-env python -m experiments.proposal_experiments.e2_absence.select_absence_channels


from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd
from nilmtk import DataSet

from experiments.proposal_experiments.e2_absence.e2_config import ACTIVE_ABSENCE_EVENT_ID, CALENDAR_EVENTS_FILE
from experiments.proposal_experiments.e2_absence.e2_selection import channels_meeting_thresholds, load_calendar_events, resolve_absence_window
from src.common.channel_tables import load_channel_tables
from src.common.column_naming import treated_column
from src.config.config_nilmtk import AnalysisConfig, DataPreparationConfig
from src.config.project_config import ProjectConfig
from src.data_preparation.auxiliary_appliance_selection import build_auxiliary_appliance_selection
from src.pipeline.io import df_to_csv

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path(__file__).parent / "output"


def main() -> None:
    logging.basicConfig(level=logging.INFO)

    project_config = ProjectConfig()
    data_config = DataPreparationConfig()
    analysis_config = AnalysisConfig()
    house = data_config.selected_house_ids[0]

    dataset = DataSet(project_config.dataset_path)
    channel_registry, channel_quality = load_channel_tables(project_config)

    canonical_manifest = pd.read_csv(project_config.canonical_output_dir / "canonical_manifest.csv")
    target_column = treated_column(str(canonical_manifest.iloc[0]["meter_key"]))
    treated_hourly = pd.read_csv(
        project_config.preprocessing_output_dir / "treated_hourly.csv", parse_dates=["timestamp"], index_col="timestamp"
    )
    mains_data = treated_hourly[target_column]

    calendar_events = load_calendar_events(CALENDAR_EVENTS_FILE)
    window_start, window_end = resolve_absence_window(calendar_events, ACTIVE_ABSENCE_EVENT_ID)

    logger.info("Selecting auxiliary appliance channels for house %d, window %s to %s...", house, window_start, window_end)

    selection = build_auxiliary_appliance_selection(
        dataset,
        channel_registry,
        channel_quality,
        mains_data,
        house=house,
        window_start=window_start,
        window_end=window_end,
        canonical_ac_type=data_config.canonical_ac_type,
        min_coverage_share=data_config.min_coverage_share,
        min_sampling_share=analysis_config.min_auxiliary_window_coverage_share,
    )

    ranking = selection.ranking.copy()
    ranking["is_selected"] = channels_meeting_thresholds(ranking)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    df_to_csv(ranking, OUTPUT_DIR, "absence_channel_ranking")
    df_to_csv(selection.data_hourly.reset_index(), OUTPUT_DIR, "absence_channel_data_hourly")

    logger.info( "Done: %d ranked candidate(s), see %s.", len(selection.ranking), OUTPUT_DIR / "absence_channel_ranking.csv")



if __name__ == "__main__":
    main()

