from __future__ import annotations

import gc
import json
import subprocess
from pathlib import Path

import pandas as pd

from experiments.prototypes.vertical_slice.llm.llm_client_new import (
    interpret_structured_state,
)

from experiments.prototypes.vertical_slice.llm_evaluation.evaluation_cases import (
    build_evaluation_cases,
)
from experiments.prototypes.vertical_slice.llm_evaluation.evaluator import (
    evaluate_output,
)


LLM_MODELS = [
    "qwen3:4b",
    "qwen3:8b",
    "qwen3.5:9b",
    "llama3.1:8b",
]

LLM_OUTPUT_LANGUAGE = "English"
LLM_SEED = 42
LLM_MAX_ATTEMPTS = 2


RESULTS_DIR = (
    Path(__file__).resolve().parent
    / "results"
)

RAW_RESULTS_FILE = (
    RESULTS_DIR
    / "llm_evaluation_raw.jsonl"
)

CASE_RESULTS_FILE = (
    RESULTS_DIR
    / "llm_evaluation_cases.csv"
)

SUMMARY_FILE = (
    RESULTS_DIR
    / "llm_evaluation_summary.csv"
)


def _unload_model(
    model: str,
) -> None:
    """
    Unload the Ollama model after its evaluation block.

    This prevents several evaluated models from remaining
    loaded in unified memory at the same time.
    """
    try:
        subprocess.run(
            [
                "ollama",
                "stop",
                model,
            ],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    except OSError:
        pass

    gc.collect()


def run_llm_evaluation(
    base_state: dict,
) -> None:
    RESULTS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    cases = build_evaluation_cases(
        base_state
    )

    evaluation_rows: list[dict] = []

    # Raw results are written immediately.
    # They are not accumulated in RAM.
    with RAW_RESULTS_FILE.open(
        "w",
        encoding="utf-8",
    ) as raw_file:

        for model in LLM_MODELS:
            print(
                f"Starting evaluation model: "
                f"{model}"
            )

            try:
                for case in cases:
                    try:
                        llm_output = (
                            interpret_structured_state(
                                case.structured_state,
                                model=model,
                                output_language=(
                                    LLM_OUTPUT_LANGUAGE
                                ),
                                seed=LLM_SEED,
                                max_attempts=(
                                    LLM_MAX_ATTEMPTS
                                ),
                            )
                        )

                        status = "success"
                        error = None

                    except Exception as exc:
                        llm_output = None
                        status = "error"

                        error = {
                            "type": (
                                type(exc).__name__
                            ),
                            "message": str(exc),
                        }

                    raw_result = {
                        "model": model,
                        "case": case.name,
                        "status": status,
                        "expected_classification": (
                            case.expected_classification
                        ),
                        "structured_state": (
                            case.structured_state
                        ),
                        "llm_output": llm_output,
                        "error": error,
                    }

                    # Write one result immediately.
                    json.dump(
                        raw_result,
                        raw_file,
                        ensure_ascii=False,
                        default=str,
                    )

                    raw_file.write("\n")
                    raw_file.flush()

                    evaluation = evaluate_output(
                        case,
                        status=status,
                        output=llm_output,
                    )

                    evaluation["model"] = model

                    evaluation_rows.append(
                        evaluation
                    )

                    print(
                        f"  {case.name}: "
                        f"{status}"
                    )

                    # Large response no longer needed.
                    del raw_result
                    del llm_output

            finally:
                # Important for a 16 GB Unified
                # Memory machine:
                # release this Ollama model before
                # loading the next one.
                _unload_model(model)

            print(
                f"Finished evaluation model: "
                f"{model}"
            )

    case_results = pd.DataFrame(
        evaluation_rows
    )

    case_results.to_csv(
        CASE_RESULTS_FILE,
        index=False,
    )

    summary = build_summary(
        case_results
    )

    summary.to_csv(
        SUMMARY_FILE,
        index=False,
    )


def build_summary(
    results: pd.DataFrame,
) -> pd.DataFrame:
    rows = []

    for model, model_df in results.groupby(
        "model"
    ):
        valid_df = model_df[
            model_df["valid_output"]
        ]

        valid_cases = len(valid_df)

        row = {
            "model": model,
            "case_count": len(model_df),

            "valid_output_rate": (
                model_df[
                    "valid_output"
                ].mean()
            ),

            "classification_accuracy_all": (
                model_df[
                    "classification_correct"
                ].mean()
            ),

            "classification_accuracy_valid": (
                valid_df[
                    "classification_correct"
                ].mean()
                if valid_cases
                else 0.0
            ),

            "evidence_path_accuracy": (
                valid_df[
                    "evidence_path_accuracy"
                ].mean()
                if valid_cases
                else 0.0
            ),

            "evidence_value_accuracy": (
                valid_df[
                    "evidence_value_accuracy"
                ].mean()
                if valid_cases
                else 0.0
            ),

            "required_evidence_recall": (
                valid_df[
                    "required_evidence_recall"
                ].mean()
                if valid_cases
                else 0.0
            ),

            "forbidden_comparison_rate": (
                valid_df[
                    "forbidden_comparison"
                ].mean()
                if valid_cases
                else 0.0
            ),

            "unsupported_claim_rate": (
                valid_df[
                    "unsupported_claim"
                ].mean()
                if valid_cases
                else 0.0
            ),

            "context_handling_accuracy": (
                valid_df[
                    "context_handling_ok"
                ].mean()
                if valid_cases
                else 0.0
            ),

            "forecast_leakage_rate": (
                valid_df[
                    "forecast_leakage"
                ].mean()
                if valid_cases
                else 0.0
            ),
        }

        rows.append(row)

    summary = pd.DataFrame(
        rows
    )

    return summary.sort_values(
        [
            "classification_accuracy_all",
            "valid_output_rate",
            "context_handling_accuracy",
        ],
        ascending=[
            False,
            False,
            False,
        ],
    ).reset_index(
        drop=True
    )