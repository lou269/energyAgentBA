from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PipelineStage:
    name: str
    module: str
    environment: str
    args: tuple[str, ...] = ()


PIPELINE_STAGES = [
    PipelineStage(
            name="preprocessing",
            module="src.preprocessing.preprocessing_runner",
            environment="forecasting-env",
    ),
    PipelineStage(
        name="numerical_analysis",
        module="src.numerical_analysis.num_analysis_runner",
        environment="forecasting-env",
    ),
    PipelineStage(
        name="forecasting",
        module="src.forecasting.forecast_runner",
        environment="forecasting-env",
    ),
    PipelineStage(
        name="structured_state",
        module="src.structured_state.structured_state_runner",
        environment="forecasting-env",
        args=(
            "--decision-time", "2015-12-15T11:00:00+00:00",
            "--model-id", "C2",
            "--split", "validation",
            "--calendar-events", "experiments/scenarios/calendar_events.json",
            "--calendar-source", "simulated_calendar",
            "--calendar-retrieved-at", "2015-12-15T11:00:00+00:00",
            "--calendar-window-start", "2015-12-14T11:00:00+00:00",
            "--calendar-window-end", "2015-12-16T11:00:00+00:00",
        ),
    ),
    PipelineStage(
        name="llm",
        module="src.llm.llm_runner",
        environment="forecasting-env",
        args=("--model", "qwen3.5:9b"),
    )
]
