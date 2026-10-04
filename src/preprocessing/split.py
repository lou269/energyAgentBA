import pandas as pd

from src.common.timestamps import local_day_index
from src.common.windows import window_splits


def split_index(
    index: pd.DatetimeIndex, window: str, split: str, local_timezone: str
) -> pd.DatetimeIndex:
    local_days = local_day_index(index, local_timezone)
    day_number = pd.Index(local_days.unique()).get_indexer(local_days)

    bounds = {}
    first_day = 0

    for name, days in window_splits(window).items():
        last_day = day_number.max() + 1 if days is None else first_day + days
        bounds[name] = (first_day, last_day)
        first_day = last_day

    first_day, last_day = bounds[split]

    return index[(day_number >= first_day) & (day_number < last_day)]


def build_split_manifest(
    window: str, index: pd.DatetimeIndex, local_timezone: str
) -> pd.DataFrame:
    rows = []

    for split in window_splits(window):
        part = split_index(index, window, split, local_timezone)
        rows.append(
            {
                "window": window,
                "split": split,
                "start": part.min(),
                "end": part.max(),
                "days": local_day_index(part, local_timezone).nunique(),
                "row_count": len(part),
            }
        )

    return pd.DataFrame(rows)
