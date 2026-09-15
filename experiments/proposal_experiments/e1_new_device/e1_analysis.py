# conda run -n forecasting-env python -m experiments.proposal_experiments.e1_new_device.e1_analysis
# optional: <run_directory> als Argument

import sys
from pathlib import Path

import pandas as pd

from experiments.proposal_experiments.config import E1Config
from experiments.proposal_experiments.shared_analysis import summarize_classification_detection, summarize_mae_before_after
from src.common.timestamps import parse_utc_timestamp
from src.pipeline.io import df_to_csv, find_run_directory

OUTPUT_DIR = Path(__file__).parent / "output"


def _resolve_run_directory() -> Path:
    if len(sys.argv) == 2:
        return Path(sys.argv[1])

    if len(sys.argv) > 2:
        raise SystemExit("usage: e1_analysis.py [run_directory]")

    latest_run = find_run_directory(OUTPUT_DIR, prefix="e1")
    if latest_run is None:
        raise SystemExit(f"no e1_XXX run found under {OUTPUT_DIR} - pass a run_directory explicitly.")

    return latest_run[1]



def main() -> None:
    run_directory = _resolve_run_directory()
    e1_config = E1Config()
    cutover_time = parse_utc_timestamp(e1_config.cutover_time, "E1Config.cutover_time")

    comparison = pd.read_csv(run_directory / "comparison_summary.csv", parse_dates=["decision_time"])

    detection = summarize_classification_detection(comparison, cutover_time, "new_pattern")
    mae_before_after = summarize_mae_before_after(comparison, cutover_time)

    df_to_csv(detection, run_directory, "e1_new_pattern_detection")
    df_to_csv(mae_before_after, run_directory, "e1_mae_before_after")


    print(detection.to_string(index=False))
    print()
    print(mae_before_after.to_string(index=False))


if __name__ == "__main__":
    main()



