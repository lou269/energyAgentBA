from dataclasses import dataclass
from typing import cast

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
from experiments.k3_llm.k3_cases import EXPECTED_EVIDENCE_PATHS
from experiments.k3_llm.k3_config import BASELINE_ID, CORRECT_ANSWER_LABEL
from src.evaluation.consistency import missing_evidence_paths
from src.evaluation.text_check import (
    collect_state_values,
    find_device_mentions,
    find_violations,
)
from src.llm.llm_schema import CLASSIFICATIONS
from src.structured_state.structured_state_schema import StructuredState

# Ebene 2: jedes Modell läuft als eigene Config, gepaart wird mit seinem eigenen Kontrolllauf
SEQUENCE_PAIR_KEYS = ["config", "days_since_cutover"]

SEQUENCE_RESULT_COLUMNS = [
    "kind",
    "cutover_date",
    "config",
    "decision_time",
    "analyzed_day",
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
    # die Regel zitiert keine Felder
    if not row["valid"] or row["model_id"] == BASELINE_ID:
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


def _summarize_classes(results: pd.DataFrame) -> pd.DataFrame:
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


def _summarize_models(results: pd.DataFrame) -> pd.DataFrame:
    results = results.copy()
    results["grounding_coverage"] = results.apply(_grounding_coverage, axis=1)

    summary = results.groupby(["model_id", "model"], as_index=False).agg(
        n_attempts=("case_id", "count"),
        correct=("correct", "sum"),
        invalid=("valid", lambda values: values.eq(False).sum()),
        mean_attempt_count=("attempt_count", "mean"),
        mean_generation_seconds=("generation_seconds", "mean"),
        p95_generation_seconds=(
            "generation_seconds",
            lambda values: values.quantile(0.95),
        ),
        mean_grounding_coverage=("grounding_coverage", "mean"),
    )

    macro_f1 = (
        _summarize_classes(results).groupby("model_id")["f1"].mean().rename("macro_f1")
    )
    summary = summary.merge(macro_f1, on="model_id", how="left")

    return summary.sort_values("macro_f1", ascending=False)


def _summarize_cases(results: pd.DataFrame) -> pd.DataFrame:
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


def _case_answers(cases: pd.DataFrame, model_order: list[str]) -> pd.DataFrame:
    # Fall x Modell, nur falsche Antworten stehen als Klasse drin, ungültige bleiben leer
    answers = (
        cases["classifications"]
        .where(cases["accuracy"].lt(1), CORRECT_ANSWER_LABEL)
        .replace("", pd.NA)
    )

    return (
        cases.assign(answer=answers)
        .pivot(
            index=["case_id", "expected_classification"],
            columns="model_id",
            values="answer",
        )[model_order]
        .reset_index()
        .rename_axis(columns=None)
    )


def _rule_deviations(sequence_results: pd.DataFrame) -> pd.DataFrame:
    # vor dem Cutover sind alle Arten gleich, ein Tag steht deshalb einmal mit allen Arten, in denen er abweicht
    rule = sequence_results.loc[
        sequence_results["config"].eq(BASELINE_ID),
        ["kind", "analyzed_day", "classification"],
    ]
    paired = sequence_results.loc[sequence_results["config"].ne(BASELINE_ID)].merge(
        rule, on=["kind", "analyzed_day"], suffixes=("", "_rule")
    )
    differs = (
        paired["classification"].fillna("").ne(paired["classification_rule"].fillna(""))
    )

    return (
        paired.loc[differs]
        .groupby(
            ["config", "analyzed_day", "classification_rule", "classification"],
            as_index=False,
            dropna=False,
            sort=False,
        )
        .agg(kinds=("kind", ", ".join))
        .sort_values(["config", "analyzed_day"], kind="stable")
        .rename(columns={"config": "model_id"})
    )


@dataclass(frozen=True)
class K3Summary:
    models: pd.DataFrame
    cases: pd.DataFrame
    case_answers: pd.DataFrame
    classes: pd.DataFrame
    sequence_models: pd.DataFrame
    events: pd.DataFrame
    rule_deviations: pd.DataFrame


def summarize_k3(results: pd.DataFrame, sequence_results: pd.DataFrame) -> K3Summary:
    single_case = _summarize_models(results)
    cases = _summarize_cases(results)
    sequence = summarize_sequence(sequence_results)
    rule_deviations = _rule_deviations(sequence_results)

    deviation_days = (
        rule_deviations.groupby("model_id")["analyzed_day"]
        .nunique()
        .reindex(sequence.models["config"], fill_value=0)
        .rename("rule_deviation_days")
    )
    sequence_models = sequence.models.merge(
        deviation_days, left_on="config", right_index=True
    ).rename(columns={"config": "model_id"})
    models = single_case.merge(sequence_models, on="model_id", how="outer").sort_values(
        "macro_f1", ascending=False
    )

    return K3Summary(
        models=models,
        cases=cases,
        case_answers=_case_answers(cases, models["model_id"].tolist()),
        classes=_summarize_classes(results),
        sequence_models=sequence_models,
        events=sequence.events,
        rule_deviations=rule_deviations,
    )


TEXT_COLUMNS = ["classification", "explanation", "user_recommendation", "uncertainty"]


@dataclass(frozen=True)
class AnswerTexts:
    single: pd.DataFrame
    sequence: pd.DataFrame


def collect_answer_texts(
    single_answers: pd.DataFrame,
    results: pd.DataFrame,
    sequence_outputs: pd.DataFrame,
    *,
    model_order: list[str],
    sequence_model_id: str,
) -> AnswerTexts:
    case_order = results["case_id"].drop_duplicates().tolist()
    single = (
        single_answers.drop(columns="state")
        .merge(
            results[["model_id", "case_id", "expected_classification", "correct"]],
            on=["model_id", "case_id"],
        )
        .assign(
            case_id=lambda frame: pd.Categorical(
                frame["case_id"], case_order, ordered=True
            ),
            model_id=lambda frame: pd.Categorical(
                frame["model_id"], model_order, ordered=True
            ),
        )
        .sort_values(["case_id", "model_id"])
        .reset_index(drop=True)
    )

    chosen = sequence_outputs.loc[sequence_outputs["config"].eq(sequence_model_id)]
    sequence = (
        chosen.groupby(["analyzed_day"] + TEXT_COLUMNS, as_index=False, sort=False)
        .agg(kinds=("scenario", ", ".join))
        .sort_values("analyzed_day", kind="stable")
        .reset_index(drop=True)
    )

    return AnswerTexts(single=single, sequence=sequence)


@dataclass(frozen=True)
class TextChecks:
    models: pd.DataFrame
    findings: pd.DataFrame


def _check_answer(
    answer: pd.Series,
    state: StructuredState,
    *,
    device_words: tuple[str, ...],
    control_words: tuple[str, ...],
    number_tolerance: float,
    prompt_numbers: tuple[float, ...],
) -> tuple[str, str, str]:
    quantities, date_parts = collect_state_values(state)
    text = " ".join(
        answer[column]
        for column in ["explanation", "user_recommendation", "uncertainty"]
    )
    violations = find_violations(
        text,
        quantities=quantities,
        date_parts=date_parts,
        control_words=control_words,
        number_tolerance=number_tolerance,
        prompt_numbers=prompt_numbers,
    )
    devices = find_device_mentions(text, device_words=device_words)
    missing = missing_evidence_paths(
        answer["classification"], answer["evidence_paths"].split(";"), state
    )

    return (
        "; ".join(f"{v.kind}: {v.found}" for v in violations),
        "; ".join(missing),
        "; ".join(devices),
    )


def check_answer_texts(
    single_answers: pd.DataFrame,
    results: pd.DataFrame,
    sequence_outputs: pd.DataFrame,
    sequence_states: pd.DataFrame,
    *,
    model_order: list[str],
    device_words: tuple[str, ...],
    control_words: tuple[str, ...],
    number_tolerance: float,
    prompt_numbers: tuple[float, ...],
) -> TextChecks:
    rules = {
        "device_words": device_words,
        "control_words": control_words,
        "number_tolerance": number_tolerance,
        "prompt_numbers": prompt_numbers,
    }
    single = single_answers.merge(
        results[["model_id", "case_id", "evidence_paths"]], on=["model_id", "case_id"]
    ).dropna(subset=["classification", "evidence_paths", "state"])
    single = single.assign(level="single", item=single["case_id"])

    sequence = (
        sequence_outputs.assign(
            time=pd.to_datetime(sequence_outputs["decision_time"], utc=True)
        )
        .merge(
            sequence_states.assign(
                time=pd.to_datetime(sequence_states["decision_time"], utc=True)
            )[["scenario", "config", "time", "state"]],
            on=["scenario", "config", "time"],
        )
        .rename(columns={"config": "model_id"})
    )
    sequence = sequence.assign(
        level="sequence", item=sequence["analyzed_day"] + " " + sequence["scenario"]
    )

    columns = ["level", "model_id", "item", "classification", "state", "evidence_paths"]
    checked = pd.concat(
        [single[columns + TEXT_COLUMNS[1:]], sequence[columns + TEXT_COLUMNS[1:]]]
    )
    checks = [
        _check_answer(row, row["state"], **rules) for _, row in checked.iterrows()
    ]
    checked = checked.assign(
        violations=[violations for violations, _, _ in checks],
        missing_evidence=[missing for _, missing, _ in checks],
        device_mentions=[devices for _, _, devices in checks],
    )

    counts = checked.groupby(["model_id", "level"]).agg(
        answers=("item", "size"),
        violations=("violations", lambda values: values.ne("").sum()),
        missing_evidence=("missing_evidence", lambda values: values.ne("").sum()),
        device_mentions=("device_mentions", lambda values: values.ne("").sum()),
    )
    # beide Ebenen immer als Spalten, auch wenn eine ohne geprüfte Antworten bleibt
    all_columns = pd.MultiIndex.from_product(
        [
            ["answers", "violations", "missing_evidence", "device_mentions"],
            ["single", "sequence"],
        ]
    )
    models = (
        cast(pd.DataFrame, counts.unstack("level"))
        .reindex(index=model_order, columns=all_columns)
        .fillna(0)
        .astype(int)
    )
    models.columns = [f"{level}_{name}" for name, level in models.columns]
    findings = (
        checked.loc[
            checked["violations"].ne("")
            | checked["missing_evidence"].ne("")
            | checked["device_mentions"].ne(""),
            [
                "level",
                "model_id",
                "item",
                "violations",
                "missing_evidence",
                "device_mentions",
            ],
        ]
        .assign(
            model_id=lambda frame: pd.Categorical(
                frame["model_id"], model_order, ordered=True
            )
        )
        .sort_values(["level", "model_id", "item"], kind="stable")
        .reset_index(drop=True)
    )

    return TextChecks(models=models.reset_index(), findings=findings)
