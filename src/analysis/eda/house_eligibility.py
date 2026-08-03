from __future__ import annotations
from typing import Any

import pandas as pd


def build_house_eligibility(
    channel_quality: pd.DataFrame,
    min_usable_channels: int,
) -> pd.DataFrame:
    """
    Bestimmt, welche Häuser grundsätzlich für das spätere
    Candidate Profiling geeignet sind.

    Ein Haus ist geeignet, wenn:

    1. mindestens ein Mains-Kanal mit dem kanonischen AC-Type existiert,
    2. alle zur Mains-Konfiguration gehörenden Kanäle nutzbar sind,
    3. mindestens die geforderte Anzahl nutzbarer Submeter existiert.
    """

    if min_usable_channels <= 0:
        raise ValueError("min_usable_channels must be greater than 0.")

    required_columns = [
        "house",
        "meter_instance",
        "meter_type",
        "has_canonical_ac_type",
        "usable_for_active_pipeline",
        "longest_good_section_days",
        "dropout_rate",
        "sampling_stable",
    ]

    missing_columns = [
        column
        for column in required_columns
        if column not in channel_quality.columns
    ]

    if missing_columns:
        raise ValueError(
            "Missing columns in channel_quality: "
            f"{missing_columns}"
        )

    rows: list[dict[str, object]] = []

    for house_id, house_channels in channel_quality.groupby(
        "house",
        sort=True,
    ):
        mains = house_channels.loc[house_channels["meter_type"].eq("mains")].copy()

        active_mains = mains.loc[
            mains["has_canonical_ac_type"]
            .fillna(False)
            .astype(bool)
        ].copy()

        usable_mains = active_mains.loc[
            active_mains["usable_for_active_pipeline"]
            .fillna(False)
            .astype(bool)
        ].copy()

        active_submeters = house_channels.loc[
            house_channels["meter_type"].eq("submeter")
            & house_channels["has_canonical_ac_type"]
            .fillna(False)
            .astype(bool)
        ].copy()

        usable_submeters = active_submeters.loc[
            active_submeters["usable_for_active_pipeline"]
            .fillna(False)
            .astype(bool)
        ].copy()

        mains_instances = sorted(
            active_mains["meter_instance"]
            .dropna()
            .astype(int)
            .tolist()
        )

        mains_configuration = ", ".join(
            str(instance)
            for instance in mains_instances
        )

        mains_count = len(mains)
        active_mains_count = len(active_mains)
        usable_mains_count = len(usable_mains)
        active_submeter_count = len(active_submeters)
        usable_submeter_count = len(usable_submeters)

        has_active_mains = active_mains_count > 0

        all_mains_usable = (
            has_active_mains
            and usable_mains_count == active_mains_count
        )

        has_sufficient_submeters = usable_submeter_count >= min_usable_channels

        exclusion_reasons: list[str] = []

        if not has_active_mains:
            exclusion_reasons.append("no_active_mains")
        elif not all_mains_usable:
            exclusion_reasons.append("mains_quality_insufficient")

        if not has_sufficient_submeters:
            exclusion_reasons.append("insufficient_usable_submeters")

        eligible_for_active_pipeline = (
            all_mains_usable
            and has_sufficient_submeters
        )

        rows.append(
            {
                "house": house_id,
                "mains_configuration": mains_configuration,
                "mains_count": mains_count,
                "active_mains_count": active_mains_count,
                "usable_mains_count": usable_mains_count,
                "has_active_mains": has_active_mains,
                "all_mains_usable": all_mains_usable,
                "active_submeter_count": active_submeter_count,
                "usable_submeter_count": usable_submeter_count,
                "has_sufficient_submeters": has_sufficient_submeters,
                "eligible_for_active_pipeline": eligible_for_active_pipeline,
                "exclusion_reasons": "|".join(exclusion_reasons),
            }
        )

    house_eligibility = pd.DataFrame(rows)

    if house_eligibility.empty:
        return house_eligibility

    return house_eligibility.sort_values(
        by="house"
    ).reset_index(drop=True)

