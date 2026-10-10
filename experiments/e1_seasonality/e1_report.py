# conda activate forecasting-env
# python -m experiments.e1_seasonality.e1_report [run_directory]

from pathlib import Path

import pandas as pd

from experiments.common.report import (
    KIND_LABELS,
    format_commit,
    format_cutovers,
    write_result_report,
)
from experiments.common.standard_config import PROJECT_CONFIG, STANDARD_CONFIG
from experiments.e1_seasonality.e1_config import RESULTS_FILE, RUN_PREFIX
from experiments.e1_seasonality.e1_evaluation import summarize_detection
from src.config.config_forecasting import SYS_LABELS
from src.pipeline.io import (
    RAW_SUBDIR,
    read_raw_json,
    run_directory_from_argv,
    user_output_directory,
)

EXPECTED_LABELS = {"reset": "auffällig", "alarm": "auffällig", "silent": "unauffällig"}


def format_range(first: float, last: float) -> str:
    if pd.isna(first):
        return "-"
    return str(first) if first == last else f"{first}–{last}"


def write_report(run_directory: Path) -> Path:
    run_config = read_raw_json(run_directory, "run_config")
    e1_config = run_config["e1_config"]
    standard_config = run_config["standard_config"]
    system = e1_config["system"]
    kinds_by_cutover = e1_config["kinds_by_cutover"][standard_config["split"]]

    results = pd.read_csv(
        run_directory / RAW_SUBDIR / f"{RESULTS_FILE}.csv",
        dtype={"cutover_date": str},
    )
    summary = summarize_detection(results)
    kinds = [kind for kind in KIND_LABELS if kind in summary.overview["kind"].values]
    overview = summary.overview.set_index("kind").loc[kinds].reset_index()
    cases = summary.cases.set_index("kind").loc[kinds].reset_index()

    tables = {
        "result_overview": (
            "Erkennung je Ereignis über alle Cutover",
            pd.DataFrame(
                {
                    "Ereignis": overview["kind"].map(KIND_LABELS),
                    "erwartet": overview["expected"].map(EXPECTED_LABELS),
                    "erkannt": overview["detected"].astype(str)
                    + "/"
                    + overview["cases"].astype(str),
                    "Ø Tag": overview["mean_day"],
                    "Tag min–max": [
                        format_range(first, last)
                        for first, last in zip(
                            overview["first_day"], overview["last_day"]
                        )
                    ],
                    "Skala (Spitze)": overview["trigger_scale"],
                    "Kontrolle mit Signal [Tage]": [
                        format_range(first, last)
                        for first, last in zip(
                            overview["control_days_min"],
                            overview["control_days_max"],
                        )
                    ],
                }
            ),
        ),
    }
    appendix = {
        "result_cases": (
            "Erkennung je Cutover und Ereignis",
            pd.DataFrame(
                {
                    "Cutover": cases["cutover_date"],
                    "Ereignis": cases["kind"].map(KIND_LABELS),
                    "erkannt am Tag": cases["first_event_day"],
                    "Skala (Spitze)": cases["trigger_scale"],
                    "Kontrolle mit Signal [Tage]": cases["control_signal_days"],
                }
            ),
        ),
    }

    output_directory = user_output_directory(run_directory)
    write_result_report(
        output_directory,
        title=f"E1 Erkennung, Lauf {run_directory.name}",
        setup={
            "Cutover": format_cutovers(standard_config, list(kinds_by_cutover)),
            "System": f"{SYS_LABELS[system]}, die Regel ordnet ein, keine Adaption, kein LLM",
            "Commit": format_commit(run_config["code_version"]),
        },
        tables=tables,
        appendix=appendix,
        notes=[
            "Tag = Entscheidungstag seit Cutover, an Tag 1 wird der Cutover-Tag eingeordnet",
            "erkannt: Spitze = Einzeltag-Alarm (daily oder weekday) an Tag 1, dem Tag ihres Einbaus, Niveauänderung und Rampe = Streak auf mehreren Skalen gleichzeitig (weekly und long_term). Gezählt wird der erste Tag, an dem das Ereignis den Kennwert hat und der Kontrolllauf desselben Cutovers nicht",
            "erwartet: auffällig = der Vorfilter soll das Ereignis melden, unauffällig = still bleiben (Rampe über 56 Tage gilt nicht als Ereignis). Kein Maß für die Einordnung",
            "Ø Tag und Tag min–max nur über die erkannten Fälle, nicht erkannt = nie innerhalb des Fensters. Bei der Spitze entfallen sie, sie zählt nur an Tag 1",
            "Skala (Spitze): dominante Einzeltag-Skala am Erkennungstag, bei Niveau und Rampen gilt immer der Streak auf weekly und long_term",
            "Kontrolle mit Signal: Tage ab Cutover (Spitze: Tag 1), an denen der Kontrolllauf denselben Kennwert hat (echte Saison, Rauschen), min–max über die Cutover.",
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
