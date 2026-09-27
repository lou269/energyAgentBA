# conda activate forecasting-env
# python -m experiments.k3_llm.k3_report [run_directory] [sequence_run_directory]

import pandas as pd

from docs.plots.plot_k3_llm_model import build_k3_plot
from experiments.common.report import (
    format_commit,
    format_number,
    key_figures_table,
    relabel,
    write_result_report,
)
from experiments.common.standard_config import DECIMALS, KIND_LABELS, PROJECT_CONFIG
from experiments.k3_llm.k3_config import (
    BASELINE_ID,
    CORRECT_ANSWER_LABEL,
    RESULTS_FILE,
    RUN_PREFIX,
    SEQUENCE_RESULTS_FILE,
    SEQUENCE_RUN_PREFIX,
)
from experiments.k3_llm.k3_evaluation import summarize_k3
from src.config.config_forecasting import SYS_VARIANTS
from src.pipeline.io import (
    RAW_SUBDIR,
    df_to_csv,
    read_raw_json,
    run_directory_from_argv,
    user_output_directory,
)

RULE_LABEL = "Regel"

SINGLE_CASE_HEADERS = {
    "model_id": "ID",
    "model": "Modell",
    "correct": "richtig",
    "macro_f1": "Macro-F1",
    "invalid": "ungültig",
    "mean_attempt_count": "Ø Versuche",
    "mean_grounding_coverage": "Grounding",
    "mean_generation_seconds": "Ø s je Aufruf",
    "p95_generation_seconds": "p95 s",
}
SEQUENCE_HEADERS = {
    "model_id": "Modell",
    "detected_kinds": "Ereignis-Arten erkannt",
    "rule_deviation_days": "Tage anders als die Regel",
    "gate_open_days": "Gate-Tage",
    "failed_days": "Ausfalltage",
    "control_notification_days": "Meldungen Kontrolle",
    "control_unknown_days": "unknown Kontrolle",
    "control_resets": "Resets Kontrolle",
}
EVENT_HEADERS = {
    "model_id": "Modell",
    "kind": "Ereignis",
    "expected_classification": "erwartet",
    "event_gate_open_days": "Gate-Tage durch das Ereignis",
    "correct_days": "davon richtig",
    "first_correct_day": "erster richtiger Tag",
    "resets": "Resets",
}
DEVIATION_HEADERS = {
    "model_id": "Modell",
    "analyzed_day": "analysierter Tag",
    "classification_rule": "Regel",
    "classification": "Modell sagt",
    "kinds": "in Arten",
}
CASE_HEADERS = {"case_id": "Fall", "expected_classification": "erwartet"}
CLASS_HEADERS = {
    "model_id": "Modell",
    "classification": "Klasse",
    "precision": "Precision",
    "recall": "Recall",
    "f1": "F1",
}


def build_setup(
    run_config: dict,
    sequence_run_config: dict,
    case_count: int,
    production_model: str,
    run_names: str,
) -> dict[str, str]:
    k3_config = run_config["k3_config"]
    llm_config = k3_config["base_llm_config"]
    sequence_config = sequence_run_config["k3_config"]
    standard_config = sequence_run_config["standard_config"]

    return {
        "Läufe (Ebene 1 / Ebene 2)": run_names,
        "Prompt (Ebene 1 / Ebene 2)": f"{llm_config['prompt_version']} / {sequence_config['base_llm_config']['prompt_version']}",
        "Modelle": ", ".join(
            f"{variant['model_id']} {variant['model']}"
            for variant in k3_config["model_variants"]
        ),
        "LLM": f"temperature {format_number(llm_config['temperature'], 1)}, höchstens {llm_config['max_attempts']} Versuche je Aufruf",
        "Ebene 1": f"{case_count} synthetische Fälle, je Modell {k3_config['repetitions']} Aufruf je Fall, Regel ({BASELINE_ID}) läuft mit",
        "Ebene 2": (
            f"Standard-Szenarien, Cutover {sequence_config['sequence_cutover_date']}, "
            f"{standard_config['monitoring_before_cutover_days']} Tage davor, {standard_config['margin_after_days']} danach, "
            "jedes Modell als eigener Kreislauf wie SYS3 mit Adaption"
        ),
        "Ereignisse Ebene 2": ", ".join(
            f"{kind} = {KIND_LABELS[kind]}"
            for kind in sequence_config["sequence_kinds"]
        ),
        "Produktivmodell SYS3": production_model,
        "Commit (Ebene 1 / Ebene 2)": f"{format_commit(run_config['code_version'])} / {format_commit(sequence_run_config['code_version'])}",
    }


