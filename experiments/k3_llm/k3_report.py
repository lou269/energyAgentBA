# conda activate forecasting-env
# python -m experiments.k3_llm.k3_report [run_directory] [sequence_run_directory]

import pandas as pd

from experiments.common.standard_config import PROJECT_CONFIG
from experiments.k3_llm.k3_config import (
    RESULTS_FILE,
    RUN_PREFIX,
    SEQUENCE_RESULTS_FILE,
    SEQUENCE_RUN_PREFIX,
)
from experiments.k3_llm.k3_evaluation import (
    summarize_cases,
    summarize_classes,
    summarize_combined,
    summarize_models,
    summarize_sequence,
)
from src.pipeline.io import (
    RAW_SUBDIR,
    df_to_csv,
    optional_run_directory_from_argv,
    user_output_directory,
)


def main() -> None:
    k3_output_dir = PROJECT_CONFIG.k3_output_dir

    single_case_summary = None
    single_run_dir = optional_run_directory_from_argv(k3_output_dir, RUN_PREFIX, 1)

    if single_run_dir is not None:
        results = pd.read_csv(single_run_dir / RAW_SUBDIR / f"{RESULTS_FILE}.csv")

        single_case_summary = summarize_models(results)
        single_output_dir = user_output_directory(single_run_dir)
        df_to_csv(single_case_summary, single_output_dir, "model_comparison")
        df_to_csv(summarize_cases(results), single_output_dir, "case_breakdown")
        df_to_csv(summarize_classes(results), single_output_dir, "class_breakdown")

        print("=== Single-case comparison ===")
        print(single_case_summary.to_string(index=False))
    else:
        print(f"No K3 single-case run found under {k3_output_dir}, skipped.")

    sequence = None
    sequence_run_dir = optional_run_directory_from_argv(
        k3_output_dir, SEQUENCE_RUN_PREFIX, 2
    )

    if sequence_run_dir is not None:
        sequence_results = pd.read_csv(
            sequence_run_dir / RAW_SUBDIR / f"{SEQUENCE_RESULTS_FILE}.csv",
            dtype={"cutover_date": str},
        )
        sequence = summarize_sequence(sequence_results)
        sequence_output_dir = user_output_directory(sequence_run_dir)
        df_to_csv(sequence.events, sequence_output_dir, "sequence_events")
        df_to_csv(sequence.models, sequence_output_dir, "sequence_models")

        print("\n=== Sequence comparison (standard scenarios with adaption) ===")
        print(sequence.events.to_string(index=False))
        print()
        print(sequence.models.to_string(index=False))
    else:
        print(f"No K3 sequence run found under {k3_output_dir}, skipped.")

    if single_case_summary is not None and sequence is not None:
        combined = summarize_combined(single_case_summary, sequence.models)
        df_to_csv(combined, k3_output_dir, "k3_combined_comparison")

        print("\n=== Combined (single case + sequence per model) ===")
        print(combined.to_string(index=False))


if __name__ == "__main__":
    main()
