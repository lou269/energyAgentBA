# conda activate forecasting-env
# python -m experiments.k2_llm.k2_report [run_directory] [sequence_run_directory]

from pathlib import Path

import pandas as pd

from experiments.common.report import (
    KIND_LABELS,
    build_setup,
    format_commit,
    format_number,
    relabel,
    write_result_report,
)
from experiments.common.standard_config import (
    LLM_SYSTEM,
    PROJECT_CONFIG,
    STANDARD_CONFIG,
)
from experiments.k2_llm.k2_config import (
    BASELINE_ID,
    RESULTS_FILE,
    RUN_PREFIX,
    SEQUENCE_RESULTS_FILE,
    SEQUENCE_RUN_PREFIX,
)
from experiments.common.harness import read_llm_outputs, read_structured_states
from experiments.k2_llm.k2_evaluation import (
    CORRECT_ANSWER,
    TEXT_COLUMNS,
    check_answer_texts,
    collect_answer_texts,
    summarize_k2,
)
from src.config.config_forecasting import SYS_VARIANTS, TextCheckConfig
from src.pipeline.io import (
    RAW_SUBDIR,
    df_to_csv,
    read_jsonl,
    read_raw_json,
    run_directory_from_argv,
    user_output_directory,
)

# in der Tabelle "Antwort je Fall" statt der Klasse, wenn sie stimmt
CORRECT_ANSWER_LABEL = "✓"

RULE_LABEL = "Regel"

SINGLE_CASE_HEADERS = {
    "model_id": "ID",
    "model": "Modell",
    "correct": "richtig",
    "macro_f1": "Macro-F1",
    "invalid": "ungültig",
    "mean_attempt_count": "Ø Versuche",
    "mean_grounding_coverage": "Grounding",
    "mean_generation_seconds": "Ø Zeit [s]",
    "p95_generation_seconds": "p95 Zeit [s]",
}
SEQUENCE_HEADERS = {
    "model_id": "Modell",
    "detected_kinds": "Szenarien erkannt",
    "rule_deviation_days": "Abweichungstage",
    "gate_open_days": "Vorfilter offen",
    "failed_days": "Ausfalltage",
    "control_notification_days": "Meldungen Kontrolllauf",
    "control_unknown_days": "unknown Kontrolllauf",
    "control_resets": "Zurücksetzen Kontrolllauf",
}
TEXT_CHECK_HEADERS = {
    "model_id": "Modell",
    "single_answers": "E1 Antworten",
    "single_violations": "E1 Verstoß",
    "single_missing_evidence": "E1 Beleg fehlt",
    "sequence_answers": "E2 Antworten",
    "sequence_violations": "E2 Verstoß",
    "sequence_missing_evidence": "E2 Beleg fehlt",
}
FINDING_HEADERS = {
    "level": "Ebene",
    "model_id": "Modell",
    "item": "Fall oder Tag",
    "violations": "Verstoß",
    "missing_evidence": "fehlende Belege",
}
LEVEL_LABELS = {"single": "Ebene 1", "sequence": "Ebene 2"}
CASE_HEADERS = {"case_id": "Fall", "expected_classification": "erwartet"}


def build_study_setup(
    run_config: dict,
    sequence_run_config: dict,
    case_count: int,
    production_model: str,
    run_names: str,
    text_check: str,
) -> dict[str, str]:
    k2_config = run_config["k2_config"]
    llm_config = k2_config["base_llm_config"]
    sequence_config = sequence_run_config["k2_config"]
    standard_config = sequence_run_config["standard_config"]
    prompts = (
        llm_config["prompt_version"],
        sequence_config["base_llm_config"]["prompt_version"],
    )

    setup = build_setup(
        run_names,
        standard_config,
        [sequence_config["sequence_cutover"][standard_config["split"]]],
        run_config["code_version"],
        scenarios=", ".join(
            KIND_LABELS[kind] for kind in sequence_config["sequence_kinds"]
        ),
        systems=f"{LLM_SYSTEM} mit Adaption, jedes Modell als eigener Kreislauf",
        llm=f"Prompt {' und '.join(dict.fromkeys(prompts))}, temperature {format_number(llm_config['temperature'], 1)}, höchstens {llm_config['max_attempts']} Versuche je Aufruf, ohne Kalender",
        details={
            "Modelle": ", ".join(
                f"{variant['model_id']} {variant['model']}"
                for variant in k2_config["model_variants"]
            ),
            "Ebene 1": f"{case_count} synthetische Fälle, je Modell {k2_config['repetitions']} Aufruf je Fall, Regel ({BASELINE_ID}) läuft mit",
            "Ebene 2": f"{standard_config['monitoring_before_cutover_days']} Tage vor und {standard_config['margin_after_days']} Tage nach dem Stichtag",
            "Produktivmodell": production_model,
            "Textprüfung": text_check,
        },
    )

    return setup | {
        "Commit": f"{format_commit(run_config['code_version'])} (Ebene 1), {format_commit(sequence_run_config['code_version'])} (Ebene 2)"
    }


