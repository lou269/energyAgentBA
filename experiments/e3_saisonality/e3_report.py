# conda activate forecasting-env
# python -m experiments.e3_saisonality.e3_report [forecast|drift] [run_directory]

import sys
from pathlib import Path

import pandas as pd

from docs.plots.plot_e3_seasonality import build_e3_forecast_plot
from experiments.common.report import (
    NOISE_RULE_NOTE,
    format_commit,
    key_figures_table,
    paired_difference_columns,
    write_result_report,
)
from experiments.common.standard_config import DECIMALS, KIND_LABELS, PROJECT_CONFIG
from experiments.e3_saisonality.e3_config import (
    DRIFT_RESULTS_FILE,
    DRIFT_RUN_PREFIX,
    FORECAST_RUN_PREFIX,
    MODEL_LABELS,
    ORIGIN_METRICS_FILE,
)
from experiments.e3_saisonality.e3_evaluation import (
    summarize_ramp_response,
    summarize_seasonal_forecast,
)
from src.config.config_forecasting import SYS_LABELS
from src.pipeline.io import (
    RAW_SUBDIR,
    read_raw_json,
    run_directory_from_argv,
    user_output_directory,
)

REPEAT_HEADERS = {"kind": "Ereignis", "mean": "Mittel", "detected": "erkannt"}


def report_forecast(run_directory: Path) -> Path:
    run_config = read_raw_json(run_directory, "run_config")
    e3_config = run_config["e3_config"]
    reference_model_id = run_config["reference_baseline"]
    model_ids = [variant["model_id"] for variant in e3_config["prophet_variants"]]

    origin_metrics = pd.read_csv(
        run_directory / RAW_SUBDIR / f"{ORIGIN_METRICS_FILE}.csv",
        dtype={"forecast_day": str},
    )
    summary = summarize_seasonal_forecast(
        origin_metrics,
        tuple((variant, reference) for variant, reference in e3_config["comparisons"]),
    )

    comparisons = [
        f"{variant} − {reference}"
        for variant, reference in zip(
            summary.paired["variant"], summary.paired["reference"]
        )
    ]
    by_month = summary.by_month[["month"] + model_ids + [reference_model_id]]

    tables = {
        "key_figures": (
            "Kennzahlen",
            key_figures_table(
                [
                    (
                        f"{comparison}: MAE-Differenz über das Jahr [W]",
                        delta,
                        "negativ = Variante besser, belastbar "
                        + ("ja" if exceeds_noise else "nein"),
                    )
                    for comparison, delta, exceeds_noise in zip(
                        comparisons,
                        summary.paired["mean_delta"],
                        summary.paired["exceeds_noise"],
                    )
                ]
            ),
        ),
        "result_by_month": (
            "MAE je Monat [W]",
            by_month.rename(columns={"month": "Monat"} | MODEL_LABELS),
        ),
        "result_paired": (
            "Gepaarte Differenzen über das Jahr, je Prognosetag",
            pd.concat(
                [
                    pd.DataFrame({"Vergleich": comparisons}),
                    paired_difference_columns(summary.paired, "Tage"),
                ],
                axis=1,
            ),
        ),
    }

    output_directory = user_output_directory(run_directory)
    build_e3_forecast_plot(
        summary.by_month,
        output_directory,
        model_ids=model_ids,
        reference_model_id=reference_model_id,
    )

    write_result_report(
        output_directory,
        title=f"E3 Prognose mit und ohne Jahressaisonalität, Lauf {run_directory.name}",
        setup={
            "Auswertung": f"{e3_config['forecast_days']} Tage ab {e3_config['forecast_start_date']}, "
            "je Tag eine 24-h-Prognose, Historie ab Datenbeginn",
            "Varianten": ", ".join(MODEL_LABELS[model_id] for model_id in model_ids),
            "Naive Referenz": MODEL_LABELS[reference_model_id],
            "Commit": format_commit(run_config["code_version"]),
        },
        tables=tables,
        notes=[
            "S1 − C2 ist der Effekt der Jahressaisonalität allein, C2 − C3_30 der der längeren Historie",
            "Monat 2014-04 und 2015-04 sind je ein halber Monat",
            NOISE_RULE_NOTE,
        ],
        images=["e3_mae_by_month.png"],
        decimals=DECIMALS,
    )

    return output_directory


