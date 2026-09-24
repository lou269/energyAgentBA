# conda run -n nilmtk-env python -m experiments.proposal_experiments.e1_new_device.e1_device_check


from __future__ import annotations

import logging

import pandas as pd

from experiments.proposal_experiments.e_config import E1Config
from experiments.proposal_experiments.shared_nilmtk import (
    load_nilmtk_context,
    load_treated_mains_series,
)
from src.common.column_naming import quality_column
from src.common.timestamps import local_calendar_range, local_day, shift_local_days
from src.config.config_forecasting import ForecastingConfig
from src.config.config_nilmtk import AnalysisConfig, DataPreparationConfig
from src.config.project_config import ProjectConfig
from src.data_preparation.auxiliary_appliance_selection import (
    build_auxiliary_appliance_selection,
)
from src.pipeline.io import df_to_csv

logger = logging.getLogger(__name__)


def candidate_cutover_times(
    window_start: pd.Timestamp,
    window_end: pd.Timestamp,
    *,
    lead_days: int,
    margin_after_days: int,
    step_days: int,
    local_timezone: str,
) -> pd.DatetimeIndex:
    # +1, falls das Fenster nicht auf lokaler Mitternacht beginnt
    first = shift_local_days(
        local_day(window_start, local_timezone), lead_days + 1, local_timezone
    )
    last = shift_local_days(
        local_day(window_end, local_timezone), -margin_after_days, local_timezone
    )

    return local_calendar_range(first, step_days, last, local_timezone)


def summarize_cutover_windows(
    device_hourly: pd.Series,
    coverage_mask: pd.Series,
    mains_hourly: pd.Series,
    cutover_times: pd.DatetimeIndex,
    *,
    window_days: int,
    local_timezone: str,
) -> pd.DataFrame:
    rows = []

    for cutover_time in cutover_times:
        window = slice(
            cutover_time,
            shift_local_days(cutover_time, window_days, local_timezone)
            - pd.Timedelta(hours=1),
        )
        rows.append(
            {
                "cutover_date": cutover_time.tz_convert(local_timezone)
                .date()
                .isoformat(),
                "device_mean_w": device_hourly.loc[window].mean(),
                # wie activity_share im Ranking, nur auf das Fenster nach dem Cutover beschränkt
                "device_share": device_hourly.loc[window].sum()
                / mains_hourly.loc[window].sum(),
                "device_coverage": coverage_mask.loc[window].mean(),
            }
        )

    return pd.DataFrame(rows)


def select_cutover(windows: pd.DataFrame, min_device_coverage: float) -> pd.DataFrame:
    # bei Lücken im Gerätekanal wäre der Anteil zu niedrig und das Herausrechnen vor dem Cutover unvollständig
    covered = windows.loc[windows["device_coverage"] >= min_device_coverage]

    return windows.assign(selected=windows.index == covered["device_share"].idxmax())


class DeviceCheckRunner:
    def __init__(
        self,
        project_config: ProjectConfig | None = None,
        data_config: DataPreparationConfig | None = None,
        analysis_config: AnalysisConfig | None = None,
        e1_config: E1Config | None = None,
        forecast_config: ForecastingConfig | None = None,
    ) -> None:
        self.project_config = project_config or ProjectConfig()
        self.data_config = data_config or DataPreparationConfig()
        self.analysis_config = analysis_config or AnalysisConfig()
        self.e1_config = e1_config or E1Config()
        self.forecast_config = forecast_config or ForecastingConfig()

    def run(self) -> None:
        local_timezone = self.project_config.timezone
        output_directory = (
            self.project_config.e1_output_dir / self.e1_config.device_selection_subdir
        )

        context = load_nilmtk_context(self.project_config)
        mains_data = load_treated_mains_series(
            self.project_config, context.mains_meter_key
        )

        logger.info(
            "Ranking all appliance channels over %s to %s...",
            context.window_start,
            context.window_end,
        )

        selection = build_auxiliary_appliance_selection(
            context.dataset,
            context.channel_registry,
            context.channel_quality,
            mains_data,
            house=context.house,
            window_start=context.window_start,
            window_end=context.window_end,
            canonical_ac_type=self.data_config.canonical_ac_type,
            min_coverage_share=self.data_config.min_coverage_share,
            min_sampling_share=self.analysis_config.min_auxiliary_window_coverage_share,
        )
        device_meter_key = selection.ranking["meter_key"].iloc[0]

        # vor dem ersten Cutover braucht E1 den Kaltstart und die Tage vor dem Cutover
        cutover_times = candidate_cutover_times(
            context.window_start,
            context.window_end,
            lead_days=self.forecast_config.cycle_coldstart_days
            + self.e1_config.margin_before_days
            + 1,
            margin_after_days=self.e1_config.margin_after_days,
            step_days=self.e1_config.cutover_step_days,
            local_timezone=local_timezone,
        )
        windows = summarize_cutover_windows(
            selection.data_hourly[device_meter_key],
            selection.quality_hourly[quality_column(device_meter_key, "coverage_mask")],
            mains_data,
            cutover_times,
            window_days=self.e1_config.margin_after_days,
            local_timezone=local_timezone,
        )
        windows = select_cutover(windows, self.e1_config.min_device_coverage)

        output_directory.mkdir(parents=True, exist_ok=True)
        df_to_csv(selection.ranking, output_directory, "e1_device_ranking")
        df_to_csv(windows, output_directory, "e1_cutover_windows")
        # alle Kanäle, damit E1 auch ein anderes Gerät aus dem Ranking nehmen kann
        df_to_csv(
            selection.data_hourly.reset_index(), output_directory, "e1_devices_hourly"
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
    DeviceCheckRunner().run()


if __name__ == "__main__":
    main()
