from __future__ import annotations

import pandas as pd



def short_gap_mask(missing: pd.Series, max_gap_intervals: int) -> pd.Series:
    gap_ids = missing.ne(missing.shift(fill_value=False)).cumsum()
    gap_lengths = missing.groupby(gap_ids).transform("sum")

    return missing & gap_lengths.le(max_gap_intervals)

