from __future__ import annotations

import logging
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, cast

import pandas as pd
from nilmtk.timeframe import TimeFrame
from nilmtk.timeframegroup import TimeFrameGroup

logger = logging.getLogger(__name__)

SECONDS_PER_DAY = 86_400.0

PROFILE_COLUMNS = [
    "candidate_id",
    "house",
    "mains_instances",
    "appliance_instances",
    "appliances",
    "candidate_start",
    "candidate_end",
    "candidate_duration_days",
    "meets_min_window",
    "meets_preferred_window",
    "mains_channel_count",
    "appliance_channel_count",
    "total_channel_count",
    "common_segment_count",
    "total_common_overlap_days",
    "longest_common_segment_days",
    "mean_channel_dropout_rate",
    "worst_channel_dropout_rate",
    "mean_channel_irregular_gap_share",
    "worst_channel_irregular_gap_share",
    "max_channel_longest_gap_seconds",
    "min_channel_good_section_coverage_share",
    "all_channels_sampling_stable",
    "calendar_month_count",
    "calendar_months",
    "weekday_days",
    "weekend_days",
    "weekday_share",
    "weekend_share",
]

CANDIDATE_CHANNEL_COLUMNS = [
    "candidate_id",
    "house",
    "candidate_start",
    "candidate_end",
    "meter_instance",
    "role",
    "appliances",
    "sample_count",
    "nominal_sample_period_seconds",
    "good_sections_count",
    "good_duration_days",
    "longest_good_section_days",
    "good_section_coverage_share",
    "dropout_rate",
    "irregular_gap_share",
    "longest_gap_seconds",
    "sampling_stable",
    "mean_power",
    "zero_share",
    "negative_share",
]

QUALITY_COLUMNS = [
    "house",
    "meter_instance",
    "meter_type",
    "appliances",
    "has_canonical_ac_type",
    "usable_for_active_pipeline",
    "sample_count",
    "nominal_sample_period_seconds",
    "good_sections_count",
    "good_duration_days",
    "longest_good_section_days",
    "good_section_coverage_share",
    "dropout_rate",
    "irregular_gap_share",
    "longest_gap_seconds",
    "sampling_stable",
    "mean_power",
    "zero_share",
    "negative_share",
]



