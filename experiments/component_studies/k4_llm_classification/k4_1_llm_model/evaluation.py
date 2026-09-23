# conda activate forecasting-env
# python -m experiments.component_studies.k4_llm_classification.k4_1_llm_model.evaluation
# optional: --run <k4-Nummer> --sequence-run <k4_seq-Nummer>

import argparse
import json
from pathlib import Path

import pandas as pd

from experiments.component_studies.k4_llm_classification.k4_1_llm_model.evaluation_cases import EXPECTED_EVIDENCE_PATHS
from experiments.proposal_experiments.e_config import E1Config
from experiments.proposal_experiments.shared_analysis import summarize_classification_detection, summarize_mae_before_after
from src.common.timestamps import local_midnight_utc
from src.config.project_config import ProjectConfig
from src.llm.llm_schema import CLASSIFICATIONS
from src.pipeline.io import RAW_SUBDIR, df_to_csv, find_run_directory


''' EBENE 1 - billiger Einzelfall-Vergleich (synthetische Fälle, isoliert) '''

def _grounding_coverage(row: pd.Series) -> float | None:
    if not row["valid"]:
        return None

    expected_paths = EXPECTED_EVIDENCE_PATHS.get(row["case_id"])
    if not expected_paths:
        return None

    cited_paths = set(row["evidence_paths"].split(";")) if isinstance(row["evidence_paths"], str) and row["evidence_paths"] else set()
    return len(cited_paths & expected_paths) / len(expected_paths)


def summarize_classes(results: pd.DataFrame) -> pd.DataFrame:
    rows = []

    for model_id, subset in results.groupby("model_id"):
        for label in sorted(CLASSIFICATIONS):
            predicted_as_label = subset["classification"] == label
            expected_as_label = subset["expected_classification"] == label

            if expected_as_label.sum() == 0:
                continue  # Klasse kommt in diesem Lauf nicht als Gold-Label vor, sonst verzerrt eine 0-Klasse den Makro-Durchschnitt

            true_positive = (predicted_as_label & expected_as_label).sum()
            false_positive = (predicted_as_label & ~expected_as_label).sum()
            false_negative = (~predicted_as_label & expected_as_label).sum()

            precision = true_positive / (true_positive + false_positive) if (true_positive + false_positive) else 0.0
            recall = true_positive / (true_positive + false_negative) if (true_positive + false_negative) else 0.0
            f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0

            rows.append({
                "model_id": model_id,
                "classification": label,
                "precision": precision,
                "recall": recall,
                "f1": f1,
            })

    return pd.DataFrame(rows)


def summarize_models(results: pd.DataFrame) -> pd.DataFrame:
    results = results.copy()
    results["grounding_coverage"] = results.apply(_grounding_coverage, axis=1)

    summary = results.groupby(["model_id", "model"], as_index=False).agg(
        n_attempts=("case_id", "count"),
        valid_rate=("valid", "mean"),
        accuracy=("correct", "mean"),
        mean_attempt_count=("attempt_count", "mean"),
        mean_generation_seconds=("generation_seconds", "mean"),
        p50_generation_seconds=("generation_seconds", lambda values: values.quantile(0.5)),
        p95_generation_seconds=("generation_seconds", lambda values: values.quantile(0.95)),
        mean_grounding_coverage=("grounding_coverage", "mean"),
    )

    macro_f1 = summarize_classes(results).groupby("model_id")["f1"].mean().rename("macro_f1")
    summary = summary.merge(macro_f1, on="model_id", how="left")


    valid_results = results[results["valid"]]
    per_case_agreement = valid_results.groupby(["model_id", "case_id"])["classification"].nunique()
    stability_rate = (per_case_agreement == 1).groupby("model_id").mean().rename("stability_rate")
    summary = summary.merge(stability_rate, on="model_id", how="left")

    return summary.sort_values("macro_f1", ascending=False)


def summarize_cases(results: pd.DataFrame) -> pd.DataFrame:
    return results.groupby(["model_id", "case_id", "expected_classification"], as_index=False).agg(
        n_repetitions=("repetition", "count"),
        accuracy=("correct", "mean"),
        classifications=("classification", lambda values: ",".join(sorted(v for v in values if pd.notna(v)))),
    )


