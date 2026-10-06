# conda activate forecasting-env
# python -m experiments.e3_saisonality.e3_report [run_directory]

from pathlib import Path

import pandas as pd

from experiments.common.evaluation import EVENT_KEYS
from experiments.common.report import (
    KIND_LABELS,
    format_commit,
    format_cutovers,
    write_result_report,
)
from experiments.common.standard_config import PROJECT_CONFIG, STANDARD_CONFIG
from experiments.e3_seasonality.e3_config import RESULTS_FILE, RUN_PREFIX
from experiments.e3_seasonality.e3_evaluation import summarize_drift_response
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


def write_report(run_directory: Path) -> Path:
    run_config = read_raw_json(run_directory, "run_config")
    e3_config = run_config["e3_config"]
    llm_config = run_config["llm_config"]
    cutover_dates = run_config["standard_config"]["cutover_dates"]
    reference = e3_config["reference_system"]
    systems = [e3_config["rule_system"], e3_config["llm_system"]]
    kinds_by_cutover = e3_config["kinds_by_cutover"]
    rows = [
        (system, cutover_dates[cutover_id], kind)
        for system in systems
        for cutover_id, kinds in kinds_by_cutover.items()
        for kind in kinds
    ]

    results = pd.read_csv(
        run_directory / RAW_SUBDIR / f"{RESULTS_FILE}.csv",
        dtype={"cutover_date": str},
    )
    response = (
        summarize_drift_response(results, reference)
        .response.set_index(EVENT_KEYS)
        .loc[rows]
        .reset_index()
    )

    tables = {
        "result_response": (
            "Erkennung, Gate und Reset je System, Cutover und Ereignis",
            response.assign(
                config=response["config"].map(SYS_LABELS),
                kind=response["kind"].map(KIND_LABELS),
            ).rename(
                columns=RESPONSE_HEADERS
                | {
                    "mean_delta": f"Tagesfehler ab Reset minus {reference} [W]",
                    "mae_delta_w": f"MAE ab Reset minus {reference} [W]",
                }
            ),
        ),
    }

    output_directory = user_output_directory(run_directory)
    write_result_report(
        output_directory,
        title=f"E3 Saisonaler Drift, Lauf {run_directory.name}",
        setup={
            "Cutover und Ereignisse": "; ".join(
                f"{format_cutovers(cutover_dates, [cutover_id])}: "
                + ", ".join(KIND_LABELS[kind] for kind in kinds)
                for cutover_id, kinds in kinds_by_cutover.items()
            ),
            "Systeme": f"{', '.join(SYS_LABELS[system] for system in systems)}, je im vollen Kreislauf, {SYS_LABELS[reference]} nur als Bezug für die Prognosefehler",
            "LLM": f"{llm_config['model']}, Prompt {llm_config['prompt_version']}",
            "Commit": format_commit(run_config["code_version"]),
        },
        tables=tables,
        notes=[
            "Tag = Entscheidungstag seit Cutover, an Tag 1 wird der Cutover-Tag eingeordnet",
            "erwartet: Rampe über 28 Tage ist ein neues Muster, Rampe über 56 Tage nicht, dort ist still aufnehmen richtig und ein Reset ein Fehler",
            "erstes new_pattern und Gate: gepaart wird je System gegen dessen eigenen Kontrolllauf, leer = still aufgenommen",
            "offenes Gate = Tag, an dem SYS3 das LLM fragt, States und Antworten liegen in raw/",
            f"Tagesfehler (Hauptmaß): Betrag von Prognose-Tagesmittel minus gemessenem Tagesmittel, MAE: mittlerer Stundenfehler, beide gemittelt über die Tage ab dem ersten Reset. {reference} ordnet wie die Regel ein, setzt aber nie zurück, bis zum ersten Reset laufen beide also gleich, sofern vor dem Cutover kein Reset war. Negativ = der Reset senkt den Fehler, leer = kein Reset",
            "keine Änderung: jeder Reset dort ist ein falscher",
        ],
        images=[],
        decimals=STANDARD_CONFIG.decimals,
    )

    return output_directory


def main() -> None:
    output_directory = write_report(
        run_directory_from_argv(PROJECT_CONFIG.e3_output_dir, RUN_PREFIX)
    )

    print(f"Result written to {output_directory / 'ergebnis.md'}")


if __name__ == "__main__":
    main()
