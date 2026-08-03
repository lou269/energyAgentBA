from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from nilmtk import DataSet

logger = logging.getLogger(__name__)

SECONDS_PER_DAY = 86_400.0


def build_channel_quality(
    dataset: DataSet,
    canonical_ac_type: str,
    min_duration_days: int,
    min_longest_good_section_days: int,
    min_sample_count: int,
    max_zero_share: float,
    min_mean_power: float,
    max_dropout_rate: float,
    max_irregular_gap_share: float,
    reject_negative_values: bool,
    chunksize: int = 1_000_000,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Create one quality row per meter and one row per NILMTK good section."""

    quality_rows: List[Dict[str, Any]] = []
    section_rows: List[Dict[str, Any]] = []

    for house_id, building in dataset.buildings.items():
        for meter in building.elec.meters:
            meter_instance = meter.instance()
            ac_types = _get_ac_types(meter)
            start, end = _get_timeframe(meter)
            channel_duration = _duration_days(start, end)

            row: Dict[str, Any] = {
                "house": house_id,
                "meter_instance": meter_instance,
                "meter_type": (
                    "mains" if meter.is_site_meter() else "submeter"
                ),
                "appliances": _appliance_names(meter),
                "ac_types": ", ".join(ac_types),
                "has_canonical_ac_type": canonical_ac_type in ac_types,
                "start": start,
                "end": end,
                "duration_days": channel_duration,
            }

            if canonical_ac_type not in ac_types:
                row.update(_empty_stats())
                row["sampling_stable"] = False
                row["usable_for_active_pipeline"] = False
                quality_rows.append(row)
                continue

            sections = _get_good_sections(
                meter=meter,
                ac_type=canonical_ac_type,
                chunksize=chunksize,
            )
            meter_sections = _sections_to_rows(
                house_id=house_id,
                meter_instance=meter_instance,
                sections=sections,
            )

            try:
                raw_stats = _summarize_chunks(
                    meter=meter,
                    ac_type=canonical_ac_type,
                    chunksize=chunksize,
                )
            except Exception as error:
                logger.warning(
                    "House %s meter %s: diagnostics failed: %s",
                    house_id,
                    meter_instance,
                    error,
                )
                raw_stats = _empty_stats()

            dropout_rate = _get_dropout_rate(
                meter=meter,
                ac_type=canonical_ac_type,
                sections=sections,
                chunksize=chunksize,
            )

            durations = [
                float(section["duration_days"])
                for section in meter_sections
            ]
            good_duration = float(sum(durations))
            good_coverage = (
                min(good_duration / channel_duration, 1.0)
                if channel_duration is not None and channel_duration > 0
                else None
            )

            row.update(raw_stats)
            row.update(
                {
                    "good_sections_count": len(meter_sections),
                    "good_duration_days": good_duration,
                    "longest_good_section_days": (
                        max(durations) if durations else 0.0
                    ),
                    "good_section_coverage_share": good_coverage,
                    "dropout_rate": dropout_rate,
                }
            )

            irregular_share = _optional_float(
                row.get("irregular_gap_share")
            )
            duplicate_count = int(
                row.get("duplicate_timestamp_count", 0)
            )

            row["sampling_stable"] = bool(
                irregular_share is not None
                and irregular_share <= max_irregular_gap_share
                and duplicate_count == 0
            )

            row["usable_for_active_pipeline"] = _is_usable(
                row=row,
                min_duration_days=min_duration_days,
                min_longest_good_section_days=(
                    min_longest_good_section_days
                ),
                min_sample_count=min_sample_count,
                max_zero_share=max_zero_share,
                min_mean_power=min_mean_power,
                max_dropout_rate=max_dropout_rate,
                reject_negative_values=reject_negative_values,
            )

            quality_rows.append(row)
            section_rows.extend(meter_sections)

    channel_quality = pd.DataFrame(quality_rows)
    good_sections = pd.DataFrame(section_rows)

    if not channel_quality.empty:
        channel_quality = channel_quality.sort_values(
            ["house", "meter_type", "meter_instance"]
        ).reset_index(drop=True)

    if not good_sections.empty:
        good_sections = good_sections.sort_values(
            ["house", "meter_instance", "section_id"]
        ).reset_index(drop=True)

    return channel_quality, good_sections


def _summarize_chunks(
    meter: Any,
    ac_type: str,
    chunksize: int,
) -> Dict[str, Any]:
    """One custom pass for metrics which NILMTK does not expose directly."""

    sample_count = 0
    values_sum = 0.0
    min_power: Optional[float] = None
    max_power: Optional[float] = None
    zero_count = 0
    negative_count = 0

    gap_stats: Dict[str, Any] = {
        "gap_count_total": 0,
        "duplicate_timestamp_count": 0,
        "irregular_gap_count": 0,
        "longest_gap_seconds": None,
    }

    max_sample_period = _positive_float(
        (meter.device or {}).get("max_sample_period")
    )
    previous_timestamp: Optional[pd.Timestamp] = None

    for chunk in meter.load(
        physical_quantity="power",
        ac_type=ac_type,
        chunksize=chunksize,
    ):
        if chunk.empty:
            continue

        series = pd.to_numeric(
            chunk.iloc[:, 0],
            errors="coerce",
        ).dropna()

        if series.empty:
            continue

        if not series.index.is_monotonic_increasing:
            series = series.sort_index()

        sample_count += int(series.size)
        values_sum += float(series.sum())
        zero_count += int(series.eq(0).sum())
        negative_count += int(series.lt(0).sum())

        current_min = float(series.min())
        current_max = float(series.max())
        min_power = (
            current_min if min_power is None else min(min_power, current_min)
        )
        max_power = (
            current_max if max_power is None else max(max_power, current_max)
        )

        timestamps = pd.DatetimeIndex(series.index)
        gap_parts: List[pd.Series] = []

        if previous_timestamp is not None:
            boundary_gap = (
                pd.Timestamp(timestamps[0]) - previous_timestamp
            ).total_seconds()

            if boundary_gap < 0:
                raise ValueError(
                    "Timestamps are not ordered across chunks."
                )

            gap_parts.append(
                pd.Series([boundary_gap], dtype="float64")
            )

        if len(timestamps) >= 2:
            internal_gaps = pd.Series(
                timestamps[1:] - timestamps[:-1],
                dtype="timedelta64[ns]",
            ).dt.total_seconds()

            if internal_gaps.lt(0).any():
                raise ValueError(
                    "Timestamps are not ordered within a chunk."
                )

            gap_parts.append(internal_gaps.astype("float64"))

        if gap_parts:
            _update_gap_stats(
                stats=gap_stats,
                gaps=pd.concat(gap_parts, ignore_index=True),
                max_sample_period=max_sample_period,
            )

        previous_timestamp = pd.Timestamp(timestamps[-1])

    if sample_count == 0:
        return _empty_stats()

    gap_count = int(gap_stats["gap_count_total"])
    irregular_share = (
        int(gap_stats["irregular_gap_count"]) / gap_count
        if gap_count > 0 and max_sample_period is not None
        else None
    )

    return {
        "sample_count": sample_count,
        "nominal_sample_period_seconds": _get_sample_period(meter),
        "max_sample_period_seconds": max_sample_period,
        "gap_count_total": gap_count,
        "duplicate_timestamp_count": int(
            gap_stats["duplicate_timestamp_count"]
        ),
        "irregular_gap_count": int(gap_stats["irregular_gap_count"]),
        "irregular_gap_share": irregular_share,
        "longest_gap_seconds": gap_stats["longest_gap_seconds"],
        "min_power": min_power,
        "max_power": max_power,
        "mean_power": values_sum / sample_count,
        "zero_share": zero_count / sample_count,
        "negative_share": negative_count / sample_count,
    }


def _update_gap_stats(
    stats: Dict[str, Any],
    gaps: pd.Series,
    max_sample_period: Optional[float],
) -> None:
    stats["gap_count_total"] += int(gaps.size)
    stats["duplicate_timestamp_count"] += int(gaps.eq(0).sum())

    if max_sample_period is not None:
        stats["irregular_gap_count"] += int(
            gaps.gt(max_sample_period).sum()
        )

    longest = float(gaps.max())
    stats["longest_gap_seconds"] = (
        longest
        if stats["longest_gap_seconds"] is None
        else max(float(stats["longest_gap_seconds"]), longest)
    )


def _get_good_sections(
    meter: Any,
    ac_type: str,
    chunksize: int,
) -> List[Any]:
    try:
        return list(
            meter.good_sections(
                physical_quantity="power",
                ac_type=ac_type,
                chunksize=chunksize,
            )
        )
    except Exception as error:
        logger.warning(
            "Meter %s: good_sections failed: %s",
            meter.instance(),
            error,
        )
        return []


def _get_dropout_rate(
    meter: Any,
    ac_type: str,
    sections: List[Any],
    chunksize: int,
) -> Optional[float]:
    if not sections:
        return None

    try:
        return _optional_float(
            meter.dropout_rate(
                ignore_gaps=False,
                sections=sections,
                physical_quantity="power",
                ac_type=ac_type,
                chunksize=chunksize,
            )
        )
    except Exception as error:
        logger.warning(
            "Meter %s: dropout_rate failed: %s",
            meter.instance(),
            error,
        )
        return None


def _sections_to_rows(
    house_id: int,
    meter_instance: int,
    sections: List[Any],
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []

    for section_id, section in enumerate(sections, start=1):
        start = getattr(section, "start", None)
        end = getattr(section, "end", None)
        days = _duration_days(start, end)

        if days is None or days <= 0:
            continue

        rows.append(
            {
                "house": house_id,
                "meter_instance": meter_instance,
                "section_id": section_id,
                "start": start,
                "end": end,
                "duration_seconds": days * SECONDS_PER_DAY,
                "duration_days": days,
            }
        )

    return rows


def _is_usable(
    row: Dict[str, Any],
    min_duration_days: int,
    min_longest_good_section_days: int,
    min_sample_count: int,
    max_zero_share: float,
    min_mean_power: float,
    max_dropout_rate: float,
    reject_negative_values: bool,
) -> bool:
    checks = [
        bool(row.get("has_canonical_ac_type", False)),
        _meets_min(row.get("duration_days"), min_duration_days),
        _meets_min(
            row.get("longest_good_section_days"),
            min_longest_good_section_days,
        ),
        _meets_min(row.get("sample_count"), min_sample_count),
        _meets_max(row.get("dropout_rate"), max_dropout_rate),
        _meets_max(row.get("zero_share"), max_zero_share),
        _meets_min(row.get("mean_power"), min_mean_power),
        bool(row.get("sampling_stable", False)),
    ]

    if reject_negative_values:
        checks.append(_meets_max(row.get("negative_share"), 0.0))

    return all(checks)


def _empty_stats() -> Dict[str, Any]:
    return {
        "sample_count": 0,
        "nominal_sample_period_seconds": None,
        "max_sample_period_seconds": None,
        "gap_count_total": 0,
        "duplicate_timestamp_count": 0,
        "irregular_gap_count": 0,
        "irregular_gap_share": None,
        "longest_gap_seconds": None,
        "good_sections_count": 0,
        "good_duration_days": 0.0,
        "longest_good_section_days": 0.0,
        "good_section_coverage_share": None,
        "dropout_rate": None,
        "min_power": None,
        "max_power": None,
        "mean_power": None,
        "zero_share": None,
        "negative_share": None,
    }


def _get_ac_types(meter: Any) -> List[str]:
    try:
        return list(meter.available_ac_types("power"))
    except Exception:
        return []


def _get_timeframe(
    meter: Any,
) -> Tuple[Optional[pd.Timestamp], Optional[pd.Timestamp]]:
    try:
        timeframe = meter.get_timeframe()
        return timeframe.start, timeframe.end
    except Exception:
        return None, None


def _get_sample_period(meter: Any) -> Optional[float]:
    try:
        return _positive_float(meter.sample_period())
    except Exception:
        return _positive_float(
            (meter.device or {}).get("sample_period")
        )


def _appliance_names(meter: Any) -> str:
    names: List[str] = []

    for appliance in getattr(meter, "appliances", []):
        identifier = getattr(appliance, "identifier", None)
        appliance_type = getattr(identifier, "type", None)
        if appliance_type is not None:
            names.append(str(appliance_type))

    return ", ".join(sorted(set(names)))


def _duration_days(start: Any, end: Any) -> Optional[float]:
    if start is None or end is None or pd.isna(start) or pd.isna(end):
        return None

    try:
        seconds = (
            pd.Timestamp(end) - pd.Timestamp(start)
        ).total_seconds()
    except (TypeError, ValueError):
        return None

    return max(float(seconds), 0.0) / SECONDS_PER_DAY


def _optional_float(value: Any) -> Optional[float]:
    if value is None or pd.isna(value):
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _positive_float(value: Any) -> Optional[float]:
    number = _optional_float(value)
    return number if number is not None and number > 0 else None


def _meets_min(value: Any, threshold: float) -> bool:
    number = _optional_float(value)
    return number is not None and number >= threshold


def _meets_max(value: Any, threshold: float) -> bool:
    number = _optional_float(value)
    return number is not None and number <= threshold