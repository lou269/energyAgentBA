# python docs/plots/plot_k4_llm_klassifikation.py
#
# ACHTUNG: Diese Daten stammen aus dem aelteren Vertical-Slice-Prototyp
# (experiments/prototypes/vertical_slice/llm_evaluation/), NICHT aus der
# aktuellen K4.1-Komponentenstudie (experiments/component_studies/
# k4_llm_classification/), deren Runner/Evaluation-Code noch leer ist.
# Das Prototyp-Schema verwendet ein anderes, umfangreicheres
# Klassifikationsschema (7 statt 4 Klassen) und andere Evidence-Felder
# (numerical_evidence/contextual_evidence statt evidence_references).
# Der Plot dient als vorlaeufige Referenz, bis K4.1 im aktuellen
# Pipeline-Schema reproduziert ist.
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import ListedColormap
from matplotlib.patches import Patch


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RESULTS_DIR = PROJECT_ROOT / "experiments" / "prototypes" / "vertical_slice" / "llm_evaluation" / "results"
FIGURE_DIR = PROJECT_ROOT / "docs" / "diagrams" / "generated"

MODEL_ORDER = ["qwen3.5:9b", "qwen3:8b", "llama3.1:8b", "qwen3:4b"]

MODEL_COLORS = {
    "qwen3.5:9b": "#4C78A8",
    "qwen3:8b": "#72B7B2",
    "llama3.1:8b": "#F58518",
    "qwen3:4b": "#E45756",
}

CASE_ORDER = [
    "normal_calendar_available",
    "normal_no_calendar",
    "absence_numerically_normal",
    "absence_strong_anomaly",
    "temporary_peak_explicit",
    "temporary_peak_unusual",
    "new_pattern_persistent_shift",
    "new_pattern_normal_anomaly_level",
    "seasonal_change_explicit",
    "seasonal_change_strong_anomaly",
    "measurement_invalid",
    "measurement_unreliable",
    "high_without_temporary_evidence",
    "season_field_only",
]

STATUS_COLORS = ["#B0B0B0", "#F58518", "#54A24B"]
STATUS_LABELS = ["Ungültige Ausgabe", "Falsch klassifiziert", "Korrekt"]


def add_bar_labels(axis, fmt: str = "{:.0%}") -> None:
    for container in axis.containers:
        for bar in container:
            height = bar.get_height()

            axis.annotate(
                fmt.format(height),
                xy=(bar.get_x() + bar.get_width() / 2, height,),
                xytext=(0, 3),
                textcoords="offset points",
                ha="center",
                va="bottom",
                fontsize=7,
            )


