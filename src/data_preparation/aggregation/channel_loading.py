from __future__ import annotations

import pandas as pd
from nilmtk import DataSet, TimeFrame

from src.common.channel_tables import MERGE_KEYS
from src.common.validation import require_columns

REQUIRED_QUALITY_COLUMNS = MERGE_KEYS + ["is_mains", "start", "end"]


def build_loaded_channels(
    dataset: DataSet,
    channel_quality: pd.DataFrame,
    canonical_ac_type: str,
    *,
    mains_only: bool,
    selected_house_ids: list[int] | None = None,
    include_meter_keys: set[str] | None = None,
    window_start: pd.Timestamp | None = None,
    window_end: pd.Timestamp | None = None,
) -> dict[str, pd.Series]:
    """Lädt jeden Kanal roh im eigenen Fenster; Merge zu einem DataFrame passiert erst nach dem Resampling in aggregation.py.

    include_meter_keys/window_start/window_end für auxiliary_appliance_selection.py
    """
    require_columns(channel_quality, REQUIRED_QUALITY_COLUMNS, "channel_quality")

    if (window_start is None) != (window_end is None):
        raise ValueError("window_start and window_end must be given together.")

    eligible = channel_quality.dropna(subset=["start", "end"])

    if selected_house_ids is not None:
        eligible = eligible.loc[eligible["house"].isin(selected_house_ids)]

    if mains_only:
        eligible = eligible.loc[eligible["is_mains"]]

    if include_meter_keys is not None:
        eligible = eligible.loc[eligible["meter_key"].isin(include_meter_keys)]

    channel_data: dict[str, pd.Series] = {}

    for row in eligible.to_dict(orient="records"):
        house = int(row["house"])
        meter_instance = int(row["meter_instance"])

        if window_start is not None and window_end is not None:
            start, end = window_start, window_end
        else:
            start = pd.to_datetime(row["start"], utc=True)
            end = pd.to_datetime(row["end"], utc=True)

        meter = dataset.buildings[house].elec[meter_instance]

        kwargs = {
            "sections": [TimeFrame(start=start, end=end)],
            "ac_type": canonical_ac_type,
            "resample": False,
        }

        loaded = meter.power_series_all_data(**kwargs)

        if loaded is None:
            loaded = pd.Series(dtype="float64", index=pd.DatetimeIndex([], tz="UTC"))
        else:
            loaded = loaded.copy()
            loaded.index = loaded.index.tz_convert("UTC")

        loaded.index.name = "timestamp"
        channel_data[str(row["meter_key"])] = loaded

    return channel_data
