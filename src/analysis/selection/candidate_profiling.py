from __future__ import annotations

import pandas as pd

from nilmtk import TimeFrame
from nilmtk.timeframegroup import TimeFrameGroup


SECONDS_PER_DAY = 86_400.0
MERGE_KEYS = ["house", "meter_instance", "meter_key"]

PROFILE_COLUMNS = [
    "candidate_id",
    "house",
    "mains_instance",
    "first_start",
    "last_end",
    "segment_count",
    "total_coverage_days",
    "longest_segment_start",
    "longest_segment_end",
    "longest_segment_days",
    "sampling_share",
    "calendar_months",
    "weekday_days",
    "weekend_days",
]


def build_candidate_profiles(
    channel_registry: pd.DataFrame,
    channel_quality: pd.DataFrame,
    house_eligibility: pd.DataFrame,
    good_sections: pd.DataFrame,
) -> pd.DataFrame:

    _validate_inputs(
        channel_registry,
        channel_quality,
        house_eligibility,
        good_sections,
    )

    mains_channels = (
        channel_registry.loc[
            channel_registry["meter_type"].eq("mains"),
            MERGE_KEYS,
        ]
        .merge(
            channel_quality[
                MERGE_KEYS + ["sampling_share"]
            ],
            on=MERGE_KEYS,
            how="inner",
            validate="one_to_one",
        )
    )

    eligible = house_eligibility.loc[
        house_eligibility[
            "eligible_for_candidate_profiling"
        ]
        .fillna(False)
        .astype(bool)
    ]

    profiles = []

    for candidate in eligible.itertuples(index=False):
        house = candidate.house
        mains_instance = int(candidate.mains_instance)

        mains = mains_channels.loc[
            mains_channels["house"].eq(house)
            & mains_channels["meter_instance"].eq(mains_instance)
        ]

        if mains.empty:
            continue

        meter = mains.iloc[0]

        section_rows = good_sections.loc[
            good_sections["house"].eq(house)
            & good_sections["meter_instance"].eq(mains_instance)
            & good_sections["meter_key"].eq(meter["meter_key"])
        ]

        timeframes = _to_timeframe_group(section_rows)

        if len(timeframes) == 0:
            continue

        sections = list(timeframes)
        longest = max(
            sections,
            key=lambda section: section.timedelta,
        )

        profiles.append(
            {
                "candidate_id": f"H{int(house)}-M{mains_instance}",
                "house": house,
                "mains_instance": mains_instance,
                "first_start": sections[0].start,
                "last_end": sections[-1].end,
                "segment_count": len(sections),
                "total_coverage_days": (timeframes.uptime().total_seconds() / SECONDS_PER_DAY),
                "longest_segment_start": longest.start,
                "longest_segment_end": longest.end,
                "longest_segment_days": (longest.timedelta.total_seconds() / SECONDS_PER_DAY),
                "sampling_share": meter["sampling_share"],
                **_calendar_metrics(sections),
            }
        )

    return (
        pd.DataFrame(
            profiles,
            columns=PROFILE_COLUMNS,
        )
        .sort_values(
            ["house", "mains_instance"],
            kind="mergesort",
        )
        .reset_index(drop=True)
    )


def _to_timeframe_group(
    sections: pd.DataFrame,
) -> TimeFrameGroup:
    """Konvertiert vorhandene Good Sections in NILMTK TimeFrames."""
    if sections.empty:
        return TimeFrameGroup([])

    starts = pd.to_datetime(sections["start"], utc=True, errors="coerce")
    ends = pd.to_datetime(sections["end"], utc=True, errors="coerce")

    timeframes = []

    for start, end in zip(starts, ends):
        if pd.isna(start) or pd.isna(end):
            continue

        if end > start:
            timeframes.append(
                TimeFrame(start=start, end=end)
            )

    return TimeFrameGroup(timeframes)


def _calendar_metrics(sections: list[TimeFrame]) -> dict:
    covered_days = set()

    for section in sections:
        start = section.start
        end = section.end

        if start is None or end is None:
            continue

        covered_days.update(
            pd.date_range(
                start.normalize(),
                end.normalize(),
                freq="D",
            )
        )

    days = pd.DatetimeIndex(sorted(covered_days))

    return {
        "calendar_months": ",".join(
            sorted(
                {
                    "{:04d}-{:02d}".format(
                        day.year,
                        day.month,
                    )
                    for day in days
                }
            )
        ),
        "weekday_days": int((days.dayofweek < 5).sum()),
        "weekend_days": int((days.dayofweek >= 5).sum())
    }

def _validate_inputs(
    channel_registry: pd.DataFrame,
    channel_quality: pd.DataFrame,
    house_eligibility: pd.DataFrame,
    good_sections: pd.DataFrame,
) -> None:
    required_columns = {
        "channel_registry": {"house", "meter_instance", "meter_key", "meter_type"},
        "channel_quality": {"house", "meter_instance", "meter_key", "sampling_share"},
        "house_eligibility": {"house", "mains_instance", "eligible_for_candidate_profiling"},
        "good_sections": {"house", "meter_instance", "meter_key", "start", "end"},
    }

    dataframes = {
        "channel_registry": channel_registry,
        "channel_quality": channel_quality,
        "house_eligibility": house_eligibility,
        "good_sections": good_sections,
    }

    for name, df in dataframes.items():
        missing = required_columns[name] - set(df.columns)

        if missing:
            raise ValueError(f"{name} is missing required columns: {sorted(missing)}")