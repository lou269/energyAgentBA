# conda activate forecasting-env
# python -m experiments.e1_seasonality.e1_report [run_directory]

from collections.abc import Mapping, Sequence
from pathlib import Path

import pandas as pd

from experiments.common.harness import read_anomaly_rows
from experiments.common.report import (
    KIND_LABELS,
    YES_NO,
    build_setup,
    criteria_table,
    format_count,
    format_number,
    split_cutover_dates,
    stichtag_labels,
    write_result_report,
)
from experiments.common.standard_config import PROJECT_CONFIG, STANDARD_CONFIG
from experiments.e1_seasonality.e1_config import RESULTS_FILE, RUN_PREFIX
from experiments.e1_seasonality.e1_evaluation import (
    summarize_detection,
    summarize_scale_onsets,
)
from src.pipeline.io import (
    RAW_SUBDIR,
    read_raw_json,
    run_directory_from_argv,
    user_output_directory,
)

EXPECTED_LABELS = {"reset": "erkannt", "alarm": "erkannt", "silent": "nicht erkannt"}
CRITERION_LABELS = {
    "built_in": ("Erkennungsrate eingebauter Anomalien", "≥ 90 %"),
    "slow_ramps": ("Erkennungsrate langsamer Rampen", "0 %"),
}


def format_day_range(mean: float, first: float, last: float, decimals: int) -> str:
    if pd.isna(mean):
        return "-"
    span = str(first) if first == last else f"{first}–{last}"
    return f"{format_number(float(mean), decimals)} ({span})"


def read_level_cases(
    raw_directory: Path,
    kinds_by_cutover: Mapping[str, Sequence[str]],
    cutover_dates: Mapping[str, str],
) -> pd.DataFrame:
    frames = [
        read_anomaly_rows(raw_directory / f"{kind}_{cutover_dates[cutover]}").assign(
            kind=kind, cutover_date=cutover_dates[cutover]
        )
        for cutover, kinds in kinds_by_cutover.items()
        for kind in kinds
        if kind not in ("control", "peak")
    ]
    return pd.concat(frames, ignore_index=True)


def build_criteria(criteria: pd.DataFrame) -> pd.DataFrame:
    return criteria_table(
        [
            (
                *CRITERION_LABELS[row["criterion"]],
                format_count(row["detected"], row["cases"], row["share_pct"]),
                row["fulfilled"],
            )
            for row in criteria.to_dict("records")
        ]
    )