def export_explanations_for_rating(run_dir: Path) -> Path:

    rows = []

    for raw_file in sorted((run_dir / RAW_SUBDIR).glob("*.jsonl")):
        for line in raw_file.read_text().splitlines():
            record = json.loads(line)

            if record["output"] is None:
                continue

            rows.append({
                "model": record["model"],
                "case_id": record["case_id"],
                "repetition": record["repetition"],
                "expected_classification": record["expected_classification"],
                "classification": record["output"]["classification"],
                "explanation": record["output"]["explanation"],
                "rubric_score": "",
            })

    df_to_csv(pd.DataFrame(rows), run_dir, "explanation_ratings_template")

    return run_dir / "explanation_ratings_template.csv"


''' EBENE 2 - echter Sequenzvergleich (E1-Geräteszenario, Tag für Tag mit Adaption) '''

def summarize_sequence(comparison: pd.DataFrame, cutover_date: str, local_timezone: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    cutover_time = local_midnight_utc(cutover_date, local_timezone)

    detection = summarize_classification_detection(comparison, cutover_time, "new_pattern", local_timezone)
    mae_before_after = summarize_mae_before_after(comparison, cutover_time)

    return detection, mae_before_after


''' ÜBERSICHT 3 - Ebene 1 und Ebene 2 pro Modell nebeneinander '''

def summarize_combined(
    single_case_summary: pd.DataFrame,
    detection: pd.DataFrame,
    mae_before_after: pd.DataFrame,
) -> pd.DataFrame:
    mae_after_event = mae_before_after.loc[mae_before_after["period"] == "after_event", ["config", "mean_mae_w"]].rename(
        columns={"config": "model_id", "mean_mae_w": "sequence_mae_after_event_w"}
    )

    sequence_summary = detection.rename(columns={"config": "model_id"})[
        ["model_id", "target_classification_days", "days_to_first_detection", "adaption_count"]
    ].merge(mae_after_event, on="model_id", how="left")

    single_case_columns = single_case_summary[
        ["model_id", "model", "accuracy", "macro_f1", "mean_grounding_coverage", "stability_rate", "mean_generation_seconds"]
    ]

    return single_case_columns.merge(sequence_summary, on="model_id", how="outer").sort_values("macro_f1", ascending=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="Aggregate K4 results (Einzelfall- und Sequenz-Vergleich).")
    parser.add_argument("--run", type=int, help="k4_<number> Einzelfall-Lauf. Standard: der neueste.")
    parser.add_argument("--sequence-run", type=int, help="k4_seq_<number> Sequenz-Lauf. Standard: der neueste.")

    arguments = parser.parse_args()
    k4_output_dir = ProjectConfig().k4_output_dir

    single_case_summary = None
    single_found = find_run_directory(k4_output_dir, prefix="k4", number=arguments.run)

    if single_found is not None:
        _, single_run_dir = single_found
        results = pd.read_csv(single_run_dir / RAW_SUBDIR / "results.csv")

        single_case_summary = summarize_models(results)
        df_to_csv(single_case_summary, single_run_dir, "model_comparison")
        df_to_csv(summarize_cases(results), single_run_dir, "case_breakdown")
        df_to_csv(summarize_classes(results), single_run_dir, "class_breakdown")
        export_explanations_for_rating(single_run_dir)

        print("=== Einzelfall-Vergleich (billiger Vorab-Check) ===")
        print(single_case_summary.to_string(index=False))
    else:
        print(f"Kein K4-Einzelfall-Lauf unter {k4_output_dir} gefunden - übersprungen.")

    detection = mae_before_after = None
    sequence_found = find_run_directory(k4_output_dir, prefix="k4_seq", number=arguments.sequence_run)

    if sequence_found is not None:
        _, sequence_run_dir = sequence_found
        comparison = pd.read_csv(sequence_run_dir / RAW_SUBDIR / "comparison_summary.csv", parse_dates=["decision_time"])

        detection, mae_before_after = summarize_sequence(comparison, E1Config().cutover_date, ProjectConfig().timezone)
        df_to_csv(detection, sequence_run_dir, "sequence_detection")
        df_to_csv(mae_before_after, sequence_run_dir, "sequence_mae_before_after")

        print("\n=== Sequenz-Vergleich (E1, echter Lauf mit Adaption) ===")
        print(detection.to_string(index=False))
        print()
        print(mae_before_after.to_string(index=False))
    else:
        print(f"Kein K4-Sequenz-Lauf unter {k4_output_dir} gefunden - übersprungen.")

    if single_case_summary is not None and detection is not None and mae_before_after is not None:
        combined = summarize_combined(single_case_summary, detection, mae_before_after)
        df_to_csv(combined, k4_output_dir, "k4_combined_comparison")

        print("\n=== Gesamtübersicht (Einzelfall + Sequenz je Modell) ===")
        print(combined.to_string(index=False))


if __name__ == "__main__":
    main()