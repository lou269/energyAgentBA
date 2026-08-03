from __future__ import annotations

import logging
from typing import Iterable

import pandas as pd

logger = logging.getLogger(__name__)

def build_channel_selection(
    channel_quality: pd.DataFrame,
    house_quality: pd.DataFrame,
    max_channels: int | None = None,
    excluded_appliances: Iterable[str] | None = None,
) -> pd.DataFrame:

    required_columns = [
        "house",
        "meter_instance",
        "meter_type",
        "appliances",
        "has_canonical_ac_type",
        "usable_for_active_pipeline",
        "start",
        "end",
        "duration_days",
        "sample_count",
        "good_duration_days",
        "longest_good_section_days",
        "dropout_rate",
    ]
    missing = [col for col in required_columns if col not in channel_quality.columns]
    if missing:
        raise ValueError(f"Missing columns in channel_quality: {missing}")

    channel_df = channel_quality.copy()
    
    required_house_columns = [
        "house",
        "eligible_for_active_pipeline",
    ]

    missing_house_columns = [column for column in required_house_columns if column not in house_quality.columns]

    if missing_house_columns:
        raise ValueError(f"Missing columns in house_quality: {missing_house_columns}")
        
        
    house_df = house_quality.copy()
    
    house_ids = (house_df.loc[house_df["eligible_for_active_pipeline"].astype(bool),"house"].tolist())

    if not house_ids:
        logger.warning(
            "No houses are eligible for the active pipeline."
        )
        return channel_df.iloc[0:0].copy()


    channel_df["start"] = pd.to_datetime(
        channel_df["start"],
        utc=True,
        errors="coerce",
    )

    channel_df["end"] = pd.to_datetime(
        channel_df["end"],
        utc=True,
        errors="coerce",
    )

    channel_df["appliances"] = (
        channel_df["appliances"]
        .fillna("")
        .astype(str)
        .str.strip()
    )


    house_channels = channel_df.loc[
        channel_df["house"].isin(house_ids)
        & channel_df["meter_type"].eq("submeter"),
        :,
    ].copy()


    for house_id, group in house_channels.groupby("house"):
        logger.info(
            "House %s: %s submeters, %s with canonical AC type, %s usable.",
            house_id,
            len(group),
            int(
                group["has_canonical_ac_type"]
                .fillna(False)
                .astype(bool)
                .sum()
            ),
            int(
                group["usable_for_active_pipeline"]
                .fillna(False)
                .astype(bool)
                .sum()
            ),
        )


    mask = (
        channel_df["house"].isin(house_ids)
        & channel_df["meter_type"].eq("submeter")
        & channel_df["has_canonical_ac_type"]
        .fillna(False)
        .astype(bool)
        & channel_df["usable_for_active_pipeline"]
        .fillna(False)
        .astype(bool)
        & channel_df["appliances"].ne("")
        & channel_df["start"].notna()
        & channel_df["end"].notna()
        & channel_df["end"].gt(channel_df["start"])
    )

    selected = channel_df.loc[mask].copy()

    if selected.empty:
        logger.warning(
            "No usable channels found for eligible houses: %s.",
            house_ids,
        )
        return selected.reset_index(drop=True)

    if excluded_appliances:
        excluded = [x.strip().lower() for x in excluded_appliances if x and x.strip()]
        if excluded:
            appliance_text = selected["appliances"].str.lower()
            exclude_mask = appliance_text.apply(
                lambda value: any(name in value for name in excluded)
            )
            selected = selected.loc[~exclude_mask].copy()

    if selected.empty:
        logger.warning("No channels left after appliance exclusion.")
        return selected.reset_index(drop=True)

    selected["appliance_key"] = (
        selected["appliances"]
        .str.lower()
        .str.replace(r"\s+", " ", regex=True)
        .str.strip()
    )

    selected = selected.sort_values(
        by=[
            "longest_good_section_days",
            "good_duration_days",
            "duration_days",
            "dropout_rate",
            "sample_count",
        ],
        ascending=[False, False, False, True, False],
        na_position="last",
    ).copy()

    selected = selected.drop_duplicates(
        subset=["house", "appliance_key"],
        keep="first",
    ).copy()

    selected = selected.drop(columns=["appliance_key"]).copy()
    
    if max_channels is not None:
        if max_channels <= 0:
            raise ValueError("max_channels must be greater than 0 or None.")

        selected = (
            selected.groupby("house", group_keys=False)
            .head(max_channels)
            .copy()
        )

    debug_columns = [
        "meter_instance",
        "appliances",
        "has_canonical_ac_type",
        "duration_days",
        "sample_count",
        "zero_share",
        "mean_power",
        "median_sample_period_seconds",
        "p99_sample_period_seconds",
        "longest_gap_seconds",
        "longest_good_section_days",
        "negative_share",
        "usable_for_active_pipeline",
    ]

    logger.info(
        "\n%s",
        house_channels[debug_columns].to_string(index=False),
    )

    selected = selected.reset_index(drop=True)

    return selected
