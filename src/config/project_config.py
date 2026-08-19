from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class ProjectConfig:
    project_root: Path = Path(__file__).resolve().parents[2]

    # Data
    data_dir: Path = project_root / "data"
    raw_dir: Path = data_dir / "raw"
    meta_dir: Path = raw_dir / "metadata"
    processed_dir: Path = data_dir / "processed"

    # Outputs
    output_dir: Path = project_root / "output"
    meta_output_dir: Path = output_dir / "metadata"
    diagnostics_output_dir: Path = output_dir / "diagnostics"
    selection_output_dir: Path = output_dir / "selection"
    preparation_output_dir: Path = output_dir / "preparation"
    validation_output_dir: Path = output_dir / "validation"
    canonical_output_dir: Path = output_dir / "canonical"
    preprocessing_output_dir: Path = output_dir / "preprocessing"
    numerical_analysis_output_dir: Path = output_dir / "numerical_analysis"

    
    # Dataset
    dataset_filename: str = "ukdale.h5"

    metadata_files: list[str] = field(
        default_factory=lambda: [
            "dataset.yaml",
            "meter_devices.yaml",
        ]
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

    # UK-DALE sources
    url_base: str = (
        "https://dap.ceda.ac.uk/edc/d1/"
        "b3baa0aa-05ac-4ec8-b608-da5751758698/"
        "data/version_0"
    )

    url_metadata: str = (
        "https://raw.githubusercontent.com/"
        "JackKelly/UK-DALE_metadata/master"
    )

    @property
    def dataset_path(self) -> Path:
        return self.processed_dir / self.dataset_filename


def ensure_project_directories(config: ProjectConfig) -> None:
    directories = [
        config.data_dir,
        config.raw_dir,
        config.meta_dir,
        config.processed_dir,
        config.output_dir,
        config.meta_output_dir,
        config.diagnostics_output_dir,
        config.selection_output_dir,
        config.preparation_output_dir,
        config.validation_output_dir,
        config.canonical_output_dir,
        config.preprocessing_output_dir,
        config.numerical_analysis_output_dir,

    ]

    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)