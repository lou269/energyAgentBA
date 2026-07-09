from __future__ import annotations

from typing import Any
import pandas as pd
from nilmtk import DataSet
import logging

logger = logging.getLogger(__name__)


def build_channel_quality(
    dataset: DataSet,
    canonical_ac_type: str,
    min_duration_days: int,
    min_longest_good_section_days: int,
    min_sample_count: int,
    max_zero_share: float,
    min_mean_power: float,
    max_median_sample_period_seconds: int,
    max_p99_sample_period_seconds: int,
    max_longest_gap_seconds: int,
    reject_negative_values: bool,
) -> pd.DataFrame:
    
    rows = []

    for house_id, building in dataset.buildings.items():
        elec = building.elec
        mains_instances = {meter.instance() for meter in get_mains_meters(elec)}

        for meter in elec.meters:
            rows.append(
                get_meter_quality(
                    house_id=house_id,
                    meter=meter,
                    mains_instances=mains_instances,
                    canonical_ac_type=canonical_ac_type,
                    min_duration_days=min_duration_days,
                    min_longest_good_section_days=min_longest_good_section_days,
                    min_sample_count=min_sample_count,
                    max_zero_share=max_zero_share,
                    min_mean_power=min_mean_power,
                    max_median_sample_period_seconds=max_median_sample_period_seconds,
                    max_p99_sample_period_seconds=max_p99_sample_period_seconds,
                    max_longest_gap_seconds=max_longest_gap_seconds,
                    reject_negative_values=reject_negative_values,
                )
            )

    return pd.DataFrame(rows)


def get_mains_meters(elec: Any) -> list[Any]:
    try:
        mains = elec.mains()
    except Exception:
        return []

    return list(mains.meters) if hasattr(mains, "meters") else [mains]


def appliance_names(meter: Any) -> str:
    appliances = getattr(meter, "appliances", [])
    names = [
        app.identifier.type
        for app in appliances
        if hasattr(app, "identifier")
    ]
    return ", ".join(names)


def duration_days(start: Any, end: Any) -> float | None:
    if start is None or end is None:
        return None
    return max((end - start).total_seconds(), 0.0) / 86400



def get_meter_quality(
    house_id: int,
    meter: Any,
    mains_instances: set[int],
    canonical_ac_type: str,
    min_duration_days: int,
    min_longest_good_section_days: int,
    min_sample_count: int,
    max_zero_share: float,
    min_mean_power: float,
    max_median_sample_period_seconds: int,
    max_p99_sample_period_seconds: int,
    max_longest_gap_seconds: int,
    reject_negative_values: bool = True,
) -> dict[str, Any]:
    
    meter_instance = meter.instance()

    try:
        ac_types = meter.available_ac_types("power")
    except Exception as error:
        logger.warning(
            "Could not read ac types for house %s meter %s: %s",
            house_id,
            meter_instance,
            error,
        )
        ac_types = []

    has_canonical_ac_type = canonical_ac_type in ac_types

    try:
        timeframe = meter.get_timeframe()
        start, end = timeframe.start, timeframe.end
    except Exception as error:
        logger.warning(
            "Could not read timeframe for house %s meter %s: %s",
            house_id,
            meter_instance,
            error,
        )
        start, end = None, None

    try:
        good_sections = (
            meter.good_sections(physical_quantity="power", ac_type=canonical_ac_type)
            if has_canonical_ac_type
            else []
        )
    except Exception as error:
        logger.warning(
            "Could not compute good sections for house %s meter %s: %s",
            house_id,
            meter_instance,
            error,
        )
        good_sections = []

    good_durations = [
        max((section.end - section.start).total_seconds(), 0.0) / 86400
        for section in good_sections
        if section.start is not None and section.end is not None
    ]

    try:
        dropout_rate = (
            meter.dropout_rate(physical_quantity="power", ac_type=canonical_ac_type)
            if has_canonical_ac_type
            else None
        )
    except Exception as error:
        logger.warning(
            "Could not compute dropout rate for house %s meter %s: %s",
            house_id,
            meter_instance,
            error,
        )
        dropout_rate = None

    try:
        power_stats = (
            summarize_power_chunks(meter, canonical_ac_type)
            if has_canonical_ac_type
            else {
                "sample_count": 0,
                "median_sample_period_seconds": None,
                "p99_sample_period_seconds": None,
                "longest_gap_seconds": None,
                "gaps_le_12s": 0,
                "gaps_le_1min": 0,
                "gaps_le_10min": 0,
                "gaps_le_1h": 0,
                "gaps_le_1d": 0,
                "gaps_gt_1d": 0,
                "min_power": None,
                "max_power": None,
                "mean_power": None,
                "zero_share": None,
                "negative_share": None,
            }
        )
    except Exception as error:
        logger.warning(
            "Could not summarize power for house %s meter %s: %s",
            house_id,
            meter_instance,
            error,
        )
        power_stats = {
            "sample_count": 0,
            "median_sample_period_seconds": None,
            "p99_sample_period_seconds": None,
            "longest_gap_seconds": None,
            "gaps_le_12s": 0,
            "gaps_le_1min": 0,
            "gaps_le_10min": 0,
            "gaps_le_1h": 0,
            "gaps_le_1d": 0,
            "gaps_gt_1d": 0,
            "min_power": None,
            "max_power": None,
            "mean_power": None,
            "zero_share": None,
            "negative_share": None,
        }

    row = {
        "house": house_id,
        "meter_instance": meter_instance,
        "meter_type": "mains" if meter_instance in mains_instances else "submeter",
        "appliances": appliance_names(meter),
        "ac_types": ", ".join(ac_types),
        "canonical_ac_type": canonical_ac_type,
        "has_canonical_ac_type": has_canonical_ac_type,
        "has_active": "active" in ac_types,
        "has_apparent": "apparent" in ac_types,
        "start": start,
        "end": end,
        "duration_days": duration_days(start, end),
        "good_sections_count": len(good_sections),
        "good_duration_days": sum(good_durations),
        "longest_good_section_days": max(good_durations) if good_durations else 0.0,
        "dropout_rate": dropout_rate,
    }
    row.update(power_stats)


    row["usable_for_active_pipeline"] = is_usable_channel(
        row=row,
        min_duration_days=min_duration_days,
        min_longest_good_section_days=min_longest_good_section_days,
        min_sample_count=min_sample_count,
        max_zero_share=max_zero_share,
        min_mean_power=min_mean_power,
        max_median_sample_period_seconds=max_median_sample_period_seconds,
        max_p99_sample_period_seconds=max_p99_sample_period_seconds,
        max_longest_gap_seconds=max_longest_gap_seconds,
        reject_negative_values=reject_negative_values
    )
    return row


