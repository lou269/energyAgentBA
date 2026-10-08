# conda activate forecasting-env
# python -m experiments.k3_adaptation.k3_report [strategies|masking] [run_directory]

import sys
from pathlib import Path

import pandas as pd

from docs.plots.plot_k3_adaptation_strategies import build_k3_plot
from experiments.common.report import (
    KIND_LABELS,
    format_commit,
    format_cutovers,
    format_number,
    key_figures_table,
    relabel,
    write_result_report,
)
from experiments.common.evaluation import ALL_DAYS
from experiments.common.standard_config import PROJECT_CONFIG, STANDARD_CONFIG
from experiments.k3_adaptation.k3_config import (
    MASKING_RESULTS_FILE,
    MASKING_RUN_PREFIX,
    RESULTS_FILE,
    RUN_PREFIX,
    K3Config,
)
from experiments.k3_adaptation.k3_evaluation import (
    StrategyKeyFigures,
    summarize_error_curve,
    pair_masking,
    pair_with_none,
    summarize_after_trigger,
    summarize_bias_after_cutover,
    summarize_effect,
    summarize_masking,
    summarize_masking_by_cutover,
    summarize_masking_key_figures,
    summarize_strategy_key_figures,
)
from src.config.config_forecasting import SYS_VARIANTS
from src.pipeline.io import (
    RAW_SUBDIR,
    read_raw_json,
    run_directory_from_argv,
    user_output_directory,
)

STRATEGY_LABELS: dict[str, str] = {
    "none": "keine Aktion",
    "cut": "Reset, Historie ab t_c",
    "step_regressor": "Stufen-Regressor",
}

MASKING_PHASE_LABELS: dict[str, str] = {
    "before_cutover": "vor Cutover",
    "before_peak": "bis zur ersten Spitze",
    "in_window": "Spitzen im Trainingsfenster",
    "after_window": "danach",
    ALL_DAYS: "alle Tage",
}

# Name und Einheit je Fehlerspalte, die Tabellen des MAE behalten ihre Dateinamen
METRIC_LABELS: dict[str, tuple[str, str]] = {
    "mae_w": ("MAE", "W"),
    "day_error_w": ("Tagesfehler", "W"),
}
METRIC_FILE_SUFFIX: dict[str, str] = {"mae_w": "", "day_error_w": "_day_error"}

HEADERS = {
    "kind": "Ereignis",
    "trigger_day": "Aktion an Tag nach Cutover",
    "strategy": "Aktion",
    "mean": "Mittel",
    "improved": "Cutover besser",
    "mean_pct": "Mittel in % des Fehlers ohne Aktion",
}
MASKING_HEADERS = {
    "kind": "Ereignis",
    "phase": "Zeitraum",
    "days": "Tage",
    "mean": "Mittel",
    "improved": "Cutover besser",
}


def _labeled(table: pd.DataFrame) -> pd.DataFrame:
    return relabel(
        table.assign(trigger_day=table["trigger_day"].astype(int)),
        HEADERS,
        {"kind": KIND_LABELS, "strategy": STRATEGY_LABELS},
    )


def _labeled_bias(table: pd.DataFrame) -> pd.DataFrame:
    labeled = table.rename(index=KIND_LABELS, columns=lambda day: f"Tag {day}")

    return labeled.rename_axis(index="Ereignis", columns=None).reset_index()


def build_setup(run_config: dict, evaluation_days: int) -> dict[str, str]:
    standard_config, k3_config = run_config["standard_config"], run_config["k3_config"]

    return {
        "Cutover": format_cutovers(
            standard_config, k3_config["cutovers"][standard_config["split"]]
        ),
        "Ereignis": (
            "Sprung, jede Stunde × "
            f"{format_number(standard_config['scale_factor'], STANDARD_CONFIG.decimals)}"
        ),
        "Aktion": (
            f"fest an Tag {' und '.join(str(day) for day in k3_config['trigger_days'])} nach dem Cutover (Orakel), "
            "Historie ab t_c wie die Adaptionsregel"
        ),
        "Auswertung": (
            f"{evaluation_days} Prognosetage ab dem Tag der Aktion, "
            "Differenz zu keiner Aktion am selben Tag"
        ),
        "Commit": format_commit(run_config["code_version"]),
    }


def build_key_figures(key: StrategyKeyFigures, metric: str) -> pd.DataFrame:
    kind_label = KIND_LABELS[key.kind]
    metric_label, unit = METRIC_LABELS[metric]

    rows = [
        (
            f"{STRATEGY_LABELS[row['strategy']]}, Aktion an Tag {key.earliest}: Differenz zu keiner Aktion bei {kind_label} [{unit}]",
            row["mean"],
            f"{format_number(row['mean_pct'], STANDARD_CONFIG.decimals)} % des Fehlers ohne Aktion, bei {row['improved']} Cutover besser",
        )
        for row in key.earliest_rows.to_dict("records")
    ]
    rows.append(
        (
            f"Aktion an Tag {key.latest}: beste Differenz bei {kind_label} [{unit}]",
            key.latest_best_w,
            "späte Erkennung",
        )
    )
    return key_figures_table(rows)


def build_strategy_tables(
    results: pd.DataFrame, k3_config: K3Config, metric: str
) -> dict[str, tuple[str, pd.DataFrame]]:
    paired = pair_with_none(results, k3_config.evaluation_days, metric)
    effect = summarize_effect(summarize_after_trigger(paired, metric), metric)
    metric_label, unit = METRIC_LABELS[metric]
    suffix = METRIC_FILE_SUFFIX[metric]

    return {
        f"key_figures{suffix}": (
            f"Kennzahlen {metric_label}",
            build_key_figures(
                summarize_strategy_key_figures(effect, kind=k3_config.key_figure_kind),
                metric,
            ),
        ),
        f"result_delta{suffix}": (
            f"Differenz der Aktion zu keiner Aktion ({metric_label}), Mittel über {k3_config.evaluation_days} Prognosetage ab der Aktion, je Cutover [{unit}], negativ = besser",
            _labeled(effect),
        ),
    }