def _count_of(counts: pd.Series, totals: pd.Series) -> pd.Series:
    return counts.astype(str) + "/" + totals.astype(str)


def build_key_figures(
    models: pd.DataFrame, rule_deviations: pd.DataFrame, production_model: str
) -> pd.DataFrame:
    production = models.loc[models["model"].eq(production_model)].iloc[0]
    rule = models.loc[models["model_id"].eq(BASELINE_ID)].iloc[0]
    best = models.loc[models["model_id"].ne(BASELINE_ID)].iloc[0]
    deviations = rule_deviations.loc[
        rule_deviations["model_id"].eq(production["model_id"])
    ]
    name = production["model"]

    return key_figures_table(
        [
            (
                "Ebene 1: bestes Modell nach Macro-F1",
                best["model"],
                f"Macro-F1 {format_number(best['macro_f1'], 2)}, Regel {format_number(rule['macro_f1'], 2)}",
            ),
            (
                f"{name}: Ebene 1 richtig",
                production["correct"],
                f"Regel {rule['correct']}",
            ),
            (
                f"{name}: Antwortzeit je Aufruf im Mittel [s]",
                production["mean_generation_seconds"],
                f"p95 {format_number(production['p95_generation_seconds'], DECIMALS)} s, "
                f"Regel {format_number(rule['mean_generation_seconds'], DECIMALS)} s",
            ),
            (
                f"{name}: Ebene 2 Ereignis-Arten erkannt",
                production["detected_kinds"],
                f"Regel {rule['detected_kinds']}",
            ),
            (
                f"{name}: Ebene 2 Tage mit anderer Klasse als die Regel",
                production["rule_deviation_days"],
                "; ".join(
                    f"{day} {model_class} statt {rule_class}"
                    for day, model_class, rule_class in zip(
                        deviations["analyzed_day"],
                        deviations["classification"],
                        deviations["classification_rule"],
                    )
                )
                or "-",
            ),
            (
                f"{name}: ungültige Antworten Ebene 1",
                production["invalid"],
                f"Ausfalltage Ebene 2: {production['failed_days']}",
            ),
        ]
    )


