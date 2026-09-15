# conda run -n forecasting-env python -m experiments.proposal_experiments.e2_absence.e2_analysis <run_directory>

import sys
from pathlib import Path

import pandas as pd

from experiments.proposal_experiments.e_config import E2Config
from experiments.proposal_experiments.e2_absence.e2_selection import load_calendar_events, resolve_absence_window
from experiments.proposal_experiments.shared_analysis import summarize_classification_detection, summarize_mae_before_after
from src.pipeline.io import df_to_csv


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: e2_analysis.py <run_directory>")

    run_directory = Path(sys.argv[1])
    e2_config = E2Config()

    calendar_events = load_calendar_events(e2_config.calendar_events_file)
    window_start, _window_end = resolve_absence_window(calendar_events, e2_config.active_absence_event_id)

    comparison = pd.read_csv(run_directory / "e2_comparison_summary.csv", parse_dates=["decision_time"])

    detection = summarize_classification_detection(comparison, window_start, "absence")
    mae_before_after = summarize_mae_before_after(comparison, window_start)

    df_to_csv(detection, run_directory, "e2_absence_detection")
    df_to_csv(mae_before_after, run_directory, "e2_mae_before_after")

    print(detection.to_string(index=False))
    print()
    print(mae_before_after.to_string(index=False))


if __name__ == "__main__":
    main()