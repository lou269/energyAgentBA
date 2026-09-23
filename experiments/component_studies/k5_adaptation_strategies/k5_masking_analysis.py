# conda activate forecasting-env
# python -m experiments.component_studies.k5_adaptation_strategies.k5_masking_analysis [run_directory]

import sys

import pandas as pd

from experiments.component_studies.k5_adaptation_strategies.k5_config import K5_MASKED_CLASSIFICATIONS, K5_MASKING_EARLY_DAYS
from experiments.component_studies.k5_adaptation_strategies.k5_masking_evaluation import pair_masking, summarize_masking
from experiments.proposal_experiments.shared_analysis import with_mean_over_cutovers
from src.config.project_config import ProjectConfig
from src.pipeline.io import RAW_SUBDIR, df_to_csv, resolve_run_directory


def main() -> None:
    run_directory = resolve_run_directory(ProjectConfig().k5_output_dir, "k5_mask", sys.argv[1] if len(sys.argv) > 1 else None)

    results = pd.read_csv(run_directory / RAW_SUBDIR / "k5_mask_results.csv", dtype={"cutover_date": str})
    decisions = pd.read_csv(run_directory / RAW_SUBDIR / "k5_mask_decisions.csv", dtype={"cutover_date": str})

    paired = pair_masking(results, decisions, K5_MASKED_CLASSIFICATIONS)
    summary = with_mean_over_cutovers(summarize_masking(paired, K5_MASKING_EARLY_DAYS), ["kind", "phase"])
    df_to_csv(summary, run_directory, "k5_mask_summary")

    print(f"replay trifft SYS2 an {paired['replay_matches_sys2'].mean():.1%} der Tage")
    print(summary.loc[summary["cutover_date"].eq("mean")].to_string(index=False))


if __name__ == "__main__":
    main()