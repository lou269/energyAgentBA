from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
from nilmtk import DataSet

from src.common.channel_tables import load_channel_tables
from src.common.column_naming import treated_column
from src.config.project_config import ProjectConfig


@dataclass(frozen=True)
class NilmtkContext:
    dataset: DataSet
    channel_registry: pd.DataFrame
    channel_quality: pd.DataFrame
    house: int
    mains_meter_key: str
    window_start: pd.Timestamp  # Mains-Kandidatenfenster aus canonical_manifest.csv
    window_end: pd.Timestamp


def load_nilmtk_context(project_config: ProjectConfig) -> NilmtkContext:
    canonical_manifest = pd.read_csv(project_config.canonical_output_dir / "canonical_manifest.csv")

    if len(canonical_manifest) != 1:
        raise ValueError("Canonical manifest must contain exactly one mains target.")

    manifest_row = canonical_manifest.iloc[0]
    channel_registry, channel_quality = load_channel_tables(project_config)

    return NilmtkContext(
        dataset=DataSet(project_config.dataset_path),
        channel_registry=channel_registry,
        channel_quality=channel_quality,
        house=int(manifest_row["house"]),
        mains_meter_key=str(manifest_row["meter_key"]),
        window_start=pd.Timestamp(manifest_row["window_start"]),
        window_end=pd.Timestamp(manifest_row["window_end"]),
    )


def load_treated_mains_series(project_config: ProjectConfig, mains_meter_key: str) -> pd.Series:
    treated_hourly = pd.read_csv(project_config.preprocessing_output_dir / "treated_hourly.csv", parse_dates=["timestamp"], index_col="timestamp")

    return treated_hourly[treated_column(mains_meter_key)]
