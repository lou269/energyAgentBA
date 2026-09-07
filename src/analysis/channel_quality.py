from __future__ import annotations

import logging

import pandas as pd
from nilmtk import DataSet

import warnings

from src.analysis.common import require_columns


logger = logging.getLogger(__name__)

SECONDS_PER_DAY = 86_400.0


CHANNEL_QUALITY_COLUMNS = [
    "house",
    "meter_instance",
    "meter_key",
    "is_mains",
    "start",
    "end",
    "duration_days",
    "valid_sample_count",
    "sampling_share",
    "dropout_rate",
    "quality_error",
]


REQUIRED_REGISTRY_COLUMNS = {
    "house",
    "meter_instance",
    "meter_key",
    "meter_type",
    "has_canonical_ac_type",
    "sample_period_seconds"
}


def build_channel_quality(
    dataset: DataSet,
    channel_registry: pd.DataFrame,
    canonical_ac_type: str,
    chunksize: int | None,
) -> pd.DataFrame:
    
    require_columns(channel_registry, REQUIRED_REGISTRY_COLUMNS, "Channel registry")

    canonical = channel_registry.loc[
        channel_registry["has_canonical_ac_type"].fillna(False).astype(bool)
    ]

    houses_with_mains = canonical.loc[canonical["meter_type"].eq("mains"), "house"].unique().tolist()

    registry = canonical.loc[canonical["house"].isin(houses_with_mains)]
    

    quality_rows = []

    for row in registry.itertuples(index=False):
        identity = {
            "house": int(row.house),
            "meter_instance": int(row.meter_instance),
            "meter_key": str(row.meter_key),
            "is_mains": row.meter_type == "mains",
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

            quality_row = _profile_meter(
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

        quality_rows.append(quality_row)

    quality = pd.DataFrame(
        quality_rows,
        columns=CHANNEL_QUALITY_COLUMNS,
    )

    if not quality.empty:
        quality = quality.sort_values(
            ["house", "meter_instance"],
            kind="mergesort",
        ).reset_index(drop=True)


    return quality


def _profile_meter(
    meter,
    identity: dict,
    canonical_ac_type: str,
    sample_period: float | None,
    chunksize: int | None,
) ->dict:

    load_kwargs = {
        "physical_quantity": "power",
        "ac_type": canonical_ac_type,
        "resample": False,
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
        "quality_error": None,
    }

    return quality_row