def write_report(run_directory: Path) -> Path:
    run_config = read_raw_json(run_directory, "run_config")
    e1_config = run_config["e1_config"]
    standard_config = run_config["standard_config"]
    system = e1_config["system"]
    kinds_by_cutover = e1_config["kinds_by_cutover"][standard_config["split"]]
    stichtage = stichtag_labels(standard_config)
    decimals = STANDARD_CONFIG.decimals

    results = pd.read_csv(
        run_directory / RAW_SUBDIR / f"{RESULTS_FILE}.csv",
        dtype={"cutover_date": str},
    )
    summary = summarize_detection(results)
    kinds = [kind for kind in KIND_LABELS if kind in summary.overview["kind"].values]
    overview = summary.overview.set_index("kind").loc[kinds].reset_index()
    cases = (
        summary.cases.set_index("kind")
        .loc[kinds]
        .reset_index()
        .sort_values(["cutover_date"], kind="stable")
    )

    tables = {
        "result_criteria": (
            "Kriterien der Teilfrage 1",
            build_criteria(summary.criteria),
        ),
        "result_overview": (
            "Erkennung je Szenario über die Stichtage",
            pd.DataFrame(
                {
                    "Szenario": overview["kind"].map(KIND_LABELS),
                    "erwartet": overview["expected"].map(EXPECTED_LABELS),
                    "erkannt": [
                        f"{detected} von {evaluable}"
                        for detected, evaluable in zip(
                            overview["detected_evaluable"], overview["evaluable_cases"]
                        )
                    ],
                    "Erkennungstag, Mittel (Spanne)": [
                        format_day_range(mean, first, last, decimals)
                        for mean, first, last in zip(
                            overview["mean_day"],
                            overview["first_day"],
                            overview["last_day"],
                        )
                    ],
                    "auslösende Skala": overview["detecting_scales"],
                }
            ),
        ),
    }
    appendix = {
        "result_cases": (
            "Erkennung je Stichtag und Szenario",
            pd.DataFrame(
                {
                    "Stichtag": cases["cutover_date"].map(stichtage),
                    "Szenario": cases["kind"].map(KIND_LABELS),
                    "erkannt am Tag": cases["first_event_day"],
                    "auslösende Skala": cases["detecting_scales"],
                    "Tage mit Kennwert im Kontrolllauf": cases["control_signal_days"],
                    "auswertbar": cases["evaluable"].map(YES_NO),
                }
            ),
        ),
    }

    onsets = summarize_scale_onsets(
        read_level_cases(
            run_directory / RAW_SUBDIR,
            kinds_by_cutover,
            split_cutover_dates(standard_config),
        )
    )
    onsets = (
        onsets.set_index("kind")
        .loc[[kind for kind in kinds if kind in onsets["kind"].values]]
        .reset_index()
        .sort_values(["cutover_date"], kind="stable")
    )
    appendix["result_scale_onsets"] = (
        "Niveauänderungen: erster Tag, an dem die Skalen anhalten",
        pd.DataFrame(
            {
                "Stichtag": onsets["cutover_date"].map(stichtage),
                "Szenario": onsets["kind"].map(KIND_LABELS),
                "weekly hält an ab Tag": onsets["first_weekly_day"],
                "long_term hält an ab Tag": onsets["first_long_term_day"],
                "beide halten an ab Tag (Erkennung)": onsets["first_both_day"],
                "weekly davor abgerissen [mal]": onsets["weekly_breaks"],
            }
        ),
    )

    output_directory = user_output_directory(run_directory)
    write_result_report(
        output_directory,
        title="E1: Erkennung der Verbrauchsänderungen",
        setup=build_setup(
            run_directory.name,
            standard_config,
            list(kinds_by_cutover),
            run_config["code_version"],
            scenarios=", ".join(kinds),
            systems=f"{system}, die Regel ordnet ein, keine Adaption, kein Sprachmodell",
        ),
        tables=tables,
        appendix=appendix,
        notes=[
            "Tag = Entscheidungstag seit dem Stichtag, an Tag 1 wird der Stichtag selbst eingeordnet",
            "erkannt: Lastspitze = Einzelanomalie (Skala daily oder weekday) an Tag 1, Dauerlast und Rampe = anhaltende Veränderung (weekly und long_term an 6 von 7 Tagen). Gezählt wird der erste Tag, an dem der Szenariolauf den Kennwert hat und der Kontrolllauf desselben Stichtags nicht",
            "auswertbar: zeigt der Kontrolllauf am Einbautag der Lastspitze schon eine Einzelanomalie, geht der Fall nicht in die Zählung ein",
            "erwartet: die Rampe über 56 Tage soll nicht als anhaltende Veränderung erkannt werden",
            f"Anhaltende Veränderungen werden im Mittel an Tag {format_number(summary.sustained_mean_day, decimals)} erkannt (Dauerlast und Rampe über 28 Tage)",
            "Erkennungstag, Mittel (Spanne): nur über die erkannten Fälle, bei der Lastspitze entfällt er, sie zählt nur an Tag 1",
            "Skalen anhaltend: weekly bzw. long_term liegt an 6 der letzten 7 Tage über der Schwelle, eine anhaltende Veränderung gilt erst, wenn beide gleichzeitig anhalten. Abgerissen zählt, wie oft weekly vor diesem Tag wieder unter 6 von 7 Tagen fiel",
        ],
        images=[],
        decimals=decimals,
    )

    return output_directory


def main() -> None:
    output_directory = write_report(
        run_directory_from_argv(PROJECT_CONFIG.e1_output_dir, RUN_PREFIX)
    )

    print(f"Result written to {output_directory / 'ergebnis.md'}")


if __name__ == "__main__":
    main()
