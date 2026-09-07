import pandas as pd


def build_chronological_split(
    data: pd.DataFrame,
    quality: pd.DataFrame,
    train_share: float,
    validation_share: float,
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

    train_end = int(len(data) * train_share)
    validation_end = train_end + int(len(data) * validation_share)

    if (
        train_end == 0
        or validation_end == train_end
        or validation_end >= len(data)
    ):
        raise ValueError("Split shares and data length must produce non-empty train, validation, and test splits.")

    train_data = data.iloc[:train_end]
    validation_data = data.iloc[train_end:validation_end]
    test_data = data.iloc[validation_end:]

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