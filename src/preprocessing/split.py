import pandas as pd

from src.common.timestamps import local_day_index


def build_chronological_split(
    data: pd.DataFrame,
    quality: pd.DataFrame,
    train_share: float,
    validation_share: float,
    local_timezone: str,
):
    if not 0 < train_share < 1:
        raise ValueError("train_share must be greater than 0 and less than 1.")

    if not 0 < validation_share < 1:
        raise ValueError("validation_share must be greater than 0 and less than 1.")

    if train_share + validation_share >= 1:
        raise ValueError("train_share and validation_share must sum to less than 1.")

    if data.empty:
        raise ValueError("data must not be empty.")

    if not data.index.equals(quality.index):
        raise ValueError("data and quality must use the same index.")

    local_days = local_day_index(data.index, local_timezone).unique()
    total_days = len(local_days)

    train_days = int(total_days * train_share)
    validation_days = train_days + int(total_days * validation_share)

    if (
        train_days == 0
        or validation_days == train_days
        or validation_days >= total_days
    ):
        raise ValueError("Split shares and data length must produce non-empty train, validation, and test splits.")

    train_end = local_days[train_days].tz_convert("UTC")
    validation_end = local_days[validation_days].tz_convert("UTC")

    train_data = data.loc[data.index < train_end]
    validation_data = data.loc[(data.index >= train_end) & (data.index < validation_end)]
    test_data = data.loc[data.index >= validation_end]

    train_quality = quality.loc[train_data.index]
    validation_quality = quality.loc[validation_data.index]
    test_quality = quality.loc[test_data.index]

    return (
        train_data,
        train_quality,
        validation_data,
        validation_quality,
        test_data,
        test_quality,
    )