from __future__ import annotations

import pandas as pd
from nilmtk import TimeFrame
from nilmtk.timeframegroup import TimeFrameGroup


SECONDS_PER_DAY = 86_400.0
MERGE_KEYS = ["house", "meter_instance", "meter_key"]


AUXILIARY_SELECTION_COLUMNS = [
    "selection_role",
    "candidate_id",
    "house",
    "meter_instance",
    "meter_key",
    "appliance",
    "sampling_share",
    "good_section_coverage_share",
    "longest_good_section_days",
    "selected_window_coverage_share",
    "longest_selected_window_overlap_days",
    "balance",
    "explanation",
    "experiment",
]


def build_auxiliary_appliance_selection(
    candidate_profiles: pd.DataFrame,
    provisional_selection: pd.DataFrame,
    channel_registry: pd.DataFrame,
    channel_quality: pd.DataFrame,
    good_sections: pd.DataFrame,
    min_window_coverage_share: float,
    max_balance_channels: int,
    max_explanation_channels: int,
) -> pd.DataFrame:
    
    _validate_inputs(
        candidate_profiles,
        provisional_selection,
        channel_registry,
        channel_quality,
        good_sections,
        min_window_coverage_share,
        max_balance_channels,
        max_explanation_channels,
    )

    candidates = provisional_selection.merge(
        candidate_profiles[
            [
                "candidate_id",
                "house",
                "longest_segment_start",
                "longest_segment_end",
            ]
        ],
        on="candidate_id",
        how="inner",
        validate="one_to_one",
    )

    appliances = (
        channel_registry.loc[
            channel_registry["meter_type"].eq("submeter"),
            MERGE_KEYS + ["appliances"],
        ]
        .merge(
            channel_quality[
                MERGE_KEYS
                + [
                    "sampling_share",
                    "good_section_count",
                    "good_section_coverage_share",
                    "longest_good_section_days",
                    "quality_error",
                ]
            ],
            on=MERGE_KEYS,
            how="inner",
            validate="one_to_one",
        )
    )

    appliances["appliances"] = (
        appliances["appliances"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    appliances = appliances.loc[
        appliances["appliances"].ne("")
        & appliances["quality_error"]
        .fillna("")
        .astype(str)
        .str.strip()
        .eq("")
        & (
            pd.to_numeric(
                appliances["good_section_count"],
                errors="coerce",
            )
            >= 1
        )
    ]

    sections_by_channel = _build_section_index(
        good_sections
    )

    rows = []

    for candidate in candidates.itertuples(index=False):
        window_start = pd.to_datetime(
            candidate.longest_segment_start,
            utc=True,
        )

        window_end = pd.to_datetime(
            candidate.longest_segment_end,
            utc=True,
        )

        if window_end <= window_start:
            continue

        window = TimeFrameGroup(
            [
                TimeFrame(
                    start=window_start,
                    end=window_end,
                )
            ]
        )

        candidate_rows = []

        house_appliances = appliances.loc[
            appliances["house"].eq(candidate.house)
        ]

        for appliance in house_appliances.itertuples(index=False):
            key = (
                appliance.house,
                appliance.meter_instance,
                appliance.meter_key,
            )

            sections = sections_by_channel.get(key)

            if sections is None or len(sections) == 0:
                continue

            overlap = sections.intersection(window)

            if len(overlap) == 0:
                continue

            coverage_share = (
                overlap.uptime().total_seconds()
                / (window_end - window_start).total_seconds()
            )

            if coverage_share < min_window_coverage_share:
                continue

            longest_overlap = max(
                overlap,
                key=lambda section: section.timedelta,
            )

            candidate_rows.append(
                {
                    "selection_role": candidate.selection_role,
                    "candidate_id": candidate.candidate_id,
                    "house": candidate.house,
                    "meter_instance": int(appliance.meter_instance),
                    "meter_key": str(appliance.meter_key),
                    "appliance": appliance.appliances,
                    "sampling_share": appliance.sampling_share,
                    "good_section_coverage_share": appliance.good_section_coverage_share,
                    "longest_good_section_days": appliance.longest_good_section_days,
                    "selected_window_coverage_share": coverage_share,
                    "longest_selected_window_overlap_days": (
                        longest_overlap.timedelta.total_seconds()
                        / SECONDS_PER_DAY
                    ),
                }
            )

        if not candidate_rows:
            continue

        ranked = pd.DataFrame(candidate_rows).sort_values(
            by=[
                "selected_window_coverage_share",
                "longest_selected_window_overlap_days",
                "sampling_share",
                "good_section_coverage_share",
                "longest_good_section_days",
                "meter_instance",
            ],
            ascending=[
                False,
                False,
                False,
                False,
                False,
                True,
            ],
            na_position="last",
            kind="mergesort",
        ).reset_index(drop=True)

        balance_count = min(max_balance_channels, len(ranked))
        explanation_count = min(max_explanation_channels, balance_count)

        ranked["balance"] = False
        ranked["explanation"] = False
        ranked["experiment"] = False

        ranked.loc[
            ranked.index[:balance_count],
            "balance",
        ] = True

        ranked.loc[
            ranked.index[:explanation_count],
            "explanation",
        ] = True

        if balance_count:
            ranked.loc[0, "experiment"] = True

        rows.extend(ranked.to_dict(orient="records"))

    result = pd.DataFrame(
        rows,
        columns=AUXILIARY_SELECTION_COLUMNS,
    )

    if result.empty:
        return result

    return result.sort_values(
        [
            "selection_role",
            "candidate_id",
            "balance",
            "explanation",
            "experiment",
            "meter_instance",
        ],
        ascending=[
            True,
            True,
            False,
            False,
            False,
            True,
        ],
        kind="mergesort",
    ).reset_index(drop=True)


def _build_section_index(
    good_sections: pd.DataFrame,
) -> dict:
    """Übersetzt Good Sections einmal pro Kanal in NILMTK TimeFrameGroups."""
    result = {}

    for key, rows in good_sections.groupby(
        MERGE_KEYS,
        sort=False,
    ):
        timeframes = []

        for row in rows.itertuples(index=False):
            if pd.isna(row.start) or pd.isna(row.end):
                continue

            start = pd.to_datetime(str(row.start), utc=True)
            end = pd.to_datetime(str(row.end), utc=True)

            if end > start:
                timeframes.append(
                    TimeFrame(start=start, end=end)
                )

        result[key] = TimeFrameGroup(timeframes)

    return result


def _validate_inputs(
    candidate_profiles: pd.DataFrame,
    provisional_selection: pd.DataFrame,
    channel_registry: pd.DataFrame,
    channel_quality: pd.DataFrame,
    good_sections: pd.DataFrame,
    min_window_coverage_share: float,
    max_balance_channels: int,
    max_explanation_channels: int,
) -> None:
    required_columns = {
        "candidate_profiles": (
            candidate_profiles,
            {
                "candidate_id",
                "house",
                "longest_segment_start",
                "longest_segment_end",
            },
        ),
        "provisional_selection": (
            provisional_selection,
            {"selection_role", "candidate_id"},
        ),
        "channel_registry": (
            channel_registry,
            {
                "house",
                "meter_instance",
                "meter_key",
                "meter_type",
                "appliances",
            },
        ),
        "channel_quality": (
            channel_quality,
            {
                "house",
                "meter_instance",
                "meter_key",
                "sampling_share",
                "good_section_count",
                "good_section_coverage_share",
                "longest_good_section_days",
                "quality_error",
            },
        ),
        "good_sections": (
            good_sections,
            {
                "house",
                "meter_instance",
                "meter_key",
                "start",
                "end",
            },
        ),
    }

    for name, (frame, columns) in required_columns.items():
        missing = columns.difference(frame.columns)
        if missing:
            raise ValueError(
                f"{name} is missing required columns: "
                + ", ".join(sorted(missing))
            )

    if not 0.0 <= min_window_coverage_share <= 1.0:
        raise ValueError(
            "min_window_coverage_share must be between 0 and 1."
        )

    if max_balance_channels <= 0:
        raise ValueError(
            "max_balance_channels must be greater than 0."
        )

    if max_explanation_channels <= 0:
        raise ValueError(
            "max_explanation_channels must be greater than 0."
        )