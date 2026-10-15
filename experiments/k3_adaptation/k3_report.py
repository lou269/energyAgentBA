# conda activate forecasting-env
# python -m experiments.k3_adaptation.k3_report [strategies|masking] [run_directory]

import sys
from pathlib import Path

import pandas as pd

from experiments.common.report import (
    KIND_LABELS,
    build_setup,
    relabel,
    stichtag_labels,
    write_result_report,
)
from experiments.common.standard_config import PROJECT_CONFIG, STANDARD_CONFIG
from experiments.k3_adaptation.k3_config import (
    MASKING_RESULTS_FILE,
    MASKING_RUN_PREFIX,
    RESULTS_FILE,
    RUN_PREFIX,
    K3Config,
)
from experiments.k3_adaptation.k3_evaluation import (
    pair_masking,
    pair_with_none,
    summarize_after_trigger,
    summarize_effect,
    summarize_masking,
    summarize_masking_by_cutover,
)
from src.config.config_forecasting import SYS_VARIANTS
from src.pipeline.io import (
    RAW_SUBDIR,
    read_raw_json,
    run_directory_from_argv,
    user_output_directory,
)

METRIC = "day_error_w"

STRATEGY_LABELS: dict[str, str] = {
    "none": "keine Aktion",
    "cut": "Zurücksetzen",
    "step_regressor": "Stufenregressor",
}

HEADERS = {
    "kind": "Szenario",
    "trigger_day": "Aktionstag",
    "strategy": "Aktion",
    "mean": "Mittel",
    "improved": "Stichtage besser",
    "mean_pct": "Mittel [%]",
}
MASKING_HEADERS = {
    "kind": "Szenario",
    "days": "Tage",
    "none": "ohne Ausblenden [W]",
    "mean": "Mittel",
    "improved": "Stichtage besser",
}


def _labeled(table: pd.DataFrame, stichtage: dict[str, str]) -> pd.DataFrame:
    labeled = relabel(
        table.assign(trigger_day=table["trigger_day"].astype(int)),
        HEADERS,
        {"kind": KIND_LABELS, "strategy": STRATEGY_LABELS},
    )

    return labeled.rename(columns=stichtage)


def report_strategies(run_directory: Path, k3_config: K3Config) -> Path:
    run_config = read_raw_json(run_directory, "run_config")
    standard_config = run_config["standard_config"]

    results = pd.read_csv(
        run_directory / RAW_SUBDIR / f"{RESULTS_FILE}.csv", dtype={"cutover_date": str}
    )
    # ältere Läufe haben noch control und step, die hier nicht mehr gebraucht werden
    results = results.loc[results["kind"].isin(k3_config.kinds)]

    paired = pair_with_none(results, k3_config.evaluation_days, METRIC)
    effect = summarize_effect(summarize_after_trigger(paired, METRIC), METRIC)

    output_directory = user_output_directory(run_directory)
    write_result_report(
        output_directory,
        title="K3: Adaptionsstrategien",
        setup=build_setup(
            run_directory.name,
            standard_config,
            run_config["k3_config"]["cutovers"][standard_config["split"]],
            run_config["code_version"],
            scenarios=", ".join(k3_config.kinds),
            details={
                "Aktionstage": f"fest an Tag {' und '.join(str(day) for day in run_config['k3_config']['trigger_days'])} nach dem Stichtag (Orakel, ohne Einordnung), Historie ab t_c wie die Adaptionsregel",
                "Auswertung": f"{k3_config.evaluation_days} Prognosetage ab dem Tag der Aktion",
            },
        ),
        tables={
            "result_delta": (
                "Differenz des Tagesfehlers zu keiner Aktion [W], negativ = besser",
                _labeled(effect, stichtag_labels(standard_config)),
            )
        },
        notes=[
            "Differenz: Tagesfehler mit Aktion minus Tagesfehler ohne Aktion, tageweise auf denselben Daten, über die Tage ab der Aktion gemittelt",
            "Stichtage besser: Zahl der Stichtage, bei denen die Differenz unter null liegt. Die Fenster überlappen, einzelne Stichtage sind nicht unabhängig",
            "Tagesfehler: Betrag der Differenz zwischen prognostiziertem und gemessenem Tagesmittel, wie in K4, nur Tage mit lauter bewerteten Stunden",
        ],
        images=[],
        decimals=STANDARD_CONFIG.decimals,
    )

    return output_directory


# Teil 2: peak/low nur für Prophet ausblenden


def report_masking(run_directory: Path, k3_config: K3Config) -> Path:
    run_config = read_raw_json(run_directory, "run_config")
    standard_config = run_config["standard_config"]

    results = pd.read_csv(
        run_directory / RAW_SUBDIR / f"{MASKING_RESULTS_FILE}.csv",
        dtype={"cutover_date": str},
    )
    paired = pair_masking(results, k3_config.error_metrics)
    # so viele Tage steckt eine Spitze im Trainingsfenster der Prognose
    window_days = SYS_VARIANTS[
        k3_config.cycle_system
    ].forecasting_config.selected_prophet_variant.rolling_window_days

    event_day_numbers = [day for day, _kind in k3_config.masking_events]
    summary = summarize_masking_by_cutover(
        paired,
        min(event_day_numbers),
        max(event_day_numbers),
        window_days,  # type: ignore
        METRIC,
    )
    table = summarize_masking(summary, METRIC)

    output_directory = user_output_directory(run_directory)
    write_result_report(
        output_directory,
        title="K3 Teil 2: Spitzen-Tage ausblenden",
        setup=build_setup(
            run_directory.name,
            standard_config,
            run_config["k3_config"]["cutovers"][standard_config["split"]],
            run_config["code_version"],
            scenarios=f"{KIND_LABELS[k3_config.masking_events[0][1]]} an Tag {', '.join(str(day) for day in event_day_numbers)} nach dem Stichtag (Orakel, ohne Einordnung)",
            details={
                "Vergleich": f"Ereignistage für Prophet ausgeblendet (mask) gegen nicht ausgeblendet (none), {window_days} Tage Trainingsfenster"
            },
        ),
        tables={
            "result_masking": (
                "Differenz des Tagesfehlers mask minus none [W], negativ = Ausblenden besser",
                relabel(
                    table,
                    MASKING_HEADERS,
                    {"kind": KIND_LABELS},
                ).rename(columns=stichtag_labels(standard_config)),
            )
        },
        notes=[
            "mask minus none: beide gegen dieselbe Reihe mit Spitzen bewertet, ausgeblendet ist nur das Training",
            "Tagesfehler wie in Teil 1: Tage mit unvollständig bewerteten Stunden zählen dort nicht mit",
        ],
        images=[],
        decimals=STANDARD_CONFIG.decimals,
    )

    return output_directory


def main() -> None:
    part = sys.argv[1] if len(sys.argv) > 1 else "strategies"
    prefix = RUN_PREFIX if part == "strategies" else MASKING_RUN_PREFIX
    run_directory = run_directory_from_argv(PROJECT_CONFIG.k3_output_dir, prefix, 2)
    # Kennzahlen aus der aktuellen Config, ältere Läufe haben sie nicht in run_config
    k3_config = K3Config()

    if part == "strategies":
        output_directory = report_strategies(run_directory, k3_config)
    else:
        output_directory = report_masking(run_directory, k3_config)

    print(f"Result written to {output_directory / 'ergebnis.md'}")


if __name__ == "__main__":
    main()
