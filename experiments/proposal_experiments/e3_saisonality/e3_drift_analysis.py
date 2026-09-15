# conda run -n forecasting-env python -m experiments.proposal_experiments.e3_saisonality.e3_drift_analysis
# optional: <run_directory> als Argument

import sys
from pathlib import Path

import pandas as pd

from src.pipeline.io import df_to_csv, find_run_directory

OUTPUT_DIR = Path(__file__).parent / "output"


def _resolve_run_directory() -> Path:
    if len(sys.argv) == 2:
        return Path(sys.argv[1])

    if len(sys.argv) > 2:
        raise SystemExit("usage: e3_drift_analysis.py [run_directory]")

    latest_run = find_run_directory(OUTPUT_DIR, prefix="e3_drift")
    if latest_run is None:
        raise SystemExit(f"no e3_drift_XXX run found under {OUTPUT_DIR} - pass a run_directory explicitly.")

    return latest_run[1]


def main() -> None:
    run_directory = _resolve_run_directory()

    comparison = pd.read_csv(run_directory / "comparison_summary.csv", parse_dates=["decision_time"])
    anomaly = pd.read_csv(run_directory / "SYS3" / "anomaly.csv", parse_dates=["decision_time"])

    merged = comparison.merge(anomaly[["decision_time", "dominant_scale", "anomaly_level"]], on="decision_time", how="left")

    # Kernfrage: bleibt long_term-dominante Drift normal/unknown statt new_pattern
    scale_classification = (
        merged.groupby(["dominant_scale", "classification"], dropna=False)
        .size()
        .reset_index(name="days")
        .sort_values(["dominant_scale", "days"], ascending=[True, False])
    )

    df_to_csv(scale_classification, run_directory, "e3_drift_scale_vs_classification")

    print(scale_classification.to_string(index=False))


if __name__ == "__main__":
    main()