def report_drift(run_directory: Path) -> Path:
    run_config = read_raw_json(run_directory, "run_config")
    e3_config = run_config["e3_config"]
    event_kinds = [kind for kind in e3_config["kinds"] if kind != "control"]

    results = pd.read_csv(
        run_directory / RAW_SUBDIR / f"{DRIFT_RESULTS_FILE}.csv",
        dtype={"cutover_date": str},
    )
    summary = summarize_ramp_response(results)
    detection = summary.detection.set_index("kind").loc[event_kinds].reset_index()
    gate_open = summary.gate_open.set_index("kind").loc[event_kinds].reset_index()

    tables = {
        "key_figures": (
            "Kennzahlen",
            key_figures_table(
                [
                    (
                        f"{KIND_LABELS[kind]}: als new_pattern gemeldet",
                        detected,
                        f"im Mittel an Tag {day:.0f}" if pd.notna(day) else "nie",
                    )
                    for kind, detected, day in zip(
                        detection["kind"], detection["detected"], detection["mean"]
                    )
                ]
                + [
                    (
                        f"{KIND_LABELS[kind]}: Tage mit offenem Gate",
                        days,
                        "Mittel über Cutover, mehr als im Kontrolllauf",
                    )
                    for kind, days in zip(gate_open["kind"], gate_open["mean"])
                ]
            ),
        ),
        "result_detection": (
            "Erster Tag mit new_pattern, den der Kontrolllauf nicht hat, je Cutover",
            detection.assign(kind=detection["kind"].map(KIND_LABELS)).rename(
                columns=REPEAT_HEADERS
            ),
        ),
        "result_gate_open": (
            "Tage mit offenem Gate ohne Gegenstück im Kontrolllauf, je Cutover",
            gate_open.assign(kind=gate_open["kind"].map(KIND_LABELS)).rename(
                columns=REPEAT_HEADERS
            ),
        ),
    }

    output_directory = user_output_directory(run_directory)
    write_result_report(
        output_directory,
        title=f"E3 Stufe gegen langsame Rampe, Lauf {run_directory.name}",
        setup={
            "Cutover": ", ".join(run_config["standard_config"]["cutover_dates"]),
            "Ereignisse": ", ".join(KIND_LABELS[kind] for kind in e3_config["kinds"]),
            "System": f"{SYS_LABELS[e3_config['system_id']]}, Einordnung und Reset wie im Betrieb, ohne LLM",
            "Commit": format_commit(run_config["code_version"]),
        },
        tables=tables,
        notes=[
            "Tag = Entscheidungstag seit Cutover, an Tag 1 wird der Cutover-Tag eingeordnet",
            "kein Tag = die Veränderung wurde still aufgenommen",
            "offenes Gate = Tag, an dem SYS3 das LLM fragen würde, die States dieser Tage liegen in raw/",
        ],
        images=[],
        decimals=DECIMALS,
    )

    return output_directory


def main() -> None:
    part = sys.argv[1] if len(sys.argv) > 1 else "forecast"
    prefix = FORECAST_RUN_PREFIX if part == "forecast" else DRIFT_RUN_PREFIX
    run_directory = run_directory_from_argv(PROJECT_CONFIG.e3_output_dir, prefix, 2)

    if part == "forecast":
        output_directory = report_forecast(run_directory)
    else:
        output_directory = report_drift(run_directory)

    print(f"Result written to {output_directory / 'ergebnis.md'}")


if __name__ == "__main__":
    main()
