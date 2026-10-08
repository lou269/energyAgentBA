# conda activate forecasting-env
# python -m experiments.e1_seasonality.e1_report [run_directory]

from pathlib import Path

import pandas as pd

from experiments.common.evaluation import EVENT_KEYS
from experiments.common.report import (
    KIND_LABELS,
    format_commit,
    format_cutovers,
    split_cutover_dates,
    write_result_report,
)
from experiments.common.standard_config import PROJECT_CONFIG, STANDARD_CONFIG
from experiments.e1_seasonality.e1_config import RESULTS_FILE, RUN_PREFIX
from experiments.e1_seasonality.e1_evaluation import summarize_drift_response
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
    "first_gate_day": "erster Tag Gate offen",
    "trigger_scale": "Skala",
    "first_event_new_pattern_day": "erstes new_pattern (Tag)",
    "gate_open_days": "Tage Gate offen",
    "control_gate_open_days": "Tage Gate offen im Kontrolllauf",
}


def write_report(run_directory: Path) -> Path:
    run_config = read_raw_json(run_directory, "run_config")
    e1_config = run_config["e1_config"]
    standard_config = run_config["standard_config"]
    cutover_dates = split_cutover_dates(standard_config)
    system = e1_config["system"]
    kinds_by_cutover = e1_config["kinds_by_cutover"][standard_config["split"]]
    rows = [
        (system, cutover_dates[cutover_id], kind)
        for cutover_id, kinds in kinds_by_cutover.items()
        for kind in kinds
    ]

    results = pd.read_csv(
        run_directory / RAW_SUBDIR / f"{RESULTS_FILE}.csv",
        dtype={"cutover_date": str},
    )
    response = (
        summarize_drift_response(results)
        .response.set_index(EVENT_KEYS)
        .loc[rows]
        .reset_index()
    )

    tables = {
        "result_response": (
            "Erkennung je Cutover und Ereignis",
            response.assign(
                config=response["config"].map(SYS_LABELS),
                kind=response["kind"].map(KIND_LABELS),
            ).rename(columns=RESPONSE_HEADERS),
        ),
    }

    output_directory = user_output_directory(run_directory)
    write_result_report(
        output_directory,
        title=f"E1 Erkennung, Lauf {run_directory.name}",
        setup={
            "Cutover und Ereignisse": "; ".join(
                f"{format_cutovers(standard_config, [cutover_id])}: "
                + ", ".join(KIND_LABELS[kind] for kind in kinds)
                for cutover_id, kinds in kinds_by_cutover.items()
            ),
            "System": f"{SYS_LABELS[system]}, die Regel ordnet ein, keine Adaption, kein LLM",
            "Commit": format_commit(run_config["code_version"]),
        },
        tables=tables,
        notes=[
            "Tag = Entscheidungstag seit Cutover, an Tag 1 wird der Cutover-Tag eingeordnet",
            "erwartet: Rampe über 28 Tage ist ein neues Muster, Rampe über 56 Tage nicht, dort ist still aufnehmen richtig",
            "erster Tag Gate offen, erstes new_pattern und Tage Gate offen: gepaart gegen den Kontrolllauf desselben Cutovers, leer = nie. Skala = Skala des ersten Gate-Tags (Spitze: dominante Skala, Niveauänderung: Skalen mit anhaltender Abweichung)",
            "Tage Gate offen im Kontrolllauf: Tage ab Cutover, an denen das Gate auch ohne Ereignis offen ist (echte Saison, Rauschen). Ohne Adaption wird die Referenz nie bereinigt, die Zahl ist daher höher als im Gesamtsystem",
            "offenes Gate = Tag, an dem in SYS2 und SYS3 die Einordnung gefragt wird",
        ],
        images=[],
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
