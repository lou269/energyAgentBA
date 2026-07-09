"""
project_config.py

Zentrale Projektkonfiguration.

Diese Datei enthält nur allgemeine Einstellungen, die von mehreren
Pipeline-Bereichen gemeinsam genutzt werden:

- Projektpfade
- Datenpfade
- Output-Pfade
- gemeinsame Dateinamen / Frequenzen
- UK-DALE-Metadaten

Spezifische Einstellungen bleiben in den jeweiligen Configs:
- EDAConfig: EDA-Thresholds, Pattern-Thresholds, Plot-Settings
- PipelineConfig: Scope, Channel-Auswahl, Pipeline-Outputs
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class ProjectConfig:
    project_root: Path = Path(__file__).resolve().parents[2]

    data_dir: Path = project_root / "data"
    raw_dir: Path = data_dir / "raw" 
    meta_dir: Path = raw_dir / "metadata"
    processed_dir: Path = data_dir / "processed"
    cleaned_dir: Path = data_dir / "cleaned"

    output_dir: Path = project_root / "output"
    eda_output_dir: Path = output_dir / "eda"
    meta_output_dir: Path = output_dir / "metadata"
    plots_output_dir: Path = output_dir / "plots"
    cleaned_plots_output_dir: Path = output_dir / "plots_cleaned"
    consistency_output_dir: Path = output_dir / "data_consistency"

    target_freq: str = "1h"

    datetime_column: str = "datetime"
    power_column: str = "power"
    
    metadata_files: list[str] = field(
        default_factory=lambda: ["dataset.yaml", "meter_devices.yaml"]
    )

    url_base: str = (
        "https://dap.ceda.ac.uk/edc/d1/b3baa0aa-05ac-4ec8-b608-da5751758698/"
        "data/version_0"
    )
    url_metadata: str = (
        "https://raw.githubusercontent.com/JackKelly/UK-DALE_metadata/master"
    )

    houses: list[str] = field(
        default_factory=lambda: [
            "house_1",
            "house_2",
            "house_3",
            "house_4",
            "house_5",
        ]
    )
    
def ensure_project_directories(config: ProjectConfig) -> None:
    directories = [
        config.data_dir,
        config.raw_dir,
        config.meta_dir,
        config.processed_dir,
        config.cleaned_dir,
        config.output_dir,
        config.eda_output_dir,
        config.meta_output_dir,
        config.plots_output_dir,
        config.cleaned_plots_output_dir,
        config.consistency_output_dir,
    ]

    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)