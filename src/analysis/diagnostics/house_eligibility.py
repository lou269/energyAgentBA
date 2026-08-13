from __future__ import annotations

import pandas as pd


MERGE_KEYS = [
    "house",
    "meter_instance",
    "meter_key",
]

HOUSE_ELIGIBILITY_COLUMNS = [
    "house",
    "mains_instance",
    "eligible_for_candidate_profiling",
    "exclusion_reason",
]


def build_house_eligibility(
    channel_registry: pd.DataFrame,
    channel_quality: pd.DataFrame,
    min_valid_sample_count: int,
) -> pd.DataFrame:
    _validate_inputs(
        channel_registry,
        channel_quality,
        min_valid_sample_count,
    )

    mains = channel_registry.loc[
        channel_registry["meter_type"].eq("mains"),
        MERGE_KEYS + ["has_canonical_ac_type"],
    ].copy()

    quality = channel_quality[
        MERGE_KEYS
        + [
            "valid_sample_count",
            "good_section_count",
            "quality_error",
        ]
    ].copy()

    mains = mains.merge(
        quality,
        on=MERGE_KEYS,
        how="left",
        validate="one_to_one",
    )

    rows = []

    house_ids = (
        channel_registry["house"]
        .dropna()
        .astype(int)
        .unique()
        .tolist()
    )

    for house_id in sorted(house_ids):
        house_mains = mains.loc[
            mains["house"].eq(house_id)
            & mains["has_canonical_ac_type"].fillna(False)
        ]

        if house_mains.empty:
            rows.append(
                {
                    "house": house_id,
                    "mains_instance": None,
                    "eligible_for_candidate_profiling": False,
                    "exclusion_reason": "no_canonical_mains",
                }
            )
            continue

        if len(house_mains) > 1:
            raise ValueError(
                f"House {house_id} has more than one mains channel."
            )

        mains_row = house_mains.iloc[0]

        usable = (
            not pd.isna(mains_row["valid_sample_count"])
            and mains_row["valid_sample_count"] >= min_valid_sample_count
            and not pd.isna(mains_row["good_section_count"])
            and mains_row["good_section_count"] >= 1
            and (
                pd.isna(mains_row["quality_error"])
                or str(mains_row["quality_error"]).strip() == ""
            )
        )


        rows.append(
            {
                "house": house_id,
                "mains_instance": int(mains_row["meter_instance"]),
                "eligible_for_candidate_profiling": usable,
                "exclusion_reason": (
                    "" if usable else "mains_quality_insufficient"
                ),
            }
        )

    return pd.DataFrame(
        rows,
        columns=HOUSE_ELIGIBILITY_COLUMNS,
    ).sort_values("house").reset_index(drop=True)


def _validate_inputs(
    channel_registry: pd.DataFrame,
    channel_quality: pd.DataFrame,
    min_valid_sample_count: int,
) -> None:
    required_registry = {
        "house",
        "meter_instance",
        "meter_key",
        "meter_type",
        "has_canonical_ac_type",
    }

    required_quality = {
        "house",
        "meter_instance",
        "meter_key",
        "valid_sample_count",
        "good_section_count",
        "quality_error",
    }

    missing_registry = required_registry - set(channel_registry.columns)
    if missing_registry:
        raise ValueError(
            "Channel registry is missing columns: "
            + ", ".join(sorted(missing_registry))
        )

    missing_quality = required_quality - set(channel_quality.columns)
    if missing_quality:
        raise ValueError(
            "Channel quality is missing columns: "
            + ", ".join(sorted(missing_quality))
        )

    if min_valid_sample_count < 2:
        raise ValueError(
            "min_valid_sample_count must be at least 2."
        )