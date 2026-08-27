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