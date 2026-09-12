from __future__ import annotations


def channel_data_column(meter_key: str, value_suffix: str) -> str:
    return f"{meter_key}{value_suffix}"


def treated_column(meter_key: str) -> str:
    return f"{meter_key}_mean_after_gt"


def imputation_column(meter_key: str) -> str:
    return f"{meter_key}_imputated"


def plausibility_column(meter_key: str) -> str:
    return f"{meter_key}_unplausible"


def quality_column(meter_key: str, metric: str) -> str:
    return f"{meter_key}_{metric}"


def meter_key_from_data_column(column: str, value_suffix: str) -> str:
    return column.removesuffix(value_suffix)