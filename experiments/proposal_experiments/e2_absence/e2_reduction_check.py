# conda run -n forecasting-env python -m experiments.proposal_experiments.e2_absence.e2_reduction_check
# Diagnose fuer das E2-Nichtergebnis: wie stark senkt subtract_channels_in_window mains ueberhaupt,
# pro Tag im Abwesenheitsfenster - unabhaengig von Anomalie-Schwellen.


import logging
from pathlib import Path

import pandas as pd

from experiments.proposal_experiments.e_config import E2Config
from experiments.proposal_experiments.e2_absence.e2_selection import (
    load_calendar_events,
    resolve_absence_window,
    select_channels_for_subtraction,
)
from experiments.proposal_experiments.shared import subtract_channels_in_window
from src.common.target_series import load_target_series
from src.common.timestamps import local_day_index
from src.config.project_config import ProjectConfig
from src.pipeline.io import df_to_csv

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path(__file__).parent / "output"


class AbsenceReductionCheckRunner:
    def __init__(
        self,
        project_config: ProjectConfig | None = None,
        e2_config: E2Config | None = None,
    ) -> None:
        self.project_config = project_config or ProjectConfig()
        self.e2_config = e2_config or E2Config()

    def run(self) -> None:
        mains_series, _target_imputed, _target_value_implausible, _meter_key = (
            load_target_series(self.project_config)
        )

        calendar_events = load_calendar_events(
            self.e2_config.calendar_events_file, self.project_config.timezone
        )
        window_start, window_end = resolve_absence_window(
            calendar_events, self.e2_config.active_absence_event_id
        )

        ranking = pd.read_csv(OUTPUT_DIR / "absence_channel_ranking.csv")
        appliance_data_hourly = pd.read_csv(
            OUTPUT_DIR / "absence_channel_data_hourly.csv",
            parse_dates=["timestamp"],
            index_col="timestamp",
        )
        selected_channels = select_channels_for_subtraction(
            ranking,
            min_coverage_share=self.e2_config.min_coverage_share_for_subtraction,
        )

        absence_adjusted_series = subtract_channels_in_window(
            mains_series,
            appliance_data_hourly,
            selected_channels,
            window_start=window_start,
            window_end=window_end,
        )
        window_mask = (mains_series.index >= window_start) & (
            mains_series.index < window_end
        )
        raw_window = mains_series.loc[window_mask]
        adjusted_window = absence_adjusted_series.loc[window_mask]

        local_day = local_day_index(raw_window.index, self.project_config.timezone).date

        comparison = pd.DataFrame(
            {
                "mains_before_w": raw_window.groupby(local_day).mean(),
                "mains_after_w": adjusted_window.groupby(local_day).mean(),
            }
        )
        comparison.index.name = "date"
        comparison["reduction_w"] = (
            comparison["mains_before_w"] - comparison["mains_after_w"]
        )
        comparison = comparison.reset_index()

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        df_to_csv(comparison, OUTPUT_DIR, "e2_reduction_by_day")

        logger.info(
            "Done: %d day(s), see %s.",
            len(comparison),
            OUTPUT_DIR / "e2_reduction_by_day.csv",
        )


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    AbsenceReductionCheckRunner().run()


if __name__ == "__main__":
    main()
