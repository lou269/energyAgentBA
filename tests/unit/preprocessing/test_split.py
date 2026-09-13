# python -m pytest tests/unit/preprocessing/test_split.py -v

import pandas as pd
import pytest

from src.preprocessing.split import build_chronological_split


def test_split_is_chronological_and_matches_shares() -> None:
    index = pd.date_range("2020-01-01", periods=10, freq="1D")
    data = pd.DataFrame({"m1": range(10)}, index=index)
    quality = pd.DataFrame({"m1_coverage_mask": [True] * 10}, index=index)

    (
        train_data,
        train_quality,
        validation_data,
        validation_quality,
        test_data,
        test_quality,
    ) = build_chronological_split(data, quality, train_share=0.6, validation_share=0.2)

    assert len(train_data) == 6
    assert len(validation_data) == 2
    assert len(test_data) == 2
    assert train_data.index[-1] < validation_data.index[0]
    assert validation_data.index[-1] < test_data.index[0]
    assert train_quality.index.equals(train_data.index)
    assert validation_quality.index.equals(validation_data.index)
    assert test_quality.index.equals(test_data.index)


def test_shares_producing_an_empty_split_raise() -> None:
    index = pd.date_range("2020-01-01", periods=2, freq="1D")
    data = pd.DataFrame({"m1": [1, 2]}, index=index)
    quality = pd.DataFrame({"m1_coverage_mask": [True, True]}, index=index)

    with pytest.raises(ValueError, match="non-empty"):
        build_chronological_split(data, quality, train_share=0.4, validation_share=0.4)
