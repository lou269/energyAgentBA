from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PipelineStage:
    name: str
    module: str
    environment: str


PIPELINE_STAGES = [
    PipelineStage(
        name="ingestion",
        module="src.ingestion.ingestion_runner",
        environment="nilmtk-env",
    ),
    PipelineStage(
        name="analysis",
        module="src.analysis.analysis_runner",
        environment="nilmtk-env",
    ),
    PipelineStage(
        name="data_preparation",
        module="src.data_preparation.data_preparation_runner",
        environment="nilmtk-env",
    ),
    PipelineStage(
        name="preprocessing",
        module="src.preprocessing.preprocessing_runner",
        environment="forecasting-env",
    ),
]

