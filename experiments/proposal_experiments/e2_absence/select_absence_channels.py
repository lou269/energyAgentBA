# conda run -n nilmtk-env python -m experiments.proposal_experiments.e2_absence.select_absence_channels

from __future__ import annotations

import logging
from pathlib import Path

from experiments.proposal_experiments.config import E2Config
from experiments.proposal_experiments.e2_absence.e2_selection import channels_meeting_thresholds, load_calendar_events, resolve_absence_window
from experiments.proposal_experiments.shared_nilmtk import load_nilmtk_context, load_treated_mains_series
from src.config.config_nilmtk import AnalysisConfig, DataPreparationConfig
from src.config.project_config import ProjectConfig
from src.data_preparation.auxiliary_appliance_selection import build_auxiliary_appliance_selection
from src.pipeline.io import df_to_csv

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path(__file__).parent / "output"


class AbsenceChannelSelectionRunner:
    def __init__(
        self,
        project_config: ProjectConfig | None = None,
        data_config: DataPreparationConfig | None = None,
        analysis_config: AnalysisConfig | None = None,
        e2_config: E2Config | None = None,
    ) -> None:
        self.project_config = project_config or ProjectConfig()
        self.data_config = data_config or DataPreparationConfig()
        self.analysis_config = analysis_config or AnalysisConfig()
        self.e2_config = e2_config or E2Config()


    def run(self) -> None:
        context = load_nilmtk_context(self.project_config)
        mains_data = load_treated_mains_series(self.project_config, context.mains_meter_key)

        calendar_events = load_calendar_events(self.e2_config.calendar_events_file)
        window_start, window_end = resolve_absence_window(calendar_events, self.e2_config.active_absence_event_id)

        logger.info("Selecting auxiliary appliance channels for house %d, window %s to %s...", context.house, window_start, window_end)

        selection = build_auxiliary_appliance_selection(
            context.dataset,
            context.channel_registry,
            context.channel_quality,
            mains_data,
            house=context.house,
            window_start=window_start,
            window_end=window_end,
            canonical_ac_type=self.data_config.canonical_ac_type,
            min_coverage_share=self.data_config.min_coverage_share,
            min_sampling_share=self.analysis_config.min_auxiliary_window_coverage_share,
        )

        ranking = selection.ranking.copy()
        ranking["is_selected"] = channels_meeting_thresholds(ranking, min_coverage_share=self.e2_config.min_coverage_share_for_subtraction)

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        df_to_csv(ranking, OUTPUT_DIR, "absence_channel_ranking")
        df_to_csv(selection.data_hourly.reset_index(), OUTPUT_DIR, "absence_channel_data_hourly")

        logger.info("Done: %d ranked candidate(s), see %s.", len(selection.ranking), OUTPUT_DIR / "absence_channel_ranking.csv")


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    AbsenceChannelSelectionRunner().run()


if __name__ == "__main__":
    main()

