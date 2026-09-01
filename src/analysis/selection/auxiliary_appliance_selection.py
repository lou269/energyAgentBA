from __future__ import annotations

import pandas as pd
from nilmtk import TimeFrame
from nilmtk.timeframegroup import TimeFrameGroup


SECONDS_PER_DAY = 86_400.0
MERGE_KEYS = ["house", "meter_instance", "meter_key"]


AUXILIARY_AVAILABILITY_COLUMNS = [
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
    "availability_rank",
]


def build_auxiliary_appliance_selection(
    candidate_profiles: pd.DataFrame,
    provisional_selection: pd.DataFrame,
    channel_registry: pd.DataFrame,
    channel_quality: pd.DataFrame,
    good_sections: pd.DataFrame,
) -> pd.DataFrame:
    """Ermittelt zeitlich verfügbare Geräte für ausgewählte Kandidaten.

    Die Rangfolge beschreibt ausschließlich die zeitliche Datenverfügbarkeit.
    Sie trifft keine Aussage über die Eignung eines Geräts für Bilanzierung,
    Erklärungen oder Experimente.
    """
    _validate_inputs(
        candidate_profiles,
        provisional_selection,
        channel_registry,
        channel_quality,
        good_sections,
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
        how="left",
        validate="one_to_one",
        indicator=True,
    )

    missing_candidates = candidates.loc[
        candidates["_merge"].ne("both"),
        "candidate_id",
    ].astype(str).tolist()

    if missing_candidates:
        raise ValueError(
            "Missing candidate profiles for provisional selection: "
            + ", ".join(missing_candidates)
        )

    candidates = candidates.drop(columns="_merge")

    appliances = channel_registry.loc[
        channel_registry["meter_type"].eq("submeter")
        & channel_registry["has_canonical_ac_type"]
        .fillna(False)
        .astype(bool),
        MERGE_KEYS + ["appliances"],
    ].merge(
        channel_quality[
            MERGE_KEYS
            + [
                "sampling_share",
                "good_section_coverage_share",
                "longest_good_section_days",
                "quality_error",
            ]
        ],
        on=MERGE_KEYS,
        how="left",
        validate="one_to_one",
        indicator=True,
    )

    missing_quality = appliances.loc[
        appliances["_merge"].ne("both"),
        MERGE_KEYS,
    ].to_dict(orient="records")

    if missing_quality:
        raise ValueError(
            "Missing channel quality for auxiliary channels: "
            f"{missing_quality}"
        )

    appliances = appliances.drop(columns="_merge")

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
    ]

    sections_by_channel = _build_section_index(good_sections)
    result_rows = []

    for candidate in candidates.itertuples(index=False):
        window_start = pd.to_datetime(
            candidate.longest_segment_start,
            utc=True,
        )
        window_end = pd.to_datetime(
            candidate.longest_segment_end,
            utc=True,
        )

        if (
            pd.isna(window_start)
            or pd.isna(window_end)
            or window_end <= window_start
        ):
            raise ValueError(
                f"Invalid selection window for {candidate.candidate_id}."
            )

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
            channel_key = (
                int(appliance.house),
                int(appliance.meter_instance),
                str(appliance.meter_key),
            )

            sections = sections_by_channel.get(channel_key)

            if sections is None or len(sections) == 0:
                continue

            overlap = sections.intersection(window)

            if len(overlap) == 0:
                continue

            coverage_share = (
                overlap.uptime().total_seconds()
                / (window_end - window_start).total_seconds()
            )
            
            if coverage_share <= 0.0:
                continue


            longest_overlap = max(
                overlap,
                key=lambda section: section.timedelta,
            )

            candidate_rows.append(
                {
                    "selection_role": candidate.selection_role,
                    "candidate_id": candidate.candidate_id,
                    "house": int(candidate.house),
                    "meter_instance": int(appliance.meter_instance),
                    "meter_key": str(appliance.meter_key),
                    "appliance": appliance.appliances,
                    "sampling_share": appliance.sampling_share,
                    "good_section_coverage_share": (
                        appliance.good_section_coverage_share
                    ),
                    "longest_good_section_days": (
                        appliance.longest_good_section_days
                    ),
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

        ranked["availability_rank"] = ranked.index + 1
        result_rows.extend(ranked.to_dict(orient="records"))

    result = pd.DataFrame(
        result_rows,
        columns=AUXILIARY_AVAILABILITY_COLUMNS,
    )

    if result.empty:
        return result

    return result.sort_values(
        [
            "selection_role",
            "candidate_id",
            "availability_rank",
        ],
        kind="mergesort",
    ).reset_index(drop=True)


def _build_section_index(
    good_sections: pd.DataFrame,
) -> dict[tuple[int, int, str], TimeFrameGroup]:
    """Übersetzt Good Sections einmal pro Kanal in TimeFrameGroups."""
    sections_by_channel: dict[
        tuple[int, int, str],
        TimeFrameGroup,
    ] = {}

    for _, rows in good_sections.groupby(
        MERGE_KEYS,
        sort=False,
    ):
        first_row = rows.iloc[0]

        channel_key = (
            int(first_row["house"]),
            int(first_row["meter_instance"]),
            str(first_row["meter_key"]),
        )

        timeframes: list[TimeFrame] = []

        for start_value, end_value in rows[
            ["start", "end"]
        ].itertuples(index=False, name=None):
            start = pd.to_datetime(
                str(start_value),
                utc=True,
                errors="coerce",
            )
            end = pd.to_datetime(
                str(end_value),
                utc=True,
                errors="coerce",
            )

            if pd.isna(start) or pd.isna(end) or end <= start:
                raise ValueError(
                    f"Invalid good section for channel {channel_key}."
                )

            timeframes.append(
                TimeFrame(
                    start=start,
                    end=end,
                )
            )

        sections_by_channel[channel_key] = TimeFrameGroup(
            timeframes
        )

    return sections_by_channel


def _validate_inputs(
    candidate_profiles: pd.DataFrame,
    provisional_selection: pd.DataFrame,
    channel_registry: pd.DataFrame,
    channel_quality: pd.DataFrame,
    good_sections: pd.DataFrame,
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
            {
                "selection_role",
                "candidate_id",
            },
        ),
        "channel_registry": (
            channel_registry,
            {
                "house",
                "meter_instance",
                "meter_key",
                "meter_type",
                "appliances",
                "has_canonical_ac_type",
            },
        ),
        "channel_quality": (
            channel_quality,
            {
                "house",
                "meter_instance",
                "meter_key",
                "sampling_share",
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
