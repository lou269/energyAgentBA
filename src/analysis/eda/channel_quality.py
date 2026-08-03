from __future__ import annotations

from typing import Any
import pandas as pd
from nilmtk import DataSet
import logging
from time import perf_counter

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
    max_median_sample_period_seconds: int,
    max_p99_sample_period_seconds: int,
    max_longest_gap_seconds: int,
    reject_negative_values: bool,
    chunksize: int = 1_000_000,
    
) -> pd.DataFrame:
    
    rows: list[dict[str, Any]] = []

    logger.info(
        "Buildings available in dataset: %s",
        list(dataset.buildings.keys()),
    )

    for house_id, building in dataset.buildings.items():
        meters = list(building.elec.meters)

        logger.info(
            "House %s: evaluating %s meters.",
            house_id,
            len(meters),
        )

        for meter in meters:
            meter_instance = meter.instance()

            try:
                ac_types = list(
                    meter.available_ac_types("power")
                )
            except Exception as error:
                logger.warning(
                    "House %s meter %s: could not read AC types: %s",
                    house_id,
                    meter_instance,
                    error,
                )
                continue

            if canonical_ac_type not in ac_types:
                logger.info(
                    "Skipping house %s meter %s because active power "
                    "is not available.",
                    house_id,
                    meter_instance,
                )
                continue
            

            meter_type = (
                "mains"
                if meter.is_site_meter()
                else "submeter"
            )



            '''
            logger.info(
                "House %s meter %s (%s): using AC type '%s'.",
                house_id,
                meter_instance,
                meter_type,
                selected_ac_type,
            )
            '''
            
            row = get_meter_quality(
                house_id=house_id,
                meter=meter,
                canonical_ac_type = canonical_ac_type,
                min_duration_days=min_duration_days,
                min_longest_good_section_days=(
                    min_longest_good_section_days
                ),
                min_sample_count=min_sample_count,
                max_zero_share=max_zero_share,
                min_mean_power=min_mean_power,
                max_median_sample_period_seconds=(
                    max_median_sample_period_seconds
                ),
                max_p99_sample_period_seconds=(
                    max_p99_sample_period_seconds
                ),
                max_longest_gap_seconds=max_longest_gap_seconds,
                reject_negative_values=reject_negative_values,
                chunksize=chunksize,
            )

            row["meter_type"] = meter_type
            rows.append(row)

    return pd.DataFrame(rows)


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

    if pd.isna(start) or pd.isna(end):
        return None

    try:
        duration_seconds = (
            pd.Timestamp(end) - pd.Timestamp(start)
        ).total_seconds()

    except (
        TypeError,
        ValueError,
    ):
        return None

    return (
        max(float(duration_seconds), 0.0)
        / SECONDS_PER_DAY
    )


def empty_quality_stats() -> dict[str, Any]:
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
        "good_sections_count": 0,
        "good_duration_days": 0.0,
        "longest_good_section_days": 0.0,
        "dropout_rate": None,
        "min_power": None,
        "max_power": None,
        "mean_power": None,
        "zero_share": None,
        "negative_share": None,
    }


def get_meter_quality(
    house_id: int,
    meter: Any,
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
    chunksize: int = 1_000_000,
) -> dict[str, Any]:
    meter_instance = meter.instance()

    try:
        ac_types = list(meter.available_ac_types("power"))
    except Exception as error:
        logger.warning(
            "Could not read ac types for house %s meter %s: %s",
            house_id,
            meter_instance,
            error,
        )
        ac_types = []

    try:
        timeframe = meter.get_timeframe()
        start = timeframe.start
        end = timeframe.end

    except Exception as error:
        logger.warning(
            "Could not read timeframe for house %s meter %s: %s",
            house_id,
            meter_instance,
            error,
        )
        start = None
        end = None


    try:
        quality_stats = summarize_power_chunks(
            meter=meter,
            ac_type=canonical_ac_type,
            chunksize=chunksize,
        )

    except Exception as error:
        logger.warning(
            "Could not summarize house %s mains meter %s: %s",
            house_id,
            meter_instance,
            error,
        )
        quality_stats = empty_quality_stats()


    row: dict[str, Any] = {
        "house": house_id,
        "meter_instance": meter_instance,
        "meter_type": "mains",
        "appliances": appliance_names(meter),
        "ac_types": ", ".join(ac_types),
        "has_canonical_ac_type": canonical_ac_type in ac_types,
        "start": start,
        "end": end,
        "duration_days": duration_days(start, end),
    }

    row.update(quality_stats)

    row["usable_for_active_pipeline"] = (
        is_usable_channel(
            row=row,
            min_duration_days=min_duration_days,
            min_longest_good_section_days=(
                min_longest_good_section_days
            ),
            min_sample_count=min_sample_count,
            max_zero_share=max_zero_share,
            min_mean_power=min_mean_power,
            max_median_sample_period_seconds=(
                max_median_sample_period_seconds
            ),
            max_p99_sample_period_seconds=(
                max_p99_sample_period_seconds
            ),
            max_longest_gap_seconds=(
                max_longest_gap_seconds
            ),
            reject_negative_values=(
                reject_negative_values
            ),
        )
    )

    return row


