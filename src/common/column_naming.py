from __future__ import annotations


def channel_data_column(meter_key: str, resolution: str) -> str:
    return f"{meter_key}_mean_{resolution}"


def treated_column(meter_key: str) -> str:
    return f"{meter_key}_mean_after_gt"


def imputation_column(meter_key: str) -> str:
    return f"{meter_key}_imputed"


def plausibility_column(meter_key: str) -> str:
    return f"{meter_key}_implausible"


def quality_column(meter_key: str, metric: str) -> str:
    return f"{meter_key}_{metric}"


def meter_key_from_data_column(column: str, resolution: str) -> str:
    return column.removesuffix(f"_mean_{resolution}")