def read_single_answers(run_directory: Path) -> pd.DataFrame:
    # je Modell eine jsonl mit einer Zeile je Fall, ungültige Antworten haben keinen output
    rows = []
    for answer_file in sorted((run_directory / RAW_SUBDIR).glob("*.jsonl")):
        for record in read_jsonl(answer_file):
            output = record["output"] or {}
            rows.append(
                {"model_id": answer_file.stem, "case_id": record["case_id"]}
                | {column: output.get(column) for column in TEXT_COLUMNS}
                | {"error": record["error"], "state": record.get("state")}
            )

    return pd.DataFrame(rows)


def _count_of(counts: pd.Series, totals: pd.Series) -> pd.Series:
    return counts.astype(str) + "/" + totals.astype(str)


def main() -> None:
    k2_output_dir = PROJECT_CONFIG.k2_output_dir
    production_llm_config = SYS_VARIANTS[LLM_SYSTEM].llm_config
    assert production_llm_config is not None
    production_model = production_llm_config.model

    run_directory = run_directory_from_argv(k2_output_dir, RUN_PREFIX, 1)
    sequence_run_directory = run_directory_from_argv(
        k2_output_dir, SEQUENCE_RUN_PREFIX, 2
    )

    results = pd.read_csv(run_directory / RAW_SUBDIR / f"{RESULTS_FILE}.csv")
    summary = summarize_k2(
        results,
        pd.read_csv(
            sequence_run_directory / RAW_SUBDIR / f"{SEQUENCE_RESULTS_FILE}.csv",
            dtype={"cutover_date": str},
        ),
    )
    models = summary.models
    model_labels = dict(zip(models["model_id"], models["model"])) | {
        BASELINE_ID: RULE_LABEL
    }
    counted = models.assign(
        correct=_count_of(models["correct"], models["n_attempts"]),
        detected_kinds=_count_of(models["detected_kinds"], models["event_kinds"]),
        model=models["model_id"].map(model_labels),
    )
    run_names = f"{run_directory.name} und {sequence_run_directory.name}"
    production_id = models.loc[models["model"].eq(production_model), "model_id"].iloc[0]
    single_answers = read_single_answers(run_directory)
    sequence_raw_directory = sequence_run_directory / RAW_SUBDIR
    sequence_outputs = read_llm_outputs(sequence_raw_directory)
    answers = collect_answer_texts(
        single_answers,
        results,
        sequence_outputs,
        model_order=models["model_id"].tolist(),
        sequence_model_id=production_id,
    )
    text_check_config = TextCheckConfig()
    # die Fensterlängen aus der Skalenbeschreibung im Prompt stehen nicht im State, kommen aber im Text vor
    analysis_config = SYS_VARIANTS[LLM_SYSTEM].numerical_analysis_config
    window_numbers = (
        float(analysis_config.weekly_window_days),
        float(analysis_config.long_term_window_days),
    )
    checks = check_answer_texts(
        single_answers,
        results,
        sequence_outputs,
        read_structured_states(sequence_raw_directory),
        model_order=[
            model_id for model_id in models["model_id"] if model_id != BASELINE_ID
        ],
        control_words=text_check_config.control_words,
        number_tolerance=text_check_config.number_tolerance,
        rounding_step=text_check_config.rounding_step,
        prompt_numbers=window_numbers,
    )

    tables = {
        "result_single_case": (
            "Ebene 1: Modellvergleich auf den Einzelfällen",
            counted[list(SINGLE_CASE_HEADERS)].rename(columns=SINGLE_CASE_HEADERS),
        ),
        "result_cases": (
            f"Ebene 1: Antwort je Fall ({CORRECT_ANSWER_LABEL} = richtig, sonst die Antwort, - = ungültig)",
            summary.case_answers.replace(CORRECT_ANSWER, CORRECT_ANSWER_LABEL).rename(
                columns=CASE_HEADERS | model_labels
            ),
        ),
        "result_sequence": (
            "Ebene 2: je Modell über alle Szenarien",
            relabel(
                counted[list(SEQUENCE_HEADERS)],
                SEQUENCE_HEADERS,
                {"model_id": model_labels},
            ),
        ),
        "result_text_checks": (
            "Textprüfung je Modell, Antworten mit Verstoß oder fehlendem Beleg",
            relabel(
                checks.models[list(TEXT_CHECK_HEADERS)],
                TEXT_CHECK_HEADERS,
                {"model_id": model_labels},
            ),
        ),
    }
    findings = relabel(
        checks.findings,
        FINDING_HEADERS,
        {"level": LEVEL_LABELS, "model_id": model_labels},
    )
    notes = [
        "Ebene 1 prüft, ob ein Modell die Regeln aus dem Prompt nachvollzieht. Der Prompt wurde auf denselben Fällen verbessert, "
        "die Quoten begründen deshalb nur die Modellwahl und belegen nicht das Ziel von 80 % richtiger Klassen (dafür E2)",
        "wenige Fälle: ein Fall sind mehrere Prozentpunkte, eine Klasse hängt teils an einem einzigen Fall",
        "Macro-F1: Mittel der F1-Werte über die Klassen, die als erwartete Klasse vorkommen",
        "Grounding: Anteil der für den Fall erwarteten Felder, die das Modell als Beleg zitiert. Die Regel zitiert keine",
        "Ebene 2, erkannt: erwartete Klasse an einem Tag, an dem nur das Szenario den Vorfilter öffnet (gepaart mit dem Kontrolllauf desselben Modells)",
        "Ebene 2, Abweichungstage: gleiche Art und gleicher analysierter Tag, Regel gegen Modell. Nach einem Zurücksetzen an verschiedenen Tagen "
        "laufen die Reihen auseinander, spätere Abweichungen können daraus folgen",
        "Zeit: gemessen auf dem Rechner des Laufs, nur zum Vergleich der Modelle untereinander",
        "Textprüfung: Verstoß heißt, ein Steuerungswort oder eine Zahl, ein Datum oder eine Uhrzeit steht im Text, aber nicht im State des Falls. "
        "Zahlwörter („sechs Wochen“) findet sie nicht. Die Fensterlängen "
        f"{' und '.join(format_number(n, 0) for n in window_numbers)} aus der Skalenbeschreibung im Prompt gelten als erlaubt",
        "Beleg fehlt: der Prompt verlangt je Klasse bestimmte Pfade (new_pattern: sustained_drift, Streaks, peak und low: level, direction, absence: level, Kalendereintrag, measurement_error: Flag). Geprüft wird gegen die eigene Klasse des Modells, nicht gegen die erwartete. Ebene 1 wird nur für Läufe geprüft, die den State der Fälle in der Antwortdatei speichern, ältere Läufe haben in der Tabelle 0 Antworten",
        "Antworttexte, Abweichungstage, Erkennung je Szenario und Auffälligkeiten der Textprüfung stehen als CSV im Ordner des Laufs (answers_single, answers_sequence nur vom Produktivmodell, result_text_findings, sequence_events)",
    ]

    output_directory = user_output_directory(run_directory)
    df_to_csv(models, output_directory, "model_comparison")
    df_to_csv(summary.cases, output_directory, "case_breakdown")
    df_to_csv(summary.classes, output_directory, "class_breakdown")
    df_to_csv(summary.rule_deviations, output_directory, "rule_deviations")
    df_to_csv(answers.single, output_directory, "answers_single")
    df_to_csv(answers.sequence, output_directory, "answers_sequence")
    df_to_csv(findings, output_directory, "result_text_findings")
    sequence_output_directory = user_output_directory(sequence_run_directory)
    df_to_csv(summary.events, sequence_output_directory, "sequence_events")
    df_to_csv(summary.sequence_models, sequence_output_directory, "sequence_models")

    write_result_report(
        output_directory,
        title="K2: Sprachmodell",
        setup=build_study_setup(
            read_raw_json(run_directory, "run_config"),
            read_raw_json(sequence_run_directory, "run_config"),
            len(summary.case_answers),
            production_model,
            run_names,
            f"{len(text_check_config.control_words)} Steuerungswörter, "
            f"Zahlentoleranz {format_number(text_check_config.number_tolerance, 1)}, "
            f"gerundet auf {format_number(text_check_config.rounding_step, 0)} erlaubt, "
            f"Fensterzahlen aus dem Prompt {', '.join(format_number(n, 0) for n in window_numbers)}",
        ),
        tables=tables,
        notes=notes,
        images=[],
        decimals=STANDARD_CONFIG.decimals,
    )

    print(f"Result written to {output_directory / 'ergebnis.md'}")


if __name__ == "__main__":
    main()
