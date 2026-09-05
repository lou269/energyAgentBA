from __future__ import annotations

import logging

import pandas as pd
from nilmtk import DataSet
from nilmtk.stats.goodsections import GoodSections

import warnings

from src.analysis.common import require_columns


logger = logging.getLogger(__name__)

SECONDS_PER_DAY = 86_400.0


CHANNEL_QUALITY_COLUMNS = [
    "house",
    "meter_instance",
    "meter_key",
    "start",
    "end",
    "duration_days",
    "valid_sample_count",
    "sampling_share",
    "dropout_rate",
    "good_section_count",
    "total_good_section_duration_days",
    "longest_good_section_days",
    "good_section_coverage_share",
    "quality_error",
]


GOOD_SECTION_COLUMNS = [
    "house",
    "meter_instance",
    "meter_key",
    "section_id",
    "start",
    "end",
    "duration_seconds",
    "duration_days",
]


REQUIRED_REGISTRY_COLUMNS = {
    "house",
    "meter_instance",
    "meter_key",
    "has_canonical_ac_type",
    "sample_period_seconds"
}


def build_channel_quality(
    dataset: DataSet,
    channel_registry: pd.DataFrame,
    canonical_ac_type: str,
    chunksize: int | None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    
    require_columns(channel_registry, REQUIRED_REGISTRY_COLUMNS, "Channel registry")

    registry = channel_registry.loc[
        channel_registry["has_canonical_ac_type"]
        .fillna(False)
        .astype(bool)
    ]

    quality_rows = []
    good_section_rows = []

    for row in registry.itertuples(index=False):
        identity = {
            "house": int(row.house),
            "meter_instance": int(row.meter_instance),
            "meter_key": str(row.meter_key),
        }

        try:
            meter = dataset.buildings[
                identity["house"]
            ].elec[
                identity["meter_instance"]
            ]

            sample_period = row.sample_period_seconds

            if pd.isna(sample_period) or float(sample_period) <= 0:
                sample_period = None
            else:
                sample_period = float(sample_period)

            quality_row, section_rows = _profile_meter(
                meter,
                identity,
                canonical_ac_type,
                sample_period,
                chunksize,
            )

        except Exception as error:
            logger.warning(
                "House %s meter %s: channel profiling failed: %s",
                identity["house"],
                identity["meter_instance"],
                error,
            )

            quality_row = {
                **identity,
                "quality_error": f"{type(error).__name__}: {error}"
            }
            section_rows = []

        quality_rows.append(quality_row)
        good_section_rows.extend(section_rows)

    quality = pd.DataFrame(
        quality_rows,
        columns=CHANNEL_QUALITY_COLUMNS,
    )

    good_sections = pd.DataFrame(
        good_section_rows,
        columns=GOOD_SECTION_COLUMNS,
    )

    if not quality.empty:
        quality = quality.sort_values(
            ["house", "meter_instance"],
            kind="mergesort",
        ).reset_index(drop=True)

    if not good_sections.empty:
        good_sections = good_sections.sort_values(
            ["house", "meter_instance", "section_id"], kind="mergesort"
        ).reset_index(drop=True)

    return quality, good_sections


def _profile_meter(
    meter,
    identity: dict,
    canonical_ac_type: str,
    sample_period: float | None,
    chunksize: int | None,
) -> tuple[dict, list[dict]]:
    good_sections_stat = GoodSections()

    load_kwargs = {
        "physical_quantity": "power",
        "ac_type": canonical_ac_type,
        "resample": False,
        "preprocessing": [good_sections_stat],
        "n_look_ahead_rows": 10,
    }

    if chunksize is not None:
        load_kwargs["chunksize"] = chunksize

    valid_sample_count = 0
    start = None
    end = None

    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message=r"If you are using `preprocessing` to resample.*",
            category=UserWarning,
            module=r"nilmtk\.electric",
        )

        for chunk in meter.load(**load_kwargs):
            if chunk.empty:
                continue

            series = chunk.iloc[:, 0]
            sample_count = int(series.count())

            if sample_count == 0:
                continue

            valid_sample_count += sample_count

            first_valid = series.first_valid_index()
            last_valid = series.last_valid_index()

            if start is None:
                start = first_valid

            end = last_valid
            
    good_section_results = good_sections_stat.results

    if good_section_results is None:
        raise RuntimeError("GoodSections produced no results.")

    sections = good_section_results.combined()

    if (
        start is not None
        and end is not None
        and end > start
        and sample_period
    ):
        duration_seconds = (end - start).total_seconds()

        expected_sample_count = int(duration_seconds // sample_period) + 1
        sampling_share = min(1.0, valid_sample_count / expected_sample_count)

        dropout_rate = 1.0 - sampling_share
    else:
        duration_seconds = None
        sampling_share = None
        dropout_rate = None

    section_rows = []
    section_durations = []

    for section_id, section in enumerate(
        sections,
        start=1,
    ):
        if section.start is None or section.end is None:
            continue

        section_duration = (section.end - section.start).total_seconds()

        section_durations.append(section_duration)

        section_rows.append(
            {
                **identity,
                "section_id": section_id,
                "start": section.start,
                "end": section.end,
                "duration_seconds": section_duration,
                "duration_days": (section_duration / SECONDS_PER_DAY),
            }
        )

    total_good_seconds = sum(section_durations)
    longest_good_seconds = max(section_durations, default=0.0)

    quality_row = {
        **identity,
        "start": start,
        "end": end,
        "duration_days": (
            duration_seconds / SECONDS_PER_DAY
            if duration_seconds is not None
            else None
        ),
        "valid_sample_count": valid_sample_count,
        "sampling_share": sampling_share,
        "dropout_rate": dropout_rate,
        "good_section_count": len(section_rows),
        "total_good_section_duration_days": total_good_seconds / SECONDS_PER_DAY,
        "longest_good_section_days": longest_good_seconds / SECONDS_PER_DAY,
        "good_section_coverage_share": (
            total_good_seconds / duration_seconds
            if duration_seconds
            else None
        ),
        "quality_error": None,
    }

    return quality_row, section_rows