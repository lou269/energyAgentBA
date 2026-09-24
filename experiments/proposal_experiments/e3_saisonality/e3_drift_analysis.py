# conda run -n forecasting-env python -m experiments.proposal_experiments.e3_saisonality.e3_drift_analysis
# optional: <run_directory> als Argument

import sys

import pandas as pd

from src.config.project_config import ProjectConfig
from src.pipeline.io import (
    RAW_SUBDIR,
    df_to_csv,
    resolve_run_directory,
    user_output_directory,
)


def main() -> None:
    run_directory = resolve_run_directory(
        ProjectConfig().e3_output_dir,
        "e3_drift",
        sys.argv[1] if len(sys.argv) > 1 else None,
    )

    comparison = pd.read_csv(
        run_directory / RAW_SUBDIR / "comparison_summary.csv",
        parse_dates=["decision_time"],
    )
    anomaly = pd.read_csv(
        run_directory / RAW_SUBDIR / "SYS3" / "anomaly.csv",
        parse_dates=["decision_time"],
    )

    merged = comparison.merge(
        anomaly[["decision_time", "dominant_scale", "anomaly_level"]],
        on="decision_time",
        how="left",
    )

    # Kernfrage: bleibt long_term-dominante Drift normal/unknown statt new_pattern
    scale_classification = (
        merged.groupby(["dominant_scale", "classification"], dropna=False)
        .size()
        .reset_index(name="days")
        .sort_values(["dominant_scale", "days"], ascending=[True, False])
    )

    df_to_csv(
        scale_classification,
        user_output_directory(run_directory),
        "e3_drift_scale_vs_classification",
    )

    print(scale_classification.to_string(index=False))


if __name__ == "__main__":
    main()