def report_strategies(run_directory: Path, k3_config: K3Config) -> Path:
    run_config = read_raw_json(run_directory, "run_config")

    results = pd.read_csv(
        run_directory / RAW_SUBDIR / f"{RESULTS_FILE}.csv", dtype={"cutover_date": str}
    )
    # ältere Läufe haben noch control und step, die hier nicht mehr gebraucht werden
    results = results.loc[results["kind"].isin(k3_config.kinds)]

    tables: dict[str, tuple[str, pd.DataFrame]] = {}
    for metric in k3_config.error_metrics:
        tables.update(build_strategy_tables(results, k3_config, metric))

    # ältere Läufe haben die Abweichung mit Vorzeichen noch nicht
    if "day_bias_w" in results.columns:
        tables["result_bias"] = (
            "Prognose minus Messung beim Tagesmittel ohne Aktion, Mittel über die Cutover, je Tag seit Cutover [W], negativ = Prognose zu niedrig",
            _labeled_bias(
                summarize_bias_after_cutover(
                    results, k3_config.bias_first_day, k3_config.bias_last_day
                )
            ),
        )

    output_directory = user_output_directory(run_directory)
    paired = pair_with_none(results, k3_config.evaluation_days, "mae_w")
    build_k3_plot(
        summarize_error_curve(paired, "mae_w"),
        output_directory,
        kind=k3_config.key_figure_kind,
        kind_label=KIND_LABELS[k3_config.key_figure_kind],
        strategy_labels=STRATEGY_LABELS,
    )

    write_result_report(
        output_directory,
        title=f"K3 Adaptionsstrategien, Lauf {run_directory.name}",
        setup=build_setup(run_config, k3_config.evaluation_days),
        tables=tables,
        notes=[
            "Differenz: Fehler mit Aktion minus Fehler ohne Aktion, tageweise auf denselben Daten, über die Tage ab der Aktion gemittelt",
            "Cutover besser: Zahl der Cutover, bei denen die Differenz unter null liegt. Die Fenster überlappen, einzelne Cutover sind nicht unabhängig",
            "Tagesfehler: Betrag der Differenz zwischen prognostiziertem und gemessenem Tagesmittel (Tagesenergie), wie in K4, nur Tage mit lauter bewerteten Stunden. Gegenläufige Stundenfehler gleichen sich dabei aus",
        ],
        images=["k3_error_curve.png"],
        decimals=STANDARD_CONFIG.decimals,
    )

    return output_directory


# Teil 2: peak/low nur für Prophet ausblenden


def build_masking_key_figures(overall: pd.DataFrame, metric: str) -> pd.DataFrame:
    metric_label, unit = METRIC_LABELS[metric]

    return key_figures_table(
        [
            (
                f"Ausblenden bei {KIND_LABELS[row['kind']]}: {metric_label}-Differenz [{unit}]",
                row["mean"],
                f"bei {format_number(row['none'], STANDARD_CONFIG.decimals)} {unit} ohne Ausblenden, "
                f"{row['days']} Tage, bei {row['improved']} Cutover besser",
            )
            for row in overall.to_dict("records")
        ]
    )


def report_masking(run_directory: Path, k3_config: K3Config) -> Path:
    run_config = read_raw_json(run_directory, "run_config")

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
    first_day, last_day = min(event_day_numbers), max(event_day_numbers)

    tables: dict[str, tuple[str, pd.DataFrame]] = {}
    for metric in k3_config.error_metrics:
        metric_label, unit = METRIC_LABELS[metric]
        suffix = METRIC_FILE_SUFFIX[metric]
        summary = summarize_masking_by_cutover(
            paired,
            first_day,
            last_day,
            window_days,  # type: ignore
            metric,
        )
        table = summarize_masking(summary, metric)
        key_figures = summarize_masking_key_figures(summary, table, metric)

        tables[f"key_figures{suffix}"] = (
            f"Kennzahlen {metric_label}",
            build_masking_key_figures(key_figures, metric),
        )
        tables[f"result_masking{suffix}"] = (
            f"{metric_label} mask minus replay je Cutover [{unit}], negativ = besser",
            relabel(
                table,
                MASKING_HEADERS,
                {"kind": KIND_LABELS, "phase": MASKING_PHASE_LABELS},
            ),
        )

    output_directory = user_output_directory(run_directory)
    write_result_report(
        output_directory,
        title=f"K3 Teil 2, Spitzen-Tage für Prophet ausblenden, Lauf {run_directory.name}",
        setup={
            "Cutover": format_cutovers(
                run_config["standard_config"],
                run_config["k3_config"]["cutovers"][
                    run_config["standard_config"]["split"]
                ],
            ),
            "Ereignis": f"{KIND_LABELS[k3_config.masking_events[0][1]]} an Tag {', '.join(str(day) for day in event_day_numbers)} nach dem Cutover (Orakel, ohne Einordnung)",
            "Vergleich": f"Ereignistage für Prophet ausgeblendet (mask) gegen nicht ausgeblendet (none), {window_days} Tage Trainingsfenster",
            "Commit": format_commit(run_config["code_version"]),
        },
        tables=tables,
        notes=[
            "mask minus none: negativ = Ausblenden besser, beide gegen dieselbe Reihe mit Spitzen bewertet, ausgeblendet ist nur das Training",
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
