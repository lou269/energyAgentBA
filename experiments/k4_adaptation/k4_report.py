# conda activate forecasting-env
# python -m experiments.k4_adaptation.k4_report [strategies|masking] [run_directory]

import sys
from pathlib import Path

import pandas as pd

from docs.plots.plot_k4_adaptation_strategies import build_k4_plot
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
from experiments.k4_adaptation.k4_config import (
    MASKING_DECISIONS_FILE,
    MASKING_RESULTS_FILE,
    MASKING_RUN_PREFIX,
    RESULTS_FILE,
    RUN_PREFIX,
    K4Config,
)
from experiments.k4_adaptation.k4_evaluation import (
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
    summarize_replay_match,
    summarize_strategy_key_figures,
)
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
    "early": f"Tag 0-{K4Config.masking_early_days - 1}",
    "late": f"ab Tag {K4Config.masking_early_days}",
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
    "masked_days": "ausgeblendet",
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
    standard_config, k4_config = run_config["standard_config"], run_config["k4_config"]

    return {
        "Cutover": format_cutovers(
            standard_config["cutover_dates"], k4_config["cutovers"]
        ),
        "Ereignis": (
            "Sprung, jede Stunde × "
            f"{format_number(standard_config['scale_factor'], STANDARD_CONFIG.decimals)}"
        ),
        "Aktion": (
            f"fest an Tag {' und '.join(str(day) for day in k4_config['trigger_days'])} nach dem Cutover (Orakel), "
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
    results: pd.DataFrame, k4_config: K4Config, metric: str
) -> dict[str, tuple[str, pd.DataFrame]]:
    paired = pair_with_none(results, k4_config.evaluation_days, metric)
    effect = summarize_effect(summarize_after_trigger(paired, metric), metric)
    metric_label, unit = METRIC_LABELS[metric]
    suffix = METRIC_FILE_SUFFIX[metric]

    return {
        f"key_figures{suffix}": (
            f"Kennzahlen {metric_label}",
            build_key_figures(
                summarize_strategy_key_figures(effect, kind=k4_config.key_figure_kind),
                metric,
            ),
        ),
        f"result_delta{suffix}": (
            f"Differenz der Aktion zu keiner Aktion ({metric_label}), Mittel über {k4_config.evaluation_days} Prognosetage ab der Aktion, je Cutover [{unit}], negativ = besser",
            _labeled(effect),
        ),
    }


def report_strategies(run_directory: Path, k4_config: K4Config) -> Path:
    run_config = read_raw_json(run_directory, "run_config")

    results = pd.read_csv(
        run_directory / RAW_SUBDIR / f"{RESULTS_FILE}.csv", dtype={"cutover_date": str}
    )
    # ältere Läufe haben noch control und step, die hier nicht mehr gebraucht werden
    results = results.loc[results["kind"].isin(k4_config.kinds)]

    tables: dict[str, tuple[str, pd.DataFrame]] = {}
    for metric in k4_config.error_metrics:
        tables.update(build_strategy_tables(results, k4_config, metric))

    # ältere Läufe haben die Abweichung mit Vorzeichen noch nicht
    if "day_bias_w" in results.columns:
        tables["result_bias"] = (
            "Prognose minus Messung beim Tagesmittel ohne Aktion, Mittel über die Cutover, je Tag seit Cutover [W], negativ = Prognose zu niedrig",
            _labeled_bias(
                summarize_bias_after_cutover(
                    results, k4_config.bias_first_day, k4_config.bias_last_day
                )
            ),
        )

    output_directory = user_output_directory(run_directory)
    paired = pair_with_none(results, k4_config.evaluation_days, "mae_w")
    build_k4_plot(
        summarize_error_curve(paired, "mae_w"),
        output_directory,
        kind=k4_config.key_figure_kind,
        kind_label=KIND_LABELS[k4_config.key_figure_kind],
        strategy_labels=STRATEGY_LABELS,
    )

    write_result_report(
        output_directory,
        title=f"K4 Adaptionsstrategien, Lauf {run_directory.name}",
        setup=build_setup(run_config, k4_config.evaluation_days),
        tables=tables,
        notes=[
            "Differenz: Fehler mit Aktion minus Fehler ohne Aktion, tageweise auf denselben Daten, über die Tage ab der Aktion gemittelt",
            "Cutover besser: Zahl der Cutover, bei denen die Differenz unter null liegt. Die Fenster überlappen, einzelne Cutover sind nicht unabhängig",
            "Tagesfehler: Betrag der Differenz zwischen prognostiziertem und gemessenem Tagesmittel (Tagesenergie), wie in K1, nur Tage mit lauter bewerteten Stunden. Gegenläufige Stundenfehler gleichen sich dabei aus",
        ],
        images=["k4_error_curve.png"],
        decimals=STANDARD_CONFIG.decimals,
    )

    return output_directory


# Teil 2: peak/low nur für Prophet ausblenden


def build_masking_key_figures(overall: pd.DataFrame, metric: str) -> pd.DataFrame:
    metric_label, unit = METRIC_LABELS[metric]

    return key_figures_table(
        [
            (
                f"Ausblenden, Szenario {KIND_LABELS[row['kind']]}: {metric_label}-Differenz [{unit}]",
                row["mean"],
                f"bei {format_number(row['replay'], STANDARD_CONFIG.decimals)} {unit} ohne Ausblenden, "
                f"{row['masked_days']} von {row['days']} Tagen ausgeblendet, bei {row['improved']} Cutover besser",
            )
            for row in overall.to_dict("records")
        ]
    )


def report_masking(run_directory: Path, k4_config: K4Config) -> Path:
    run_config = read_raw_json(run_directory, "run_config")

    results = pd.read_csv(
        run_directory / RAW_SUBDIR / f"{MASKING_RESULTS_FILE}.csv",
        dtype={"cutover_date": str},
    )
    decisions = pd.read_csv(
        run_directory / RAW_SUBDIR / f"{MASKING_DECISIONS_FILE}.csv",
        dtype={"cutover_date": str},
    )

    paired = pair_masking(
        results,
        decisions,
        k4_config.masked_classifications,
        k4_config.error_metrics,
    )

    tables: dict[str, tuple[str, pd.DataFrame]] = {}
    for metric in k4_config.error_metrics:
        metric_label, unit = METRIC_LABELS[metric]
        suffix = METRIC_FILE_SUFFIX[metric]
        summary = summarize_masking_by_cutover(
            paired, k4_config.masking_early_days, metric
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
        title=f"K4 Teil 2, {'/'.join(k4_config.masked_classifications)} für Prophet ausblenden, Lauf {run_directory.name}",
        setup={
            "Cutover": format_cutovers(
                run_config["standard_config"]["cutover_dates"],
                run_config["k4_config"]["cutovers"],
            ),
            "Entscheidungen": "SYS2, danach zweimal nachgespielt: nur Resets (replay) und zusätzlich ausgeblendet (mask)",
            "Commit": format_commit(run_config["code_version"]),
        },
        tables=tables,
        notes=[
            f"replay trifft SYS2 an {format_number(summarize_replay_match(paired), STANDARD_CONFIG.decimals)} % der Tage",
            "Tagesfehler wie in Teil 1: Tage mit unvollständig bewerteten Stunden zählen dort nicht mit",
        ],
        images=[],
        decimals=STANDARD_CONFIG.decimals,
    )

    return output_directory


def main() -> None:
    part = sys.argv[1] if len(sys.argv) > 1 else "strategies"
    prefix = RUN_PREFIX if part == "strategies" else MASKING_RUN_PREFIX
    run_directory = run_directory_from_argv(PROJECT_CONFIG.k4_output_dir, prefix, 2)
    # Kennzahlen und Ausblend-Einstellungen aus der aktuellen Config, ältere Läufe haben sie nicht in run_config
    k4_config = K4Config()

    if part == "strategies":
        output_directory = report_strategies(run_directory, k4_config)
    else:
        output_directory = report_masking(run_directory, k4_config)

    print(f"Result written to {output_directory / 'ergebnis.md'}")


if __name__ == "__main__":
    main()
