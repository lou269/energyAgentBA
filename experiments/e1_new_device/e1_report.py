# conda activate forecasting-env
# python -m experiments.e1_new_device.e1_report [run_directory]

from pathlib import Path

import pandas as pd

from docs.plots.plot_e1_new_device import build_e1_plot
from experiments.common.evaluation import EVENT_KEYS
from experiments.common.report import (
    KIND_LABELS,
    format_commit,
    format_cutovers,
    write_result_report,
)
from experiments.common.standard_config import PROJECT_CONFIG, STANDARD_CONFIG
from experiments.e1_new_device.e1_config import (
    DEVICE_WINDOWS_FILE,
    RESULTS_FILE,
    RUN_PREFIX,
)
from experiments.e1_new_device.e1_evaluation import summarize_e1
from src.config.config_forecasting import SYS_LABELS
from src.pipeline.io import (
    RAW_SUBDIR,
    read_raw_json,
    run_directory_from_argv,
    user_output_directory,
)

RESPONSE_HEADERS = {
    "config": "System",
    "cutover_date": "Cutover",
    "kind": "Ereignis",
    "expected": "erwartet",
    "first_event_new_pattern_day": "erstes new_pattern (Tag)",
    "gate_open_days": "Tage Gate offen",
    "resets_before_cutover": "Resets vor Cutover",
    "reset_forecast_day": "erster Reset (Tag)",
}

DEVICE_HEADERS = {
    "cutover_date": "Cutover",
    "kind": "Gerät",
    "device_mean_w": "Leistung ab Cutover [W]",
    "device_share_pct": "Anteil an Mains ab Cutover [%]",
    "coverage_before_pct": "Abdeckung Kanal vor Cutover [%]",
    "coverage_after_pct": "Abdeckung Kanal ab Cutover [%]",
}

EVENT_HEADERS = {
    "cutover_date": "Cutover",
    "kind": "Ereignis",
    "config": "System",
    "days_since_cutover": "Tag",
    "analyzed_day": "eingeordnet",
    "classification": "Klasse",
    "adaption_action": "Adaption",
    "explanation": "Begründung",
    "error": "Fehler",
}


def write_report(run_directory: Path) -> Path:
    run_config = read_raw_json(run_directory, "run_config")
    e1_config = run_config["e1_config"]
    llm_config = run_config["llm_config"]
    cutover_dates = run_config["standard_config"]["cutover_dates"]
    reference = e1_config["reference_system"]
    systems = [e1_config["rule_system"], e1_config["llm_system"]]
    devices = e1_config["devices"]
    kind_labels = {"control": KIND_LABELS["control"]} | {
        kind: f"{kind} ({', '.join(meter_keys)})"
        for kind, meter_keys in devices.items()
    }
    rows = [
        (system, cutover_dates[cutover_id], kind)
        for system in systems
        for cutover_id in e1_config["cutover_ids"]
        for kind in kind_labels
    ]

    results = pd.read_csv(
        run_directory / RAW_SUBDIR / f"{RESULTS_FILE}.csv",
        dtype={"cutover_date": str},
    )
    device_windows = pd.read_csv(
        run_directory / RAW_SUBDIR / f"{DEVICE_WINDOWS_FILE}.csv",
        dtype={"cutover_date": str},
    )
    summary = summarize_e1(
        results,
        reference_config=reference,
        device_kinds=list(devices),
        target_classification=e1_config["target_classification"],
    )
    response = summary.response.set_index(EVENT_KEYS).loc[rows].reset_index()

    tables = {
        "result_response": (
            "Erkennung, Gate und Reset je System, Cutover und Ereignis",
            response.assign(
                config=response["config"].map(SYS_LABELS),
                kind=response["kind"].map(kind_labels),
            ).rename(
                columns=RESPONSE_HEADERS
                | {
                    "mean_delta": f"Tagesfehler ab Reset minus {reference} [W]",
                    "mae_delta_w": f"MAE ab Reset minus {reference} [W]",
                }
            ),
        ),
        "result_devices": (
            "Gerät je Cutover",
            device_windows.assign(kind=device_windows["kind"].map(kind_labels)).rename(
                columns=DEVICE_HEADERS
            ),
        ),
        "event_log": (
            "Tage mit new_pattern, Adaption oder Fehler",
            summary.events.assign(
                config=summary.events["config"].map(SYS_LABELS),
                kind=summary.events["kind"].map(kind_labels),
            ).rename(columns=EVENT_HEADERS),
        ),
    }

    output_directory = user_output_directory(run_directory)
    build_e1_plot(
        results,
        output_directory,
        reference_config=reference,
        kind_labels=kind_labels,
    )
    write_result_report(
        output_directory,
        title=f"E1 Neues Gerät, Lauf {run_directory.name}",
        setup={
            "Cutover": format_cutovers(cutover_dates, e1_config["cutover_ids"]),
            "Geräte": ", ".join(kind_labels[kind] for kind in devices),
            "Systeme": f"{', '.join(SYS_LABELS[system] for system in systems)}, je im vollen Kreislauf, {SYS_LABELS[reference]} nur als Bezug für die Prognosefehler",
            "LLM": f"{llm_config['model']}, Prompt {llm_config['prompt_version']}",
            "Commit": format_commit(run_config["code_version"]),
        },
        tables=tables,
        notes=[
            "Tag = Entscheidungstag seit Cutover, an Tag 1 wird der Cutover-Tag eingeordnet",
            "Gerät: vor dem Cutover aus Mains herausgerechnet, ab dem Cutover echte Mains-Reihe. keine Änderung = dieselbe Reihe mit Gerät durchgehend",
            "erstes new_pattern und Gate: gepaart wird je System gegen dessen eigenen Kontrolllauf, leer = nicht erkannt",
            "offenes Gate = Tag, an dem SYS3 das LLM fragt, States und Antworten liegen in raw/",
            f"Tagesfehler (Hauptmaß): Betrag von Prognose-Tagesmittel minus gemessenem Tagesmittel, MAE: mittlerer Stundenfehler, beide gemittelt über die Tage ab dem ersten Reset. {reference} ordnet wie die Regel ein, setzt aber nie zurück, bis zum ersten Reset laufen beide also gleich, sofern vor dem Cutover kein Reset war. Negativ = der Reset senkt den Fehler, leer = kein Reset",
            "Abdeckung Kanal vor Cutover: fehlt der Gerätekanal, bleibt das Gerät dort in Mains, der Sprung am Cutover ist dann kleiner",
            "keine Änderung: jeder Reset dort ist ein falscher",
        ],
        images=["e1_timeline.png"],
        decimals=STANDARD_CONFIG.decimals,
    )

    return output_directory


def main() -> None:
    output_directory = write_report(
        run_directory_from_argv(PROJECT_CONFIG.e1_output_dir, RUN_PREFIX)
    )

    print(f"Result written to {output_directory / 'ergebnis.md'}")


if __name__ == "__main__":
    main()
