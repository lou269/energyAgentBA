# conda activate forecasting-env
# python -m experiments.component_studies.k5_adaptation_strategies.k5_analysis [run_directory]

import sys

import pandas as pd

from experiments.component_studies.k5_adaptation_strategies.k5_config import K5Config
from experiments.component_studies.k5_adaptation_strategies.k5_evaluation import error_curve, pair_with_none, summarize_after_trigger
from experiments.proposal_experiments.shared_analysis import with_mean_over_cutovers
from src.config.project_config import ProjectConfig
from src.pipeline.io import RAW_SUBDIR, df_to_csv, resolve_run_directory


def main() -> None:
    run_directory = resolve_run_directory(ProjectConfig().k5_output_dir, "k5", sys.argv[1] if len(sys.argv) > 1 else None)

    results = pd.read_csv(run_directory / RAW_SUBDIR / "k5_results.csv", dtype={"cutover_date": str})
    paired = pair_with_none(results, K5Config().evaluation_days)

    summary = with_mean_over_cutovers(summarize_after_trigger(paired), ["kind", "trigger_day", "strategy"])
    df_to_csv(summary, run_directory, "k5_after_trigger")
    df_to_csv(error_curve(paired), run_directory, "k5_error_curve")

    print(summary.loc[summary["cutover_date"].eq("mean")].to_string(index=False))


if __name__ == "__main__":
    main()