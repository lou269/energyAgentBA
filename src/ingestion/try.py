from __future__ import annotations
from nilmtk import DataSet
from pathlib import Path
from src.config.project_config import ProjectConfig
from src.analysis.eda.metadata_exploration import summary_to_csv


if __name__ == "__main__":
    summary_to_csv(
        hdf_path=Path("data/processed/ukdale.h5"),
        output_path=Path("output/metadata"))
    