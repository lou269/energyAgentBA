# python -m src.structured_state.structured_state_runner
from __future__ import annotations

import argparse
import json
import logging
from collections.abc import Mapping
from pathlib import Path
from typing import Literal

import pandas as pd

from src.config.project_config import ProjectConfig, ensure_project_directories
from src.context.calendar_context import build_calendar_context
from src.pipeline.io import save_json
from src.structured_state.builder import build_structured_state
from src.structured_state.structured_state_schema import (
    StructuredState,
    validate_structured_state,
)


logger = logging.getLogger(__name__)

StateSplit = Literal["validation", "test"]


class StructuredStateRunner:
    def __init__(self, project_config: ProjectConfig | None = None) -> None:
        self.project_config = project_config or ProjectConfig()

    def run(
        self,
        *,
        decision_time: str | pd.Timestamp,
        model_id: str,
        split: StateSplit,
        calendar_events: list[Mapping[str, object]],
        calendar_source_available: bool,
        calendar_source: str,
        calendar_retrieved_at: str | pd.Timestamp,
        calendar_window_start: str | pd.Timestamp,
        calendar_window_end: str | pd.Timestamp,
    ) -> StructuredState:
        ensure_project_directories(self.project_config)

        logger.info(
            "Starting Structured State: decision_time=%s, model_id=%s, split=%s.",
            decision_time,
            model_id,
            split,
        )

        decision_timestamp = pd.Timestamp(decision_time)

        if decision_timestamp.tzinfo is None:
            raise ValueError("decision_time must contain timezone information.")

        decision_timestamp = decision_timestamp.tz_convert("UTC")

        analysis = pd.read_csv(
            self.project_config.numerical_analysis_output_dir
            / "anomaly_scores_hourly.csv",
            parse_dates=["timestamp"],
        )

        analysis_timestamp = decision_timestamp - pd.Timedelta(hours=1)

        analysis_rows = analysis.loc[
            analysis["timestamp"].eq(analysis_timestamp) & analysis["split"].eq(split)
        ]

        if len(analysis_rows) != 1:
            raise ValueError(
                f"Expected exactly one numerical-analysis row for {analysis_timestamp.isoformat()} and split {split!r}, found {len(analysis_rows)}."
            )

        forecasts = pd.read_csv(
            self.project_config.forecasting_output_dir / f"forecasts_{split}.csv",
            parse_dates=["forecast_origin", "target_timestamp"],
        )

        forecast_rows = forecasts.loc[
            forecasts["forecast_origin"].eq(decision_timestamp)
            & forecasts["model_id"].eq(model_id)
            & forecasts["split"].eq(split)
        ]

        calendar_context = build_calendar_context(
            calendar_events,
            source_available=calendar_source_available,
            source=calendar_source,
            retrieved_at=calendar_retrieved_at,
            decision_time=decision_timestamp,
            window_start=calendar_window_start,
            window_end=calendar_window_end,
        )

        state = build_structured_state(
            decision_time=decision_timestamp,
            analysis_row=analysis_rows.iloc[0],
            forecast_rows=forecast_rows,
            calendar_context=calendar_context,
        )

        validate_structured_state(state)

        output_file = (
            self.project_config.structured_state_output_dir / "structured_state.json"
        )

        save_json(dict(state), output_file)

        logger.info("Structured State saved to %s.", output_file)

        return state


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a Structured State.")

    parser.add_argument("--decision-time", required=True)
    parser.add_argument("--model-id", required=True)
    parser.add_argument("--split", choices=("validation", "test"), required=True)
    parser.add_argument(
        "--calendar-events",
        type=Path,
        default=None,
        help="Optional JSON file containing a list of calendar events.",
    )
    parser.add_argument("--calendar-source", required=True)
    parser.add_argument("--calendar-source-unavailable", action="store_true")
    parser.add_argument("--calendar-retrieved-at", required=True)
    parser.add_argument("--calendar-window-start", required=True)
    parser.add_argument("--calendar-window-end", required=True)

    args = parser.parse_args()

    calendar_events: list[Mapping[str, object]] = []

    if args.calendar_events is not None:
        with args.calendar_events.open("r", encoding="utf-8") as file:
            loaded_events = json.load(file)

        if not isinstance(loaded_events, list):
            raise ValueError("calendar-events must contain a JSON list.")

        calendar_events = loaded_events

    split: StateSplit = args.split

    logging.basicConfig(level=logging.INFO)

    StructuredStateRunner().run(
        decision_time=args.decision_time,
        model_id=args.model_id,
        split=split,
        calendar_events=calendar_events,
        calendar_source_available=not args.calendar_source_unavailable,
        calendar_source=args.calendar_source,
        calendar_retrieved_at=args.calendar_retrieved_at,
        calendar_window_start=args.calendar_window_start,
        calendar_window_end=args.calendar_window_end,
    )


if __name__ == "__main__":
    main()
