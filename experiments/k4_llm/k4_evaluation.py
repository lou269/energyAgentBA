from dataclasses import dataclass

import pandas as pd

from experiments.common.evaluation import (
    FIRST_ANALYZED_DAY,
    add_days_since_cutover,
    count_notifications,
    merge_cycle_days,
    pair_with_control,
)
from experiments.common.standard_config import (
    GOLDSTANDARD_EXPECTED,
    NOTIFICATION_CLASSIFICATIONS,
    NOTIFICATION_PERIOD_DAYS,
)
from experiments.k4_llm.k4_cases import EXPECTED_EVIDENCE_PATHS
from src.llm.llm_schema import CLASSIFICATIONS

# Ebene 2: jedes Modell läuft als eigene Config, gepaart wird mit seinem eigenen Kontrolllauf
SEQUENCE_PAIR_KEYS = ["config", "days_since_cutover"]

SEQUENCE_RESULT_COLUMNS = [
    "kind",
    "cutover_date",
    "config",
    "decision_time",
    "classification",
    "anomaly_level",
    "sustained_drift",
    "alarm",
    "gate_open",
    "new_pattern",
    "reference_reset",
    "error",
]

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


def read_sequence_results(
    summary: pd.DataFrame, anomaly: pd.DataFrame, *, kind: str, cutover_date: str
) -> pd.DataFrame:
    results = merge_cycle_days(summary, anomaly).assign(
        kind=kind, cutover_date=cutover_date
    )

    return results[SEQUENCE_RESULT_COLUMNS]


@dataclass(frozen=True)
class SequenceSummary:
    events: pd.DataFrame
    models: pd.DataFrame


def summarize_sequence(results: pd.DataFrame) -> SequenceSummary:
    """Je Modell und Ereignis-Art ab Cutover: erster Tag mit der erwarteten Klasse aus GOLDSTANDARD_EXPECTED an einem Tag,
    an dem nur das Ereignis das Gate öffnet, dazu die Resets. Je Modell: erkannte Arten, Meldungen und Resets im Kontrolllauf,
    Tage mit offenem Gate (in SYS3 je ein LLM-Aufruf) und Tage ohne gültiges Ergebnis über alle Arten
    """
    results = add_days_since_cutover(results)
    paired = pair_with_control(results, SEQUENCE_PAIR_KEYS)
    after_cutover = paired.loc[paired["days_since_cutover"].ge(FIRST_ANALYZED_DAY)]

    # Stärke steht im Namen (peak_6, ramp_56), erwartet wird je Art ohne Stärke
    expected = after_cutover["kind"].str.partition("_")[0].map(GOLDSTANDARD_EXPECTED)
    correct_days = after_cutover["days_since_cutover"].where(
        after_cutover["event_gate_open"] & after_cutover["classification"].eq(expected)
    )
    events = (
        after_cutover.assign(expected_classification=expected, correct_day=correct_days)
        .groupby(["config", "kind", "expected_classification"], as_index=False)
        .agg(
            event_gate_open_days=("event_gate_open", "sum"),
            correct_days=("correct_day", "count"),
            first_correct_day=("correct_day", "min"),
            resets=("reference_reset", "sum"),
        )
        .astype({"first_correct_day": "Int64"})
    )

    control = results.loc[results["kind"].eq("control")]
    control_summary = count_notifications(
        control,
        ["config"],
        notification_classes=NOTIFICATION_CLASSIFICATIONS,
        period_days=NOTIFICATION_PERIOD_DAYS,
    ).merge(
        control.groupby("config", as_index=False).agg(
            control_resets=("reference_reset", "sum")
        ),
        on="config",
    )

    models = (
        results.assign(failed=results["error"].notna())
        .groupby("config", as_index=False)
        .agg(gate_open_days=("gate_open", "sum"), failed_days=("failed", "sum"))
        .merge(
            events.assign(detected=events["correct_days"].gt(0))
            .groupby("config", as_index=False)
            .agg(detected_kinds=("detected", "sum"), event_kinds=("kind", "size")),
            on="config",
        )
        .merge(
            control_summary[
                ["config", "notification_days", "unknown_days", "control_resets"]
            ].rename(
                columns={
                    "notification_days": "control_notification_days",
                    "unknown_days": "control_unknown_days",
                }
            ),
            on="config",
        )
    )

    return SequenceSummary(events=events, models=models)


def summarize_combined(
    single_case_summary: pd.DataFrame, sequence_models: pd.DataFrame
) -> pd.DataFrame:
    """Beide Ebenen je Modell nebeneinander"""
    sequence_summary = sequence_models.rename(columns={"config": "model_id"})

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