def build_candidate_profiles(
    channel_quality: pd.DataFrame,
    house_eligibility: pd.DataFrame,
    good_sections: pd.DataFrame,
    min_window_days: int,
    preferred_window_days: int,
    max_channels: Optional[int] = None,
    min_appliance_channels: int = 1,
    excluded_appliances: Optional[Iterable[str]] = None,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Create pre-alignment profiles for nested appliance sets.

    One candidate is:
        house x mains configuration x appliance set x common good section

    Appliance sets are generated greedily. Channels are ranked once; the
    weakest appliance channel is removed in each iteration. This avoids the
    combinatorial generation of every possible subset.
    """

    _validate_inputs(
        channel_quality=channel_quality,
        house_eligibility=house_eligibility,
        good_sections=good_sections,
        min_window_days=min_window_days,
        preferred_window_days=preferred_window_days,
        max_channels=max_channels,
        min_appliance_channels=min_appliance_channels,
    )

    quality = _prepare_quality(channel_quality)
    sections = good_sections.copy()

    eligible_houses = house_eligibility.loc[
        house_eligibility["eligible_for_active_pipeline"]
        .fillna(False)
        .astype(bool),
        "house",
    ].tolist()

    profile_rows: List[Dict[str, Any]] = []
    channel_rows: List[Dict[str, Any]] = []

    for house_id in sorted(eligible_houses):
        
        house_quality = cast(
            pd.DataFrame,
            quality[quality["house"].eq(house_id)].copy(),
        )

        mains = _usable_channels(
            house_quality=house_quality,
            meter_type="mains",
        ).sort_values("meter_instance")

        appliances = _usable_channels(
            house_quality=house_quality,
            meter_type="submeter",
        )
        appliances = _exclude_appliances(
            appliances=appliances,
            excluded_appliances=excluded_appliances,
        )
        appliances = _rank_appliances(appliances)

        if max_channels is not None:
            appliances = appliances.head(max_channels).copy()

        if mains.empty or len(appliances) < min_appliance_channels:
            logger.warning(
                "House %s cannot form a candidate: %s mains, %s appliances.",
                house_id,
                len(mains),
                len(appliances),
            )
            continue

        for appliance_count in range(
            len(appliances),
            min_appliance_channels - 1,
            -1,
        ):
            appliance_set = appliances.head(appliance_count).copy()
            all_channels = pd.concat(
                [mains, appliance_set],
                ignore_index=True,
            )

            channel_keys = [
                (house_id, int(instance))
                for instance in all_channels["meter_instance"].tolist()
            ]
            common_sections = find_common_good_sections(
                good_sections=sections,
                channel_keys=channel_keys,
            )

            if not common_sections:
                continue

            common_metrics = _common_metrics(common_sections)
            qualifying_sections = [
                section
                for section in common_sections
                if _duration_days(section) >= min_window_days
            ]

            for segment_number, section in enumerate(
                qualifying_sections,
                start=1,
            ):
                candidate_id = "H{}-S{:02d}-T{:02d}".format(
                    house_id,
                    appliance_count,
                    segment_number,
                )

                profile_rows.append(
                    _profile_row(
                        candidate_id=candidate_id,
                        house_id=house_id,
                        mains=mains,
                        appliances=appliance_set,
                        all_channels=all_channels,
                        section=section,
                        common_metrics=common_metrics,
                        min_window_days=min_window_days,
                        preferred_window_days=preferred_window_days,
                    )
                )
                channel_rows.extend(
                    _candidate_channel_rows(
                        candidate_id=candidate_id,
                        house_id=house_id,
                        section=section,
                        mains=mains,
                        appliances=appliance_set,
                    )
                )

    profiles = pd.DataFrame(profile_rows, columns=PROFILE_COLUMNS)
    candidate_channels = pd.DataFrame(
        channel_rows,
        columns=CANDIDATE_CHANNEL_COLUMNS,
    )

    if not profiles.empty:
        profiles = profiles.sort_values(
            ["house", "appliance_channel_count", "candidate_start"],
            ascending=[True, False, True],
        ).reset_index(drop=True)

    if not candidate_channels.empty:
        candidate_channels = candidate_channels.sort_values(
            ["candidate_id", "role", "meter_instance"],
            ascending=[True, False, True],
        ).reset_index(drop=True)

    return profiles, candidate_channels



def find_common_good_sections(
    good_sections: pd.DataFrame,
    channel_keys: Sequence[Tuple[Any, int]],
) -> TimeFrameGroup:
    """Intersect the NILMTK good sections of all supplied channels."""

    common: Optional[TimeFrameGroup] = None

    for house_id, meter_instance in channel_keys:
        rows = good_sections[
            good_sections["house"].eq(house_id)
            & good_sections["meter_instance"].eq(meter_instance)
        ][["start", "end"]].copy()
        
        meter_sections = _to_timeframe_group(rows)

        if not meter_sections:
            return TimeFrameGroup()

        common = (
            meter_sections
            if common is None
            else common.intersection(meter_sections)
        )

        if not common:
            return TimeFrameGroup()

    if common is None:
        return TimeFrameGroup()

    return TimeFrameGroup(
        sorted(
            [section for section in common if not section.empty],
            key=lambda section: section.start,
        )
    )



def _usable_channels(
    house_quality: pd.DataFrame,
    meter_type: str,
) -> pd.DataFrame:
    mask = (
        house_quality["meter_type"].eq(meter_type)
        & house_quality["has_canonical_ac_type"]
        & house_quality["usable_for_active_pipeline"]
    )

    if meter_type == "submeter":
        mask &= house_quality["appliances"].ne("")

    return cast(pd.DataFrame, house_quality.loc[mask].copy())



def _exclude_appliances(
    appliances: pd.DataFrame,
    excluded_appliances: Optional[Iterable[str]],
) -> pd.DataFrame:
    excluded = {
        str(value).strip().lower()
        for value in (excluded_appliances or [])
        if str(value).strip()
    }

    if not excluded or appliances.empty:
        return appliances

    mask = appliances["appliances"].str.lower().apply(
        lambda value: any(name in value for name in excluded)
    )
    excluded_indices = appliances.index[mask]
    return appliances.drop(index=excluded_indices).copy()



def _rank_appliances(appliances: pd.DataFrame) -> pd.DataFrame:
    """Best channel first; the last row is removed first."""

    return appliances.sort_values(
        by=[
            "longest_good_section_days",
            "good_section_coverage_share",
            "dropout_rate",
            "irregular_gap_share",
            "longest_gap_seconds",
            "sample_count",
            "meter_instance",
        ],
        ascending=[False, False, True, True, True, False, True],
        na_position="last",
    ).reset_index(drop=True)



def _to_timeframe_group(rows: pd.DataFrame) -> TimeFrameGroup:
    timeframes: List[TimeFrame] = []

    for row in rows.sort_values("start").itertuples(index=False):
        start = pd.Timestamp(row.start)
        end = pd.Timestamp(row.end)

        if pd.isna(start) or pd.isna(end) or end <= start:
            continue

        timeframes.append(TimeFrame(start=start, end=end))

    return TimeFrameGroup(timeframes)



def _common_metrics(sections: TimeFrameGroup) -> Dict[str, Any]:
    durations = [_duration_days(section) for section in sections]

    return {
        "common_segment_count": len(sections),
        "total_common_overlap_days": (
            sections.uptime().total_seconds() / SECONDS_PER_DAY
        ),
        "longest_common_segment_days": (
            max(durations) if durations else 0.0
        ),
    }


def _profile_row(
    candidate_id: str,
    house_id: Any,
    mains: pd.DataFrame,
    appliances: pd.DataFrame,
    all_channels: pd.DataFrame,
    section: TimeFrame,
    common_metrics: Dict[str, Any],
    min_window_days: int,
    preferred_window_days: int,
) -> Dict[str, Any]:
    duration = _duration_days(section)

    row: Dict[str, Any] = {
        "candidate_id": candidate_id,
        "house": house_id,
        "mains_instances": _join_instances(mains),
        "appliance_instances": _join_instances(appliances),
        "appliances": " | ".join(
            "M{}: {}".format(int(item.meter_instance), item.appliances)
            for item in appliances.itertuples(index=False)
        ),
        "candidate_start": section.start,
        "candidate_end": section.end,
        "candidate_duration_days": duration,
        "meets_min_window": duration >= min_window_days,
        "meets_preferred_window": duration >= preferred_window_days,
        "mains_channel_count": len(mains),
        "appliance_channel_count": len(appliances),
        "total_channel_count": len(all_channels),
    }
    row.update(common_metrics)
    row.update(_aggregate_quality(all_channels))
    row.update(_calendar_metrics(section.start, section.end))

    return row



def _aggregate_quality(channels: pd.DataFrame) -> Dict[str, Any]:
    return {
        "mean_channel_dropout_rate": _stat(
            channels["dropout_rate"], "mean"
        ),
        "worst_channel_dropout_rate": _stat(
            channels["dropout_rate"], "max"
        ),
        "mean_channel_irregular_gap_share": _stat(
            channels["irregular_gap_share"], "mean"
        ),
        "worst_channel_irregular_gap_share": _stat(
            channels["irregular_gap_share"], "max"
        ),
        "max_channel_longest_gap_seconds": _stat(
            channels["longest_gap_seconds"], "max"
        ),
        "min_channel_good_section_coverage_share": _stat(
            channels["good_section_coverage_share"], "min"
        ),
        "all_channels_sampling_stable": bool(
            channels["sampling_stable"].all()
        ),
    }



def _candidate_channel_rows(
    candidate_id: str,
    house_id: Any,
    section: TimeFrame,
    mains: pd.DataFrame,
    appliances: pd.DataFrame,
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []

    for role, channels in (("mains", mains), ("appliance", appliances)):
        output = channels[CANDIDATE_CHANNEL_COLUMNS[6:]].copy()
        output.insert(0, "role", role)
        output.insert(0, "meter_instance", channels["meter_instance"].values)
        output.insert(0, "candidate_end", section.end)
        output.insert(0, "candidate_start", section.start)
        output.insert(0, "house", house_id)
        output.insert(0, "candidate_id", candidate_id)
        rows.extend(
            [
                dict(zip(output.columns, values))
                for values in output.itertuples(
                    index=False,
                    name=None,
                )
            ]
        )

    return rows



def _calendar_metrics(start: Any, end: Any) -> Dict[str, Any]:
    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(end)

    if end_ts <= start_ts:
        return {
            "calendar_month_count": 0,
            "calendar_months": "",
            "weekday_days": 0,
            "weekend_days": 0,
            "weekday_share": None,
            "weekend_share": None,
        }

    # NILMTK TimeFrame.end is exclusive.
    last_included = end_ts - pd.Timedelta(nanoseconds=1)
    days = pd.date_range(
        start=start_ts.normalize(),
        end=last_included.normalize(),
        freq="D",
    )

    weekday_days = int((days.dayofweek < 5).sum())
    weekend_days = int((days.dayofweek >= 5).sum())
    months = sorted(
        {
            "{:04d}-{:02d}".format(day.year, day.month)
            for day in days
        }
    )

    return {
        "calendar_month_count": len(months),
        "calendar_months": ", ".join(months),
        "weekday_days": weekday_days,
        "weekend_days": weekend_days,
        "weekday_share": _share(weekday_days, len(days)),
        "weekend_share": _share(weekend_days, len(days)),
    }



def _prepare_quality(channel_quality: pd.DataFrame) -> pd.DataFrame:
    quality = channel_quality.copy()
    quality["appliances"] = (
        quality["appliances"].fillna("").astype(str).str.strip()
    )

    for column in [
        "has_canonical_ac_type",
        "usable_for_active_pipeline",
        "sampling_stable",
    ]:
        quality[column] = quality[column].fillna(False).astype(bool)

    for column in [
        "meter_instance",
        "sample_count",
        "nominal_sample_period_seconds",
        "good_sections_count",
        "good_duration_days",
        "longest_good_section_days",
        "good_section_coverage_share",
        "dropout_rate",
        "irregular_gap_share",
        "longest_gap_seconds",
        "mean_power",
        "zero_share",
        "negative_share",
    ]:
        quality[column] = pd.to_numeric(quality[column], errors="coerce")

    return quality



def _duration_days(section: TimeFrame) -> float:
    start = section.start
    end = section.end

    if section.empty or start is None or end is None:
        return 0.0

    duration = pd.Timestamp(end) - pd.Timestamp(start)

    return duration.total_seconds() / SECONDS_PER_DAY



def _join_instances(channels: pd.DataFrame) -> str:
    instances = sorted(
        int(value)
        for value in channels["meter_instance"].dropna().tolist()
    )
    return ", ".join(str(value) for value in instances)



def _stat(
    values: pd.Series,
    operation: str,
) -> Optional[float]:
    numeric = values.apply(
        lambda value: pd.to_numeric(
            value,
            errors="coerce",
        )
    ).dropna()

    if numeric.empty:
        return None

    if operation == "mean":
        result = numeric.mean()
    elif operation == "min":
        result = numeric.min()
    elif operation == "max":
        result = numeric.max()
    else:
        raise ValueError(
            "Unsupported operation: {}".format(operation)
        )

    return float(result)


def _share(numerator: int, denominator: int) -> Optional[float]:
    if denominator <= 0:
        return None
    return numerator / denominator



def _validate_inputs(
    channel_quality: pd.DataFrame,
    house_eligibility: pd.DataFrame,
    good_sections: pd.DataFrame,
    min_window_days: int,
    preferred_window_days: int,
    max_channels: Optional[int],
    min_appliance_channels: int,
) -> None:
    required = {
        "channel_quality": QUALITY_COLUMNS,
        "house_eligibility": [
            "house",
            "eligible_for_active_pipeline",
        ],
        "good_sections": [
            "house",
            "meter_instance",
            "start",
            "end",
        ],
    }
    frames = {
        "channel_quality": channel_quality,
        "house_eligibility": house_eligibility,
        "good_sections": good_sections,
    }

    for name, columns in required.items():
        missing = [column for column in columns if column not in frames[name]]
        if missing:
            raise ValueError("Missing columns in {}: {}".format(name, missing))

    if min_window_days <= 0:
        raise ValueError("min_window_days must be greater than 0.")
    if preferred_window_days < min_window_days:
        raise ValueError(
            "preferred_window_days must be >= min_window_days."
        )
    if max_channels is not None and max_channels <= 0:
        raise ValueError("max_channels must be greater than 0 or None.")
    if min_appliance_channels <= 0:
        raise ValueError("min_appliance_channels must be greater than 0.")
    if max_channels is not None and min_appliance_channels > max_channels:
        raise ValueError(
            "min_appliance_channels cannot exceed max_channels."
        )