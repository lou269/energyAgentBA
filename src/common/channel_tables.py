from __future__ import annotations

import pandas as pd

from src.config.project_config import ProjectConfig

MERGE_KEYS = ["house", "meter_instance", "meter_key"]


def mains_channels(channel_registry: pd.DataFrame) -> pd.DataFrame:
    return channel_registry.loc[channel_registry["meter_type"].eq("mains"), MERGE_KEYS]


def load_channel_tables(project_config: ProjectConfig) -> tuple[pd.DataFrame, pd.DataFrame]:
    channel_registry = pd.read_csv(project_config.meta_output_dir / "channel_registry.csv")
    channel_quality = pd.read_csv(project_config.analysis_output_dir / "channel_quality.csv")

    return channel_registry, channel_quality