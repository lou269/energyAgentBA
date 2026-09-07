# python -m pytest tests/unit/data_preparation/test_aggregation.py -v

from __future__ import annotations

import pandas as pd
import pytest

from src.data_preparation.aggregation.aggregation import build_aggregated_data


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