def main() -> None:
    summary = pd.read_csv(RESULTS_DIR / "llm_evaluation_summary.csv").set_index("model").loc[MODEL_ORDER]
    cases = pd.read_csv(RESULTS_DIR / "llm_evaluation_cases.csv")

    figure = plt.figure(figsize=(13, 14))
    grid = figure.add_gridspec(
        3,
        2,
        height_ratios=[1.0, 1.0, 1.3],
        hspace=0.6,
        wspace=0.3,
        top=0.90,
    )

    accuracy_axis = figure.add_subplot(grid[0, :])
    evidence_axis = figure.add_subplot(grid[1, 0])
    risk_axis = figure.add_subplot(grid[1, 1])
    matrix_axis = figure.add_subplot(grid[2, :])

    x_positions = np.arange(len(MODEL_ORDER))
    bar_width = 0.25

    # A: Gültigkeit und Klassifikationsgenauigkeit je Modell
    accuracy_axis.bar(
        x_positions - bar_width,
        summary["valid_output_rate"],
        width=bar_width,
        color=[MODEL_COLORS[m] for m in MODEL_ORDER],
        alpha=0.45,
        label="Valide Ausgabe (von 14 Fällen)",
    )
    accuracy_axis.bar(
        x_positions,
        summary["classification_accuracy_all"],
        width=bar_width,
        color=[MODEL_COLORS[m] for m in MODEL_ORDER],
        label="Klassifikation korrekt (alle Fälle)",
    )
    accuracy_axis.bar(
        x_positions + bar_width,
        summary["classification_accuracy_valid"],
        width=bar_width,
        color=[MODEL_COLORS[m] for m in MODEL_ORDER],
        hatch="//",
        label="Klassifikation korrekt (nur valide Fälle)",
    )

    accuracy_axis.set_xticks(x_positions)
    accuracy_axis.set_xticklabels(MODEL_ORDER)
    accuracy_axis.set_ylim(0, 1.35)
    accuracy_axis.set_ylabel("Anteil")
    accuracy_axis.set_title( "A: Ausgabevalidität und Klassifikationsgenauigkeit je Modell (n=14 Testfälle)", loc="left")
    accuracy_axis.grid(axis="y", alpha=0.25)
    add_bar_labels(accuracy_axis)
    accuracy_axis.legend(
        fontsize=8,
        ncol=3,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.08),
    )

    # B: Evidenzqualität je Modell
    evidence_metrics = [
        "evidence_path_accuracy",
        "evidence_value_accuracy",
        "required_evidence_recall",
    ]
    evidence_labels = [
        "Pfad-\nGenauigkeit",
        "Wert-\nGenauigkeit",
        "Pflicht-Evidenz-\nRecall",
    ]
    metric_positions = np.arange(len(evidence_metrics))
    model_bar_width = 0.2

    for offset, model_id in zip(
        np.linspace(
            -model_bar_width * 1.5,
            model_bar_width * 1.5,
            len(MODEL_ORDER),
        ),
        MODEL_ORDER,
    ):
        evidence_axis.bar(
            metric_positions + offset,
            summary.loc[model_id, evidence_metrics],
            width=model_bar_width,
            color=MODEL_COLORS[model_id],
            label=model_id,
        )

    evidence_axis.set_xticks(metric_positions)
    evidence_axis.set_xticklabels(evidence_labels, fontsize=8)
    evidence_axis.set_ylim(0, 1.15)
    evidence_axis.set_ylabel("Anteil")
    evidence_axis.set_title("B: Evidenzqualität je Modell", loc="left")
    evidence_axis.grid(axis="y", alpha=0.25)
    evidence_axis.legend(fontsize=7)

    # C: Problematische Verhaltensweisen je Modell (niedriger = besser)
    risk_metrics = [
        "forbidden_comparison_rate",
        "unsupported_claim_rate",
        "forecast_leakage_rate",
    ]
    risk_labels = [
        "Verbotener\nSkalarvergleich",
        "Unbelegte\nAussage",
        "Forecast-\nLeakage",
    ]
    risk_positions = np.arange(len(risk_metrics))

    for offset, model_id in zip(
        np.linspace(
            -model_bar_width * 1.5,
            model_bar_width * 1.5,
            len(MODEL_ORDER),
        ),
        MODEL_ORDER,
    ):
        risk_axis.bar(
            risk_positions + offset,
            summary.loc[model_id, risk_metrics],
            width=model_bar_width,
            color=MODEL_COLORS[model_id],
            label=model_id,
        )

    risk_axis.set_xticks(risk_positions)
    risk_axis.set_xticklabels(risk_labels, fontsize=8)
    risk_axis.set_ylim(0, 1.0)
    risk_axis.set_ylabel("Anteil betroffener Fälle")
    risk_axis.set_title("C: Problematische Verhaltensweisen je Modell (niedriger = besser)", loc="left")
    risk_axis.grid(axis="y", alpha=0.25)
    risk_axis.legend(fontsize=7)

    # D: Ergebnis je Testfall und Modell
    status_matrix = np.zeros((len(CASE_ORDER), len(MODEL_ORDER)))

    for row_index, case_name in enumerate(CASE_ORDER):
        for col_index, model_id in enumerate(MODEL_ORDER):
            case_row = cases.loc[
                cases["case"].eq(case_name) & cases["model"].eq(model_id)
            ].iloc[0]

            if not bool(case_row["valid_output"]):
                status_matrix[row_index, col_index] = 0
            elif bool(case_row["classification_correct"]):
                status_matrix[row_index, col_index] = 2
            else:
                status_matrix[row_index, col_index] = 1

    matrix_axis.imshow(
        status_matrix,
        cmap=ListedColormap(STATUS_COLORS),
        vmin=0,
        vmax=2,
        aspect="auto",
    )

    for row_index, case_name in enumerate(CASE_ORDER):
        for col_index, model_id in enumerate(MODEL_ORDER):
            case_row = cases.loc[
                cases["case"].eq(case_name) & cases["model"].eq(model_id)
            ].iloc[0]

            predicted = case_row["predicted_classification"]
            label = predicted if isinstance(predicted, str) else "—"

            matrix_axis.text(
                col_index,
                row_index,
                label,
                ha="center",
                va="center",
                fontsize=7,
                color="white" if label != "—" else "#333333",
            )

    matrix_axis.set_xticks(np.arange(len(MODEL_ORDER)))
    matrix_axis.set_xticklabels(MODEL_ORDER)
    matrix_axis.set_yticks(np.arange(len(CASE_ORDER)))
    matrix_axis.set_yticklabels(CASE_ORDER, fontsize=8)
    matrix_axis.set_title("D: Vorhergesagte Klassifikation je Testfall und Modell (erwartete Klasse im Fallnamen)", loc="left")
    matrix_axis.legend(
        handles=[
            Patch(color=color, label=label)
            for color, label in zip(STATUS_COLORS, STATUS_LABELS)
        ],
        fontsize=8,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.08),
        ncol=3,
    )

    figure.suptitle(
        "K4.1-Vorstudie: LLM-Modellvergleich zur Klassifikation (Vertical-Slice-Prototyp, älteres Schema)",
        fontsize=14,
        fontweight="bold",
        y=1.0,
    )
    figure.text(
        0.5,
        0.965,
        "Hinweis: Daten aus experiments/prototypes/vertical_slice/, nicht aus der aktuellen K4.1-Komponentenstudie",
        ha="center",
        fontsize=9,
        style="italic",
        color="#555555",
    )

    FIGURE_DIR.mkdir(parents=True, exist_ok=True)

    figure.savefig(str(FIGURE_DIR / "k4_llm_klassifikation_prototyp.svg"), bbox_inches="tight")
    figure.savefig(str(FIGURE_DIR / "k4_llm_klassifikation_prototyp.png"), dpi=300, bbox_inches="tight")


    plt.close(figure)


if __name__ == "__main__":
    main()
