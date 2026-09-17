# python -m pytest tests/unit/data_preparation/test_aggregation.py -v

from __future__ import annotations

import pandas as pd
import pytest

from src.common.column_naming import channel_data_column
from src.data_preparation.aggregation.aggregation import build_aggregated_data, build_canonical_data


def test_build_aggregated_data_uses_per_channel_sample_period() -> None:
    index_1s = pd.date_range("2020-01-01T00:00:00Z", periods=3600, freq="1s")
    index_6s = pd.date_range("2020-01-01T00:00:00Z", periods=600, freq="6s")

    channels = {
        "mains": pd.Series(1.0, index=index_1s),
        "submeter": pd.Series(1.0, index=index_6s),
    }
    sample_periods = {"mains": 1, "submeter": 6}

    _, _, _, quality_hourly = build_aggregated_data(
        channels=channels,
        sample_periods=sample_periods,
        min_coverage_share=0.95,
    )

    assert quality_hourly["mains_coverage_share"].iloc[0] == pytest.approx(1.0)
    assert quality_hourly["submeter_coverage_share"].iloc[0] == pytest.approx(1.0)
    assert quality_hourly["mains_coverage_mask"].iloc[0]
    assert quality_hourly["submeter_coverage_mask"].iloc[0]


def test_build_aggregated_data_flags_low_coverage_independently_per_channel() -> None:
    full_index = pd.date_range("2020-01-01T00:00:00Z", periods=3600, freq="1s")
    sparse_index = full_index[:900]

    channels = {
        "mains": pd.Series(1.0, index=full_index),
        "sparse": pd.Series(1.0, index=sparse_index),
    }
    sample_periods = {"mains": 1, "sparse": 1}

    _, _, _, quality_hourly = build_aggregated_data(
        channels=channels,
        sample_periods=sample_periods,
        min_coverage_share=0.95,
    )

    assert quality_hourly["mains_coverage_mask"].iloc[0]
    assert not quality_hourly["sparse_coverage_mask"].iloc[0]
    assert quality_hourly["sparse_coverage_share"].iloc[0] == pytest.approx(0.25)


def test_build_aggregated_data_merges_channels_after_resampling() -> None:
    channels = {
        "early": pd.Series(1.0, index=pd.date_range("2020-01-01", periods=2, freq="1h")),
        "late": pd.Series(1.0, index=pd.date_range("2020-01-02", periods=2, freq="1h")),
    }
    sample_periods = {"early": 3600, "late": 3600}

    _, _, data_hourly, _ = build_aggregated_data(
        channels=channels,
        sample_periods=sample_periods,
        min_coverage_share=0.95,
    )

    assert list(data_hourly.columns) == ["early", "late"]
    assert data_hourly["early"].isna().any()
    assert data_hourly["late"].isna().any()


def test_build_canonical_data_snaps_a_partial_window_to_full_local_days() -> None:
    meter_key = "H1_M1"
    index_hourly = pd.date_range("2020-01-01T00:00:00Z", "2020-01-05T00:00:00Z", freq="1h")
    index_15min = pd.date_range("2020-01-01T00:00:00Z", "2020-01-05T00:00:00Z", freq="15min")

    data_hourly = pd.DataFrame({meter_key: 1.0}, index=index_hourly)
    data_15min = pd.DataFrame({meter_key: 1.0}, index=index_15min)

    quality_values = {
        f"{meter_key}_valid_observation_count": 1,
        f"{meter_key}_coverage_share": 1.0,
        f"{meter_key}_coverage_mask": True,
    }
    quality_hourly = pd.DataFrame(quality_values, index=index_hourly)
    quality_15min = pd.DataFrame(quality_values, index=index_15min)

    # 05:00 am ersten und 19:00 am letzten Tag, kein voller Kalendertag an beiden Rändern
    window_start = pd.Timestamp("2020-01-01T05:00:00Z")
    window_end = pd.Timestamp("2020-01-04T19:00:00Z")

    (
        snapped_start,
        snapped_end,
        canonical_data_15min,
        canonical_data_hourly,
        canonical_quality_15min,
        canonical_quality_hourly,
    ) = build_canonical_data(
        data_15min, quality_15min, data_hourly, quality_hourly,
        meter_key, window_start, window_end, "Europe/London",
    )

    assert snapped_start == pd.Timestamp("2020-01-02T00:00:00Z")
    assert snapped_end == pd.Timestamp("2020-01-04T00:00:00Z")
    assert canonical_data_hourly.index[0] == snapped_start
    assert canonical_data_hourly.index[-1] == snapped_end
    assert canonical_data_15min.index[0] == snapped_start
    assert canonical_data_15min.index[-1] == snapped_end

    assert list(canonical_data_hourly.columns) == [channel_data_column(meter_key, "hourly")]
    assert list(canonical_data_15min.columns) == [channel_data_column(meter_key, "15min")]
    assert list(canonical_quality_hourly.columns) == list(quality_values)
    assert list(canonical_quality_15min.columns) == list(quality_values)