from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
from nilmtk import DataSet

from experiments.common.standard_config import PROJECT_CONFIG
from src.common.channel_tables import load_channel_tables
from src.common.column_naming import treated_column
from src.config.config_nilmtk import DataPreparationConfig, DiagnosticsConfig
from src.data_preparation.auxiliary_appliance_selection import (
    AuxiliaryApplianceSelection,
    build_auxiliary_appliance_selection,
)
from src.pipeline.io import (
    read_canonical_manifest,
    read_preprocessing_frame,
    read_split_manifest,
)


@dataclass(frozen=True)
class NilmtkContext:
    dataset: DataSet
    channel_registry: pd.DataFrame
    channel_quality: pd.DataFrame
    house: int
    mains_meter_key: str
    # bereinigte Stundenwerte, gegen die der Anteil der Geräte gerechnet wird
    mains: pd.Series
    window_start: pd.Timestamp  # Mains-Kandidatenfenster aus canonical_manifest.csv
    window_end: pd.Timestamp
    # Grenzen des Abschnitts aus split_manifest.csv
    split_start: pd.Timestamp
    split_end: pd.Timestamp


def load_nilmtk_context(split: str) -> NilmtkContext:
    # beide Manifeste statt der Fensterkonfiguration, nilmtk-env liest nur Dateien
    split_manifest = read_split_manifest(PROJECT_CONFIG)
    split_row = split_manifest.loc[split_manifest["split"].eq(split)].iloc[0]
    window = split_row["window"]
    canonical_manifest = read_canonical_manifest(PROJECT_CONFIG)
    manifest_row = canonical_manifest.loc[canonical_manifest["window"].eq(window)].iloc[
        0
    ]
    mains_meter_key = str(manifest_row["meter_key"])
    channel_registry, channel_quality = load_channel_tables(PROJECT_CONFIG)

    return NilmtkContext(
        dataset=DataSet(PROJECT_CONFIG.dataset_path),
        channel_registry=channel_registry,
        channel_quality=channel_quality,
        house=int(manifest_row["house"]),
        mains_meter_key=mains_meter_key,
        mains=read_preprocessing_frame(PROJECT_CONFIG, "treated_hourly", window)[
            treated_column(mains_meter_key)
        ],
        window_start=manifest_row["window_start"],
        window_end=manifest_row["window_end"],
        split_start=split_row["start"],
        split_end=split_row["end"],
    )


def select_appliance_channels(
    context: NilmtkContext,
    window_start: pd.Timestamp,
    window_end: pd.Timestamp,
) -> AuxiliaryApplianceSelection:
    diagnostics_config = DiagnosticsConfig()
    data_config = DataPreparationConfig()

    return build_auxiliary_appliance_selection(
        context.dataset,
        context.channel_registry,
        context.channel_quality,
        context.mains,
        house=context.house,
        window_start=window_start,
        window_end=window_end,
        canonical_ac_type=data_config.canonical_ac_type,
        min_coverage_share=data_config.min_coverage_share,
        min_sampling_share=diagnostics_config.min_auxiliary_window_coverage_share,
    )