def main() -> None:
    k3_output_dir = PROJECT_CONFIG.k3_output_dir
    production_llm_config = SYS_VARIANTS["SYS3"].llm_config
    assert production_llm_config is not None
    production_model = production_llm_config.model

    run_directory = run_directory_from_argv(k3_output_dir, RUN_PREFIX, 1)
    sequence_run_directory = run_directory_from_argv(
        k3_output_dir, SEQUENCE_RUN_PREFIX, 2
    )

    summary = summarize_k3(
        pd.read_csv(run_directory / RAW_SUBDIR / f"{RESULTS_FILE}.csv"),
        pd.read_csv(
            sequence_run_directory / RAW_SUBDIR / f"{SEQUENCE_RESULTS_FILE}.csv",
            dtype={"cutover_date": str},
        ),
    )
    models = summary.models
    model_labels = dict(zip(models["model_id"], models["model"])) | {
        BASELINE_ID: RULE_LABEL
    }
    # Zählungen als "richtig/gesamt", so auch in den Kennzahlen
    counted = models.assign(
        correct=_count_of(models["correct"], models["n_attempts"]),
        detected_kinds=_count_of(models["detected_kinds"], models["event_kinds"]),
        model=models["model_id"].map(model_labels),
    )
    run_names = f"{run_directory.name} / {sequence_run_directory.name}"

    tables = {
        "key_figures": (
            "Kennzahlen",
            build_key_figures(counted, summary.rule_deviations, production_model),
        ),
        "result_single_case": (
            "Ebene 1: Modellvergleich auf den Einzelfällen",
            counted[list(SINGLE_CASE_HEADERS)].rename(columns=SINGLE_CASE_HEADERS),
        ),
        "result_cases": (
            f"Ebene 1: Antwort je Fall ({CORRECT_ANSWER_LABEL} = richtig, sonst die Antwort, - = ungültig)",
            summary.case_answers.rename(columns=CASE_HEADERS | model_labels),
        ),
        "result_sequence": (
            "Ebene 2: je Modell über alle Ereignis-Arten",
            relabel(
                counted[list(SEQUENCE_HEADERS)],
                SEQUENCE_HEADERS,
                {"model_id": model_labels},
            ),
        ),
        "result_sequence_events": (
            "Ebene 2: Erkennung je Ereignis, Tag seit Cutover",
            relabel(
                summary.events,
                EVENT_HEADERS,
                {"model_id": model_labels, "kind": KIND_LABELS},
            ),
        ),
        "result_rule_deviations": (
            "Ebene 2: Tage, an denen ein Modell anders einordnet als die Regel",
            relabel(
                summary.rule_deviations, DEVIATION_HEADERS, {"model_id": model_labels}
            ),
        ),
    }
    appendix = {
        "result_classes": (
            "Ebene 1: Precision, Recall und F1 je Klasse",
            relabel(summary.classes, CLASS_HEADERS, {"model_id": model_labels}),
        )
    }
    notes = [
        "Ebene 1 prüft, ob ein Modell die Regeln aus dem Prompt nachvollzieht. Der Prompt wurde auf denselben Fällen verbessert, "
        "die Quoten begründen deshalb nur die Modellwahl und belegen nicht das Ziel von 80 % richtiger Klassen (dafür E5)",
        "wenige Fälle: ein Fall sind mehrere Prozentpunkte, eine Klasse hängt teils an einem einzigen Fall",
        "Macro-F1: Mittel der F1-Werte über die Klassen, die als erwartete Klasse vorkommen",
        "Grounding: Anteil der für den Fall erwarteten Felder, die das Modell als Beleg zitiert. Die Regel zitiert keine",
        "Tag seit Cutover = Entscheidungstag: an Tag n meldet das System, eingeordnet ist dabei Tag n-1. Ab Cutover zählt deshalb erst ab Tag 1",
        "Ebene 2, erkannt: erwartete Klasse an einem Tag, an dem nur das Ereignis das Gate öffnet (gepaart mit dem Kontrolllauf desselben Modells)",
        "Ebene 2, anders als die Regel: gleiche Art und gleicher analysierter Tag, Regel gegen Modell. Nach einem Reset an verschiedenen Tagen "
        "laufen die Reihen auseinander, spätere Abweichungen können daraus folgen",
        "Antwortzeit: gemessen auf dem Rechner des Laufs, nur zum Vergleich der Modelle untereinander",
    ]

    output_directory = user_output_directory(run_directory)
    # die bisherigen CSVs mit Rohspalten, model_comparison enthält jetzt beide Ebenen
    df_to_csv(models, output_directory, "model_comparison")
    df_to_csv(summary.cases, output_directory, "case_breakdown")
    df_to_csv(summary.classes, output_directory, "class_breakdown")
    sequence_output_directory = user_output_directory(sequence_run_directory)
    df_to_csv(summary.events, sequence_output_directory, "sequence_events")
    df_to_csv(summary.sequence_models, sequence_output_directory, "sequence_models")

    build_k3_plot(models, output_directory, production_model=production_model)

    write_result_report(
        output_directory,
        title=f"K3 LLM-Klassifikation und Modellwahl, Läufe {run_names}",
        setup=build_setup(
            read_raw_json(run_directory, "run_config"),
            read_raw_json(sequence_run_directory, "run_config"),
            len(summary.case_answers),
            production_model,
            run_names,
        ),
        tables=tables,
        notes=notes,
        images=["k3_quality_vs_time.png"],
        decimals=DECIMALS,
        appendix=appendix,
    )

    print(f"Result written to {output_directory / 'ergebnis.md'}")


if __name__ == "__main__":
    main()
