from __future__ import annotations

import pandas as pd

from src.common.gap_masking import short_gap_mask

CANDIDATE_AVAILABILITY_COLUMNS = [
    "meter_key",
    "start",
    "end",
    "length_days",
    "coverage_share",
]


def build_candidate_availability(
    data: pd.DataFrame,
    quality: pd.DataFrame,
    max_gap_intervals: int,
) -> pd.DataFrame:
    _validate_inputs(data, quality, max_gap_intervals=max_gap_intervals)

    interval_hours = (data.index[1] - data.index[0]).total_seconds() / 3600

    rows: list[dict] = []

    for meter_key in data.columns:
        coverage_mask = quality[f"{meter_key}_coverage_mask"].fillna(False).astype(bool)
        rows.extend(_span_rows(meter_key, coverage_mask, max_gap_intervals, interval_hours))

    return pd.DataFrame(rows, columns=CANDIDATE_AVAILABILITY_COLUMNS)


def _span_rows(
    meter_key: str,
    coverage_mask: pd.Series,
    max_gap_intervals: int,
    interval_hours: float,
) -> list[dict]:
    missing = ~coverage_mask
    bridgeable_gap = short_gap_mask(missing, max_gap_intervals)
    usable = coverage_mask | bridgeable_gap

    span_ids = usable.ne(usable.shift(fill_value=False)).cumsum()

    rows = []

    for _, span in usable[usable].groupby(span_ids[usable]):
        span_index = span.index
        rows.append(
            {
                "meter_key": meter_key,
                "start": span_index[0],
                "end": span_index[-1],
                "length_days": len(span_index) * interval_hours / 24.0,
                "coverage_share": coverage_mask.loc[span_index].mean(),
            }
        )

    return rows


def _validate_inputs(
    data: pd.DataFrame,
    quality: pd.DataFrame,
    *,
    max_gap_intervals: int,
) -> None:
    if isinstance(max_gap_intervals, bool) or not isinstance(max_gap_intervals, int) or max_gap_intervals < 0:
        raise ValueError("max_gap_intervals must be a non-negative integer.")

    if data.empty or len(data.index) < 2:
        raise ValueError("data must contain at least two rows to infer the grid interval.")

    if not data.index.equals(quality.index):
        raise ValueError("data and quality must use the same index.")

    missing_quality_columns = {f"{column}_coverage_mask" for column in data.columns}.difference(
        quality.columns
    )

    if missing_quality_columns:
        raise ValueError("Missing quality columns: " + ", ".join(sorted(missing_quality_columns)))