import pandas as pd

from experiments.k4_llm.k4_cases import EXPECTED_EVIDENCE_PATHS
from src.llm.llm_schema import CLASSIFICATIONS

# Ebene 1: billiger Einzelfall-Vergleich auf synthetischen Fällen


def _grounding_coverage(row: pd.Series) -> float | None:
    if not row["valid"]:
        return None

    expected_paths = EXPECTED_EVIDENCE_PATHS.get(row["case_id"])
    if not expected_paths:
        return None

    cited_paths = (
        set(row["evidence_paths"].split(";"))
        if isinstance(row["evidence_paths"], str) and row["evidence_paths"]
        else set()
    )
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

            precision = (
                true_positive / (true_positive + false_positive)
                if (true_positive + false_positive)
                else 0.0
            )
            recall = (
                true_positive / (true_positive + false_negative)
                if (true_positive + false_negative)
                else 0.0
            )
            f1 = (
                2 * precision * recall / (precision + recall)
                if (precision + recall)
                else 0.0
            )

            rows.append(
                {
                    "model_id": model_id,
                    "classification": label,
                    "precision": precision,
                    "recall": recall,
                    "f1": f1,
                }
            )

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
        p50_generation_seconds=(
            "generation_seconds",
            lambda values: values.quantile(0.5),
        ),
        p95_generation_seconds=(
            "generation_seconds",
            lambda values: values.quantile(0.95),
        ),
        mean_grounding_coverage=("grounding_coverage", "mean"),
    )

    macro_f1 = (
        summarize_classes(results).groupby("model_id")["f1"].mean().rename("macro_f1")
    )
    summary = summary.merge(macro_f1, on="model_id", how="left")

    valid_results = results[results["valid"]]
    per_case_agreement = valid_results.groupby(["model_id", "case_id"])[
        "classification"
    ].nunique()
    stability_rate = (
        (per_case_agreement == 1).groupby("model_id").mean().rename("stability_rate")
    )
    summary = summary.merge(stability_rate, on="model_id", how="left")

    return summary.sort_values("macro_f1", ascending=False)


def summarize_cases(results: pd.DataFrame) -> pd.DataFrame:
    return results.groupby(
        ["model_id", "case_id", "expected_classification"], as_index=False
    ).agg(
        n_repetitions=("repetition", "count"),
        accuracy=("correct", "mean"),
        classifications=(
            "classification",
            lambda values: ",".join(sorted(v for v in values if pd.notna(v))),
        ),
    )


# Ebene 2 (Sequenz auf dem Standard-Szenario) rechnet common/evaluation, hier nur beide Ebenen je Modell nebeneinander


def summarize_combined(
    single_case_summary: pd.DataFrame,
    detection: pd.DataFrame,
    mae_before_after: pd.DataFrame,
) -> pd.DataFrame:
    mae_after_event = mae_before_after.loc[
        mae_before_after["period"] == "after_event", ["config", "mean_mae_w"]
    ].rename(columns={"config": "model_id", "mean_mae_w": "sequence_mae_after_event_w"})

    sequence_summary = detection.rename(columns={"config": "model_id"})[
        [
            "model_id",
            "target_classification_days",
            "first_detection_day",
            "adaption_count",
        ]
    ].merge(mae_after_event, on="model_id", how="left")

    single_case_columns = single_case_summary[
        [
            "model_id",
            "model",
            "accuracy",
            "macro_f1",
            "mean_grounding_coverage",
            "stability_rate",
            "mean_generation_seconds",
        ]
    ]

    return single_case_columns.merge(
        sequence_summary, on="model_id", how="outer"
    ).sort_values("macro_f1", ascending=False)
