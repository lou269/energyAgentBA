from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ProjectConfig:
    project_root: Path = Path(__file__).resolve().parents[2]

    # Data
    data_dir: Path = project_root / "data"
    archive_path: Path = data_dir / "ukdale.zip"
    raw_dir: Path = data_dir / "raw"
    meta_dir: Path = raw_dir / "metadata"
    processed_dir: Path = data_dir / "processed"

    # Outputs
    output_dir: Path = project_root / "output"
    meta_output_dir: Path = output_dir / "metadata"
    diagnostics_output_dir: Path = output_dir / "diagnostics"
    selection_output_dir: Path = output_dir / "selection"
    preparation_output_dir: Path = output_dir / "preparation"
    # validation_output_dir: Path = output_dir / "validation"
    canonical_output_dir: Path = output_dir / "canonical"
    preprocessing_output_dir: Path = output_dir / "preprocessing"
    # numerical_analysis_output_dir: Path = output_dir / "numerical_analysis"
    # forecasting_output_dir: Path = output_dir / "forecasting"
    # structured_state_output_dir: Path = output_dir / "structured_state"
    # llm_output_dir: Path = output_dir / "llm"
    cycle_output_dir: Path = output_dir / "cycle"

    # je Experiment ein Unterordner (e1, k1, ...), darin je Lauf die Ergebnisse oben und die Rohdaten in raw/
    experiment_output_dir: Path = project_root / "experiments" / "output"
    e1_output_dir: Path = experiment_output_dir / "e1"
    e2_output_dir: Path = experiment_output_dir / "e2"
    e3_output_dir: Path = experiment_output_dir / "e3"
    e4_output_dir: Path = experiment_output_dir / "e4"
    e5_output_dir: Path = experiment_output_dir / "e5"
    k1_output_dir: Path = experiment_output_dir / "k1"
    k2_output_dir: Path = experiment_output_dir / "k2"
    k3_output_dir: Path = experiment_output_dir / "k3"
    k4_output_dir: Path = experiment_output_dir / "k4"
    proactive_cycle_output_dir: Path = experiment_output_dir / "proactive_cycle"

    timezone: str = "Europe/London"

    # Dataset
    dataset_release: str = "UK-DALE April 2017"
    dataset_doi: str = "10.5286/UKERC.EDC.000004"
    dataset_filename: str = "ukdale.h5"

    # CEDA directories
    url_data: str = "https://data.ceda.ac.uk/edc/d1/7d78f943-f9fe-413b-af52-1816f9d968b0/data/version_0"
    url_metadata: str = (
        "https://data.ceda.ac.uk/edc/d1/7d78f943-f9fe-413b-af52-1816f9d968b0/documents"
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
        # config.validation_output_dir,
        config.canonical_output_dir,
        config.preprocessing_output_dir,
        # config.numerical_analysis_output_dir,
        # config.forecasting_output_dir,
        # config.structured_state_output_dir,
        # config.llm_output_dir,
        config.cycle_output_dir,
    ]

    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)