def summarize_power_chunks(
    meter: Any,
    ac_type: str,
    chunksize: int = 1_000_000,
) -> dict[str, Any]:
    device = meter.device or {}

    sample_period = device.get("sample_period")
    max_sample_period = device.get("max_sample_period")

    values_count = 0
    values_sum = 0.0
    values_min: float | None = None
    values_max: float | None = None
    zero_count = 0
    negative_count = 0

    gap_values: list[pd.Series] = []
    previous_timestamp: pd.Timestamp | None = None

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

        values_count += int(series.size)
        values_sum += float(series.sum())

        current_min = float(series.min())
        current_max = float(series.max())
        values_min = current_min if values_min is None else min(values_min, current_min)
        values_max = current_max if values_max is None else max(values_max, current_max)

        zero_count += int((series == 0).sum())
        negative_count += int((series < 0).sum())

        first_timestamp = pd.Timestamp(series.index[0])
        last_timestamp = pd.Timestamp(series.index[-1])

        if previous_timestamp is not None:
            boundary_gap = (
                first_timestamp - previous_timestamp
            ).total_seconds()

            if boundary_gap < 0:
                raise ValueError(
                    "Timestamps are not ordered across chunks."
                )

            gap_values.append(
                pd.Series(
                    [boundary_gap],
                    dtype="float64",
                )
            )

        if len(series) >= 2:
            gaps = pd.Series(
                series.index[1:] - series.index[:-1],
                dtype="timedelta64[ns]",
            ).dt.total_seconds()

            gaps = gaps.dropna()

            if gaps.lt(0).any():
                raise ValueError(
                    "Timestamps are not ordered within a chunk."
                )

            gap_values.append(
                gaps.astype("float64")
            )

        previous_timestamp = last_timestamp

    if values_count == 0:
        return empty_quality_stats()

    all_gaps = (
        pd.concat(gap_values, ignore_index=True)
        if gap_values
        else pd.Series(dtype="float64")
    )

    result: dict[str, Any] = {
        "sample_count": values_count,
        "median_sample_period_seconds": (
            float(all_gaps.median())
            if not all_gaps.empty
            else None
        ),
        "p99_sample_period_seconds": (
            float(all_gaps.quantile(0.99))
            if not all_gaps.empty
            else None
        ),
        "longest_gap_seconds": (
            float(all_gaps.max())
            if not all_gaps.empty
            else None
        ),
        "min_power": values_min,
        "max_power": values_max,
        "mean_power": values_sum / values_count,
        "zero_share": zero_count / values_count,
        "negative_share": negative_count / values_count,
    }

    result.update(
        summarize_good_sections(
            gaps=all_gaps,
            sample_period=sample_period,
            max_sample_period=max_sample_period,
        )
    )

    return result


def positive_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None

    if pd.isna(number) or number <= 0:
        return None

    return number

def summarize_good_sections(
    gaps: pd.Series,
    sample_period: float | None,
    max_sample_period: float | None,
) -> dict[str, Any]:
    """Leitet Good Sections aus den Abständen der Zeitstempel ab."""

    empty_result = {
        "good_sections_count": 0,
        "good_duration_days": 0.0,
        "longest_good_section_days": 0.0,
        "dropout_rate": None,
    }

    if gaps.empty:
        return empty_result

    if max_sample_period is None:
        return empty_result

    good_gap_mask = gaps.le(
        max_sample_period
    )

    if not good_gap_mask.any():
        return empty_result

    previous_mask = good_gap_mask.shift(
        periods=1,
        fill_value=False,
    )

    group_ids = (
        good_gap_mask
        .ne(previous_mask)
        .cumsum()
    )

    good_gaps = gaps[
        good_gap_mask
    ]

    good_group_ids = group_ids[
        good_gap_mask
    ]

    section_durations = (
        good_gaps
        .groupby(good_group_ids)
        .sum()
    )

    section_gap_counts = (
        good_gaps
        .groupby(good_group_ids)
        .size()
    )

    section_sample_counts = (
        section_gap_counts + 1
    )

    dropout_rate: float | None = None

    if sample_period is not None:
        expected_sample_counts = (
            section_durations
            .div(sample_period)
            .round()
            .astype("int64")
            .add(1)
            .clip(lower=1)
        )

        section_dropout_rates = (
            1.0
            - section_sample_counts.div(
                expected_sample_counts
            )
        ).clip(
            lower=0.0,
            upper=1.0,
        )

        total_section_samples = int(
            section_sample_counts.sum()
        )

        if total_section_samples > 0:
            weighted_dropout_sum = float(
                section_dropout_rates
                .mul(section_sample_counts)
                .sum()
            )

            dropout_rate = (
                weighted_dropout_sum
                / total_section_samples
            )

    return {
        "good_sections_count": int(
            section_durations.size
        ),
        "good_duration_days": float(
            section_durations.sum()
            / SECONDS_PER_DAY
        ),
        "longest_good_section_days": float(
            section_durations.max()
            / SECONDS_PER_DAY
        ),
        "dropout_rate": dropout_rate,
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
    '''
    if (
        row["longest_gap_seconds"] is not None
        and row["longest_gap_seconds"] > max_longest_gap_seconds
    ):
        return False
    '''

    if reject_negative_values and row["negative_share"] is not None and row["negative_share"] > 0:
        return False

    return True





