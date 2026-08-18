import pandas as pd


def build_chronological_split(
    data: pd.DataFrame,
    quality: pd.DataFrame,
    train_share: float,
    validation_share: float,
):
    train_end = int(len(data) * train_share)
    validation_end = train_end + int(
        len(data) * validation_share
    )

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