def summarize_power_chunks(
    meter: Any,
    ac_type: str,
    chunksize: int = 1_000_000,
) -> dict[str, Any]:
    
    values_count = 0
    values_sum = 0.0
    values_min = None
    values_max = None
    zero_count = 0
    negative_count = 0
    gap_values: list[float] = []
    previous_timestamp = None

    for chunk in meter.load(
        physical_quantity="power",
        ac_type=ac_type,
        chunksize=chunksize,
    ):
        if chunk.empty:
            continue

        series = chunk.iloc[:, 0].dropna().sort_index()
        if series.empty:
            continue

        values_count += len(series)
        values_sum += float(series.sum())

        current_min = float(series.min())
        current_max = float(series.max())
        values_min = current_min if values_min is None else min(values_min, current_min)
        values_max = current_max if values_max is None else max(values_max, current_max)

        zero_count += int((series == 0).sum())
        negative_count += int((series < 0).sum())

        index = series.index
        if previous_timestamp is not None:
            gap_values.append((index[0] - previous_timestamp).total_seconds())

        if len(index) >= 2:
            gaps = index.to_series().diff().dropna().dt.total_seconds()
            gap_values.extend(gaps.tolist())

        previous_timestamp = index[-1]

    if values_count == 0:
        return {
            "sample_count": 0,
            "median_sample_period_seconds": None,
            "p99_sample_period_seconds": None,
            "longest_gap_seconds": None,
            "gaps_le_12s": 0,
            "gaps_le_1min": 0,
            "gaps_le_10min": 0,
            "gaps_le_1h": 0,
            "gaps_le_1d": 0,
            "gaps_gt_1d": 0,
            "min_power": None,
            "max_power": None,
            "mean_power": None,
            "zero_share": None,
            "negative_share": None,
        }

    gaps = pd.Series(gap_values, dtype="float64")

    return {
        "sample_count": values_count,
        "median_sample_period_seconds": float(gaps.median()) if not gaps.empty else None,
        "p99_sample_period_seconds": float(gaps.quantile(0.99)) if not gaps.empty else None,
        "longest_gap_seconds": float(gaps.max()) if not gaps.empty else None,
        "gaps_le_12s": int((gaps <= 12).sum()),
        "gaps_le_1min": int(((gaps > 12) & (gaps <= 60)).sum()),
        "gaps_le_10min": int(((gaps > 60) & (gaps <= 600)).sum()),
        "gaps_le_1h": int(((gaps > 600) & (gaps <= 3600)).sum()),
        "gaps_le_1d": int(((gaps > 3600) & (gaps <= 86400)).sum()),
        "gaps_gt_1d": int((gaps > 86400).sum()),
        "min_power": values_min,
        "max_power": values_max,
        "mean_power": values_sum / values_count,
        "zero_share": zero_count / values_count,
        "negative_share": negative_count / values_count,
    }


def is_usable_channel(
    row: dict[str, Any],
    min_duration_days: int,
    min_longest_good_section_days: int,
    min_sample_count: int,
    max_zero_share: float,
    min_mean_power: float,
    max_median_sample_period_seconds: int,
    max_p99_sample_period_seconds: int,
    max_longest_gap_seconds: int,
    reject_negative_values: bool = True,
) -> bool:

    if not row["has_canonical_ac_type"]:
        return False

    if row["duration_days"] is None or row["duration_days"] < min_duration_days:
        return False

    if row["longest_good_section_days"] < min_longest_good_section_days:
        return False

    if row["sample_count"] is None or row["sample_count"] < min_sample_count:
        return False

    if row["zero_share"] is not None and row["zero_share"] > max_zero_share:
        return False

    if row["mean_power"] is not None and row["mean_power"] < min_mean_power:
        return False

    if (
        row["median_sample_period_seconds"] is not None
        and row["median_sample_period_seconds"] > max_median_sample_period_seconds
    ):
        return False

    if (
        row["p99_sample_period_seconds"] is not None
        and row["p99_sample_period_seconds"] > max_p99_sample_period_seconds
    ):
        return False

    if (
        row["longest_gap_seconds"] is not None
        and row["longest_gap_seconds"] > max_longest_gap_seconds
    ):
        return False

    if reject_negative_values and row["negative_share"] is not None and row["negative_share"] > 0:
        return False

    return True





