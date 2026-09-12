# python -m src.structured_state.structured_state_runner --decision-time 2015-12-15T11:00:00+00:00 --model-id C2 --split validation --calendar-events path/to/calendar_events.json --calendar-source simulated_calendar --calendar-retrieved-at 2015-12-15T11:00:00+00:00 --calendar-window-start 2015-12-14T11:00:00+00:00 --calendar-window-end 2015-12-16T11:00:00+00:00
# --decision-time muss ein forecast_origin im gelesenen Forecasting-Run sein und genau 1h nach einem timestamp im gelesenen output/numerical_analysis/an_<nummer>/anomaly_scores_hourly.csv (gleicher split) liegen
# liest standardmäßig den neuesten output/forecasting/fc_<val|test>_<nummer>/ Ordner; --forecast-run-number erzwingt einen bestimmten
# liest standardmäßig den neuesten output/numerical_analysis/an_<nummer>/ Ordner; --analysis-run-number erzwingt einen bestimmten
# --calendar-events weglassen = kein Kalenderzugriff (CTX0, source_available=false); die anderen --calendar-* Felder sind auch dann Pflicht
# jeder Lauf landet in einem eigenen Ordner output/structured_state/ss_<nummer>_fc_<forecast-nummer>_an_<analysis-nummer>_<decision_time>/
from __future__ import annotations

import argparse
import json
import logging
from collections.abc import Mapping
from pathlib import Path
from time import perf_counter
from typing import Literal

import pandas as pd

from src.common.timestamps import parse_utc_timestamp
from src.config.project_config import ProjectConfig, ensure_project_directories
from src.context.calendar_context import build_calendar_context
from src.pipeline.io import find_run_directory, latest_sequential_number, save_json
from src.structured_state.builder import build_structured_state
from src.structured_state.structured_state_run_manifest import build_structured_state_run_manifest
from src.structured_state.structured_state_schema import StructuredState, validate_structured_state


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
        forecast_run_number: int | None = None,
        analysis_run_number: int | None = None,
        calendar_events_file: Path | None = None,
    ) -> StructuredState:
        ensure_project_directories(self.project_config)
        run_started = perf_counter()

        split_abbreviation = "val" if split == "validation" else split

        if forecast_run_number is None:
            forecast_run_number = latest_sequential_number(self.project_config.forecasting_output_dir, prefix=f"fc_{split_abbreviation}")
            if forecast_run_number is None:
                raise FileNotFoundError(f"No forecasting run found for split {split!r} in {self.project_config.forecasting_output_dir}.")

        forecast_run_directory = self.project_config.forecasting_output_dir / f"fc_{split_abbreviation}_{forecast_run_number:03d}"

        if analysis_run_number is None:
            analysis_run_number = latest_sequential_number(self.project_config.numerical_analysis_output_dir, prefix="an")
            if analysis_run_number is None:
                raise FileNotFoundError(f"No numerical-analysis run found in {self.project_config.numerical_analysis_output_dir}.")

        analysis_run_directory = self.project_config.numerical_analysis_output_dir / f"an_{analysis_run_number:03d}"

        logger.info(
            "Starting Structured State: decision_time=%s, model_id=%s, split=%s, forecast_run=%s, analysis_run=%s.",
            decision_time,
            model_id,
            split,
            forecast_run_directory.name,
            analysis_run_directory.name,
        )

        decision_timestamp = parse_utc_timestamp(decision_time, "decision_time")

        analysis_path = analysis_run_directory / "anomaly_scores_hourly.csv"
        analysis = pd.read_csv(analysis_path, parse_dates=["timestamp"])

        analysis_timestamp = decision_timestamp - pd.Timedelta(hours=1)

        analysis_rows = analysis.loc[analysis["timestamp"].eq(analysis_timestamp) & analysis["split"].eq(split)]

        if len(analysis_rows) != 1:
            raise ValueError(
                f"Expected exactly one numerical-analysis row for {analysis_timestamp.isoformat()} and split {split!r}, found {len(analysis_rows)}."
            )

        forecasts = pd.read_csv(
            forecast_run_directory / f"forecasts_{split}.csv",
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

        latest_ss_run = find_run_directory(self.project_config.structured_state_output_dir, prefix="ss")
        ss_number = (latest_ss_run[0] if latest_ss_run is not None else 0) + 1
        run_id = f"ss_{ss_number:03d}_fc_{forecast_run_number:03d}_an_{analysis_run_number:03d}_{decision_timestamp.strftime('%Y%m%dT%H%M')}"
        run_directory = self.project_config.structured_state_output_dir / run_id

        if run_directory.exists():
            raise FileExistsError(f"Structured State run directory already exists: {run_directory}")

        run_directory.mkdir(parents=True, exist_ok=False)

        output_file = run_directory / "structured_state.json"
        save_json(dict(state), output_file)

        input_paths = {
            "numerical_analysis": analysis_path,
            "forecasts": forecast_run_directory / f"forecasts_{split}.csv",
        }

        if calendar_events_file is not None:
            input_paths["calendar_events"] = calendar_events_file

        manifest = build_structured_state_run_manifest(
            project_root=self.project_config.project_root,
            run_id=run_id,
            decision_time=decision_timestamp.isoformat(),
            model_id=model_id,
            split=split,
            forecast_run_directory=forecast_run_directory.name,
            forecast_run_number=forecast_run_number,
            analysis_run_directory=analysis_run_directory.name,
            analysis_run_number=analysis_run_number,
            calendar_source=calendar_source,
            calendar_source_available=calendar_source_available,
            calendar_retrieved_at=calendar_context["retrieved_at"],
            calendar_window_start=calendar_context["window_start"],
            calendar_window_end=calendar_context["window_end"],
            input_paths=input_paths,
            output_paths={"structured_state": output_file},
            runtime_seconds=perf_counter() - run_started,
        )

        save_json(manifest, run_directory / "run_manifest.json")

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
        help=(
            "JSON file containing a list of calendar events. Omitted entirely means no calendar access (CTX0); pass a file with an empty list "
            "for an available-but-empty calendar."
        ),
    )
    parser.add_argument("--calendar-source", required=True)
    parser.add_argument("--calendar-retrieved-at", required=True)
    parser.add_argument("--calendar-window-start", required=True)
    parser.add_argument("--calendar-window-end", required=True)
    parser.add_argument(
        "--forecast-run-number",
        type=int,
        default=None,
        help="Which fc_<val|test>_<number> run to read. Defaults to the latest one for the given split.",
    )
    parser.add_argument(
        "--analysis-run-number",
        type=int,
        default=None,
        help="Which numerical_analysis an_<number> run to read. Defaults to the latest one.",
    )

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
        calendar_source_available=args.calendar_events is not None,
        calendar_source=args.calendar_source,
        calendar_retrieved_at=args.calendar_retrieved_at,
        calendar_window_start=args.calendar_window_start,
        calendar_window_end=args.calendar_window_end,
        forecast_run_number=args.forecast_run_number,
        analysis_run_number=args.analysis_run_number,
        calendar_events_file=args.calendar_events,
    )


if __name__ == "__main__":
    main()


