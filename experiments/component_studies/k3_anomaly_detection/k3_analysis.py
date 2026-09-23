# conda activate forecasting-env
# python -m experiments.component_studies.k3_anomaly_detection.k3_analysis [run_directory]

import sys
from pathlib import Path

import pandas as pd

from docs.plots.plot_k3_referenzfenster import build_k3_plots
from experiments.component_studies.k3_anomaly_detection.k3_evaluation import (
    pair_with_control,
    score_shift_by_week,
    summarize_closed_loop,
    summarize_control,
    summarize_event_response,
    with_mean_over_cutovers,
)
from src.config.config_forecasting import NumericalAnalysisConfig
from src.pipeline.io import df_to_csv, resolve_run_directory

OUTPUT_DIR = Path(__file__).parent / "output"


def main() -> None:
    run_directory = resolve_run_directory(OUTPUT_DIR, "k3", sys.argv[1] if len(sys.argv) > 1 else None)
    unusual_threshold = NumericalAnalysisConfig().unusual_threshold

    results = pd.read_csv(run_directory / "k3_results.csv", dtype={"cutover_date": str})
    isolated = results.loc[results["mode"].eq("isolated")]

    control_summary = summarize_control(isolated)
    paired = pair_with_control(isolated)

    tables = {
        "k3_control_summary": with_mean_over_cutovers(control_summary, ["variant", "phase"]),
        "k3_event_response": with_mean_over_cutovers(summarize_event_response(paired, unusual_threshold), ["variant"]),
        "k3_closed_loop": with_mean_over_cutovers(summarize_closed_loop(results), ["variant"]),
    }

    for name, table in tables.items():
        df_to_csv(table, run_directory, name)
        print(name)
        print(table.loc[table["cutover_date"].eq("mean")].to_string(index=False))
        print()

    build_k3_plots(control_summary, score_shift_by_week(paired), run_directory, unusual_threshold=unusual_threshold)


if __name__ == "__main__":
    main()