import pandas as pd


def build_features(
    data: pd.DataFrame,
    imputation_mask: pd.DataFrame,
    lags: tuple[int, ...],
    rolling_windows: tuple[int, ...],
):
    features = pd.DataFrame(index=data.index)
    index = pd.DatetimeIndex(data.index)

    features["hour"] = index.hour
    features["day_of_week"] = index.dayofweek
    features["month"] = index.month
    features["is_weekend"] = index.dayofweek >= 5

    for column in data.columns:
        for lag in lags:
            features[f"{column}_lag_{lag}"] = data[column].shift(lag)

        shifted = data[column].shift(1)

        for window in rolling_windows:
            features[f"{column}_rolling_mean_{window}"] = (
                shifted.rolling(window).mean()
            )
            features[f"{column}_rolling_std_{window}"] = (
                shifted.rolling(window).std()
            )

        features[f"{column}_imputed"] = (
            imputation_mask[column].shift(1).fillna(False)
        )

    return features