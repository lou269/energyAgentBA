# conda activate forecasting-env
# python -m experiments.e3_saisonality.e3_report [run_directory]

from pathlib import Path

import pandas as pd

from experiments.common.report import (
    KIND_LABELS,
    format_commit,
    format_cutovers,
    key_figures_table,
    write_result_report,
)
from experiments.common.standard_config import DECIMALS, PROJECT_CONFIG
from experiments.e3_saisonality.e3_config import RESULTS_FILE, RUN_PREFIX
from experiments.e3_saisonality.e3_evaluation import summarize_ramp_response
from src.config.config_forecasting import SYS_LABELS
from src.pipeline.io import (
    RAW_SUBDIR,
    read_raw_json,
    run_directory_from_argv,
    user_output_directory,
)

REPEAT_HEADERS = {"kind": "Ereignis", "mean": "Mittel", "detected": "erkannt"}


def write_report(run_directory: Path) -> Path:
    run_config = read_raw_json(run_directory, "run_config")
    e3_config = run_config["e3_config"]
    event_kinds = [kind for kind in e3_config["kinds"] if kind != "control"]

    results = pd.read_csv(
        run_directory / RAW_SUBDIR / f"{RESULTS_FILE}.csv",
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
            "Cutover": format_cutovers(
                run_config["standard_config"]["cutover_dates"], e3_config["cutovers"]
            ),
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
    output_directory = write_report(
        run_directory_from_argv(PROJECT_CONFIG.e3_output_dir, RUN_PREFIX)
    )

    print(f"Result written to {output_directory / 'ergebnis.md'}")


if __name__ == "__main__":
    main()
