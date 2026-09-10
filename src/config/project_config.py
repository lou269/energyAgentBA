from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ProjectConfig:
    project_root: Path = Path(__file__).resolve().parents[2]

    # Data
    data_dir: Path = project_root / "data_2017"
    archive_path: Path = data_dir / "ukdale.zip"
    raw_dir: Path = data_dir / "raw"
    meta_dir: Path = raw_dir / "metadata"
    processed_dir: Path = data_dir / "processed"

    # Outputs
    output_dir: Path = project_root / "output"
    meta_output_dir: Path = output_dir / "metadata"
    analysis_output_dir: Path = output_dir / "analysis"
    selection_output_dir: Path = output_dir / "selection"
    preparation_output_dir: Path = output_dir / "preparation"
    validation_output_dir: Path = output_dir / "validation"
    canonical_output_dir: Path = output_dir / "canonical"
    preprocessing_output_dir: Path = output_dir / "preprocessing"
    numerical_analysis_output_dir: Path = output_dir / "numerical_analysis"
    forecasting_output_dir: Path = output_dir / "forecasting"
    structured_state_output_dir: Path = output_dir / "structured_state"
    llm_output_dir: Path = output_dir / "llm"
    cycle_output_dir: Path = output_dir / "cycle"

    # Dataset
    dataset_release: str = "UK-DALE April 2017"
    dataset_doi: str = "10.5286/UKERC.EDC.000004"
    dataset_filename: str = "ukdale.h5"

    # CEDA directories
    url_data: str = "https://data.ceda.ac.uk/edc/d1/7d78f943-f9fe-413b-af52-1816f9d968b0/data/version_0"
    url_metadata: str = "https://data.ceda.ac.uk/edc/d1/7d78f943-f9fe-413b-af52-1816f9d968b0/documents"
 

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
        config.analysis_output_dir,
        config.selection_output_dir,
        config.preparation_output_dir,
        config.validation_output_dir,
        config.canonical_output_dir,
        config.preprocessing_output_dir,
        config.numerical_analysis_output_dir,
        config.forecasting_output_dir,
        config.structured_state_output_dir,
        config.llm_output_dir,
        config.cycle_output_dir,
    ]

    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)

