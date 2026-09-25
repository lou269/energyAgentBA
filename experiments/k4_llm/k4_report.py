# conda activate forecasting-env
# python -m experiments.k4_llm.k4_report [run_directory] [sequence_run_directory]

import json
from pathlib import Path

import pandas as pd

from experiments.common.evaluation import (
    summarize_classification_detection,
    summarize_mae_before_after,
)
from experiments.common.harness import COMPARISON_SUMMARY_FILE
from experiments.common.standard_config import LOCAL_TIMEZONE, PROJECT_CONFIG
from experiments.k4_llm.k4_config import RESULTS_FILE, RUN_PREFIX, SEQUENCE_RUN_PREFIX
from experiments.k4_llm.k4_evaluation import (
    summarize_cases,
    summarize_classes,
    summarize_combined,
    summarize_models,
)
from src.common.timestamps import local_midnight_utc
from src.pipeline.io import (
    RAW_SUBDIR,
    df_to_csv,
    optional_run_directory_from_argv,
    read_raw_json,
    user_output_directory,
)


def export_explanations_for_rating(run_dir: Path) -> Path:
    rows = []

    for raw_file in sorted((run_dir / RAW_SUBDIR).glob("*.jsonl")):
        for line in raw_file.read_text().splitlines():
            record = json.loads(line)

            if record["output"] is None:
                continue

            rows.append(
                {
                    "model": record["model"],
                    "case_id": record["case_id"],
                    "repetition": record["repetition"],
                    "expected_classification": record["expected_classification"],
                    "classification": record["output"]["classification"],
                    "explanation": record["output"]["explanation"],
                    "rubric_score": "",
                }
            )

    output_directory = user_output_directory(run_dir)
    df_to_csv(pd.DataFrame(rows), output_directory, "explanation_ratings_template")

    return output_directory / "explanation_ratings_template.csv"


def main() -> None:
    k4_output_dir = PROJECT_CONFIG.k4_output_dir

    single_case_summary = None
    single_run_dir = optional_run_directory_from_argv(k4_output_dir, RUN_PREFIX, 1)

    if single_run_dir is not None:
        results = pd.read_csv(single_run_dir / RAW_SUBDIR / f"{RESULTS_FILE}.csv")

        single_case_summary = summarize_models(results)
        single_output_dir = user_output_directory(single_run_dir)
        df_to_csv(single_case_summary, single_output_dir, "model_comparison")
        df_to_csv(summarize_cases(results), single_output_dir, "case_breakdown")
        df_to_csv(summarize_classes(results), single_output_dir, "class_breakdown")
        export_explanations_for_rating(single_run_dir)

        print("=== Single-case comparison ===")
        print(single_case_summary.to_string(index=False))
    else:
        print(f"No K4 single-case run found under {k4_output_dir}, skipped.")

    detection = mae_before_after = None
    sequence_run_dir = optional_run_directory_from_argv(
        k4_output_dir, SEQUENCE_RUN_PREFIX, 2
    )

    if sequence_run_dir is not None:
        k4_config = read_raw_json(sequence_run_dir, "run_config")["k4_config"]
        comparison = pd.read_csv(
            sequence_run_dir
            / RAW_SUBDIR
            / k4_config["sequence_target_kind"]
            / COMPARISON_SUMMARY_FILE,
            parse_dates=["decision_time"],
        )

        cutover_time = local_midnight_utc(
            k4_config["sequence_cutover_date"], LOCAL_TIMEZONE
        )
        detection = summarize_classification_detection(
            comparison, cutover_time, k4_config["sequence_target_classification"]
        )
        mae_before_after = summarize_mae_before_after(comparison, cutover_time)
        sequence_output_dir = user_output_directory(sequence_run_dir)
        df_to_csv(detection, sequence_output_dir, "sequence_detection")
        df_to_csv(mae_before_after, sequence_output_dir, "sequence_mae_before_after")

        print("\n=== Sequence comparison (standard scenario with adaption) ===")
        print(detection.to_string(index=False))
        print()
        print(mae_before_after.to_string(index=False))
    else:
        print(f"No K4 sequence run found under {k4_output_dir}, skipped.")

    if (
        single_case_summary is not None
        and detection is not None
        and mae_before_after is not None
    ):
        combined = summarize_combined(single_case_summary, detection, mae_before_after)
        df_to_csv(combined, k4_output_dir, "k4_combined_comparison")

        print("\n=== Combined (single case + sequence per model) ===")
        print(combined.to_string(index=False))


if __name__ == "__main__":
    main()
