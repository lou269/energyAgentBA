from __future__ import annotations

from typing import cast

import numpy as np
import pandas as pd
from sklearn.feature_selection import VarianceThreshold
from sklearn.preprocessing import StandardScaler


def fit_transformations(
    train_features: pd.DataFrame,
    variance_threshold: float,
) -> tuple[
    pd.DataFrame,
    VarianceThreshold,
    StandardScaler,
    list[str],
]:
    """Fittet Featureauswahl und Skalierung nur auf Trainingsdaten."""
    if not np.isfinite(variance_threshold) or variance_threshold < 0:
        raise ValueError(
            "variance_threshold must be finite and greater than or equal to zero."
        )

    selector = VarianceThreshold(threshold=variance_threshold)

    selected_values = cast(
        np.ndarray,
        selector.fit_transform(train_features),
    )

    selected_columns = cast(
        list[str],
        train_features.columns[
            selector.get_support()
        ].tolist(),
    )

    scaler = StandardScaler()

    transformed_values = cast(
        np.ndarray,
        scaler.fit_transform(selected_values),
    )

    train_transformed = pd.DataFrame(
        transformed_values,
        index=train_features.index,
        columns=selected_columns,
    )

    return (
        train_transformed,
        selector,
        scaler,
        selected_columns,
    )


def apply_transformations(
    features: pd.DataFrame,
    selector: VarianceThreshold,
    scaler: StandardScaler,
    selected_columns: list[str],
) -> pd.DataFrame:
    """Wendet die auf Training gefitteten Transformationen an."""
    expected_columns = list(selector.feature_names_in_)

    if list(features.columns) != expected_columns:
        raise ValueError(
            "Feature columns or their order differ from the training schema."
        )

    selected_values = cast(
        np.ndarray,
        selector.transform(features),
    )

    transformed_values = cast(
        np.ndarray,
        scaler.transform(selected_values),
    )

    return pd.DataFrame(
        transformed_values,
        index=features.index,
        columns=selected_columns,
    )
    
    
def fit_normalization(
    train_data: pd.DataFrame,
) -> tuple[pd.DataFrame, StandardScaler]:
    """Fittet die Normalisierung ausschließlich auf Trainingsdaten."""

    if train_data.empty:
        raise ValueError("train_data must not be empty.")

    if train_data.notna().sum().eq(0).any():
        raise ValueError(
            "Every column must contain at least one observed training value."
        )

    scaler = StandardScaler()

    normalized_values = cast(
        np.ndarray,
        scaler.fit_transform(train_data),
    )

    normalized_data = pd.DataFrame(
        normalized_values,
        index=train_data.index,
        columns=train_data.columns,
    )

    return normalized_data, scaler


def apply_normalization(
    data: pd.DataFrame,
    scaler: StandardScaler,
) -> pd.DataFrame:
    """Wendet die auf Train gefittete Normalisierung unverändert an."""

    expected_columns = list(scaler.feature_names_in_)

    if list(data.columns) != expected_columns:
        raise ValueError(
            "Data columns or their order differ from the training schema."
        )

    normalized_values = cast(
        np.ndarray,
        scaler.transform(data),
    )

    return pd.DataFrame(
        normalized_values,
        index=data.index,
        columns=data.columns,
    )


def inverse_normalization(
    values: pd.Series,
    scaler: StandardScaler,
    source_column: str,
) -> pd.Series:
    """Transformiert normalisierte Werte zurück in die ursprüngliche Einheit."""

    expected_columns = list(scaler.feature_names_in_)

    if source_column not in expected_columns:
        raise ValueError(
            f"Unknown normalization source column: {source_column}."
        )

    column_position = expected_columns.index(source_column)

    means = scaler.mean_
    scales = scaler.scale_

    if means is None or scales is None:
        raise ValueError(
            "Scaler must be fitted with mean and standard deviation."
        )

    mean = float(means[column_position])
    scale = float(scales[column_position])

    return values * scale + mean