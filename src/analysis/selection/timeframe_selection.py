from __future__ import annotations

import logging

import pandas as pd

logger = logging.getLogger(__name__)

SECONDS_PER_DAY = 86_400.0


def select_common_timeframe(
    selected_channels: pd.DataFrame,
    min_overlap_days: int = 180,
) -> pd.DataFrame:
    required_columns = [
        "house",
        "meter_instance",
        "start",
        "end",
    ]

    missing_columns = [
        column
        for column in required_columns
        if column not in selected_channels.columns
    ]

    if missing_columns:
        raise ValueError(
            "Missing columns in selected_channels: "
            f"{missing_columns}" 
        )

    if selected_channels.empty:
        logger.warning(
            "Cannot calculate timeframe because no channels "
            "were selected."
        )

        return pd.DataFrame(
            columns=[
                "house",
                "common_start",
                "common_end",
                "common_overlap_days",
                "selected_channel_count",
                "meets_min_overlap",
            ]
        )

    channels = selected_channels.copy()

    channels["start"] = pd.to_datetime(channels["start"], utc=True, errors="coerce")
    channels["end"] = pd.to_datetime(channels["end"], utc=True, errors="coerce")

    valid_mask = (
        channels["start"].notna()
        & channels["end"].notna()
        & channels["end"].gt(channels["start"])
    )

    channels = channels.loc[
        valid_mask,
        :,
    ].copy()

    if channels.empty:
        logger.warning(
            "No selected channels have a valid timeframe."
        )

        return pd.DataFrame(
            columns=[
                "house",
                "common_start",
                "common_end",
                "common_overlap_days",
                "selected_channel_count",
                "meets_min_overlap",
            ]
        )

    rows: list[dict[str, object]] = []

    for house_id, group in channels.groupby("house"):
        common_start = group["start"].max()
        common_end = group["end"].min()

        duration_seconds = max(
            (
                common_end - common_start
            ).total_seconds(),
            0.0,
        )

        overlap_days = (
            duration_seconds
            / SECONDS_PER_DAY
        )

        meets_min_overlap = (
            overlap_days >= min_overlap_days
        )

        if not meets_min_overlap:
            logger.warning(
                "Common overlap for house %s is only %.2f days. "
                "Required minimum: %s days.",
                house_id,
                overlap_days,
                min_overlap_days,
            )

        rows.append(
            {
                "house": house_id,
                "common_start": common_start,
                "common_end": common_end,
                "common_overlap_days": overlap_days,
                "selected_channel_count": len(group),
                "meets_min_overlap": meets_min_overlap,
            }
        )

    return pd.DataFrame(rows)