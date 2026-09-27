# conda activate forecasting-env
# python -m experiments.k4_adaptation.k4_report [strategies|masking] [run_directory]

import sys
from pathlib import Path

import pandas as pd

from docs.plots.plot_k4_adaptation_strategies import build_k4_plot
from experiments.common.report import (
    format_commit,
    format_number,
    key_figures_table,
    relabel,
    write_result_report,
)
from experiments.common.standard_config import DECIMALS, KIND_LABELS, PROJECT_CONFIG
from experiments.k4_adaptation.k4_config import (
    MASKING_DECISIONS_FILE,
    MASKING_PHASE_LABELS,
    MASKING_RESULTS_FILE,
    MASKING_RUN_PREFIX,
    RESULTS_FILE,
    RUN_PREFIX,
    STRATEGY_LABELS,
    K4Config,
)
from experiments.k4_adaptation.k4_evaluation import (
    StrategyKeyFigures,
    summarize_error_curve,
    summarize_excess_without_action,
    net_of_control,
    pair_masking,
    pair_with_none,
    summarize_after_trigger,
    summarize_false_alarm,
    summarize_masking,
    summarize_masking_by_cutover,
    summarize_masking_key_figures,
    summarize_net_effect,
    summarize_strategy_key_figures,
)
from src.pipeline.io import (
    RAW_SUBDIR,
    read_raw_json,
    run_directory_from_argv,
    user_output_directory,
)

HEADERS = {
    "kind": "Ereignis",
    "trigger_day": "Trigger-Tag",
    "strategy": "Aktion",
    "mean_pct": "Mittel [%]",
    "mean": "Mittel",
    "same_direction": "gleiche Richtung",
}
MASKING_HEADERS = {
    "kind": "Ereignis",
    "phase": "Zeitraum",
    "days": "Tage",
    "masked_days": "ausgeblendet",
    "mean": "Mittel",
    "same_direction": "gleiche Richtung",
}


def _labeled(table: pd.DataFrame) -> pd.DataFrame:
    return relabel(
        table.assign(trigger_day=table["trigger_day"].astype(int)),
        HEADERS,
        {"kind": KIND_LABELS, "strategy": STRATEGY_LABELS},
    )


def _labeled_excess(table: pd.DataFrame) -> pd.DataFrame:
    labeled = table.rename(index=KIND_LABELS, columns=lambda week: f"Woche {week}")

    return labeled.rename_axis(index="Ereignis", columns=None).reset_index()


def build_setup(run_config: dict) -> dict[str, str]:
    standard_config, k4_config = run_config["standard_config"], run_config["k4_config"]

    return {
        "Cutover": ", ".join(standard_config["cutover_dates"]),
        "Ereignisse": (
            f"Dauerlast +{format_number(standard_config['step_injection_w'], 0)} W, proportional jede Stunde × "
            f"{format_number(standard_config['scale_factor'], DECIMALS)}, dazu keine Änderung als Kontrolle"
        ),
        "Trigger": (
            f"Aktion fest an Tag {' und '.join(str(day) for day in k4_config['trigger_days'])} nach dem Cutover (Orakel), "
            "t_c wie die Adaptionsregel"
        ),
        "Auswertung": f"{k4_config['evaluation_days']} Prognosetage ab Trigger, gepaart gegen keine Aktion am selben Tag",
        "Commit": format_commit(run_config["code_version"]),
    }


def build_key_figures(key: StrategyKeyFigures, late_week: int) -> pd.DataFrame:
    kind_label = KIND_LABELS[key.kind]

    rows = [
        (
            f"{STRATEGY_LABELS[row['strategy']]}, Trigger Tag {key.earliest}: Netto-Effekt bei {kind_label} [W]",
            row["mean"],
            f"{format_number(row['mean_pct'], DECIMALS)} % MAE, gleiche Richtung {row['same_direction']} Cutover",
        )
        for row in key.earliest_rows.to_dict("records")
    ]
    rows.append(
        (
            f"Trigger Tag {key.latest}: bester Netto-Effekt bei {kind_label} [W]",
            key.latest_best_w,
            "späte Erkennung",
        )
    )
    rows.append(
        (
            f"ohne Aktion: Mehrfehler bei {kind_label} in Woche 0 [W]",
            key.excess_first_week_w,
            f"Woche {late_week}: {format_number(key.excess_late_week_w, DECIMALS)} W",
        )
    )
    return key_figures_table(rows)


def report_strategies(run_directory: Path, k4_config: K4Config) -> Path:
    run_config = read_raw_json(run_directory, "run_config")

    results = pd.read_csv(
        run_directory / RAW_SUBDIR / f"{RESULTS_FILE}.csv", dtype={"cutover_date": str}
    )
    paired = pair_with_none(results, run_config["k4_config"]["evaluation_days"])
    summary = summarize_after_trigger(paired)

    net = summarize_net_effect(net_of_control(summary))
    excess = summarize_excess_without_action(results)

    tables = {
        "key_figures": (
            "Kennzahlen",
            build_key_figures(
                summarize_strategy_key_figures(
                    net,
                    excess,
                    kind=k4_config.key_figure_kind,
                    late_week=k4_config.key_figure_late_week,
                ),
                k4_config.key_figure_late_week,
            ),
        ),
        "result_without_action": (
            "Ohne Aktion: Mehrfehler gegenüber keiner Änderung je Woche seit Cutover [W]",
            _labeled_excess(excess),
        ),
        "result_net": (
            "Netto-Effekt der Aktion über die Auswertungstage, je Cutover [W], negativ = besser",
            _labeled(net),
        ),
        "result_false_alarm": (
            "Kosten eines Fehlalarms: Aktion ohne echte Änderung, je Cutover [W]",
            _labeled(summarize_false_alarm(summary)).drop(columns="Ereignis"),
        ),
    }

    output_directory = user_output_directory(run_directory)
    build_k4_plot(
        summarize_error_curve(paired),
        output_directory,
        kind=k4_config.key_figure_kind,
        kind_label=KIND_LABELS[k4_config.key_figure_kind],
        strategy_labels=STRATEGY_LABELS,
    )

    write_result_report(
        output_directory,
        title=f"K4 Adaptionsstrategien, Lauf {run_directory.name}",
        setup=build_setup(run_config),
        tables=tables,
        notes=[
            "Netto: Differenz zu keiner Aktion bei echter Änderung minus Differenz derselben Aktion ohne Änderung",
            "gleiche Richtung: Cutover, deren Wert dasselbe Vorzeichen hat wie das Mittel. Die Fenster überlappen, einzelne Cutover sind nicht unabhängig",
        ],
        images=["k4_error_curve.png"],
        decimals=DECIMALS,
    )

    return output_directory


# Teil 2: peak/low nur für Prophet ausblenden


def build_masking_key_figures(overall: pd.DataFrame) -> pd.DataFrame:
    return key_figures_table(
        [
            (
                f"Ausblenden, Szenario {KIND_LABELS[row['kind']]}: MAE-Differenz [W]",
                row["mean"],
                f"bei {format_number(row['mae_replay_w'], DECIMALS)} W ohne Ausblenden, "
                f"{row['masked_days']} von {row['days']} Tagen ausgeblendet, gleiche Richtung {row['same_direction']}",
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

    paired = pair_masking(results, decisions, k4_config.masked_classifications)
    summary = summarize_masking_by_cutover(paired, k4_config.masking_early_days)
    table = summarize_masking(summary)
    key = summarize_masking_key_figures(summary, table, paired)

    output_directory = user_output_directory(run_directory)
    write_result_report(
        output_directory,
        title=f"K4 Teil 2, {'/'.join(k4_config.masked_classifications)} für Prophet ausblenden, Lauf {run_directory.name}",
        setup={
            "Cutover": ", ".join(run_config["standard_config"]["cutover_dates"]),
            "Entscheidungen": "SYS2, danach zweimal nachgespielt: nur Resets (replay) und zusätzlich ausgeblendet (mask)",
            "Commit": format_commit(run_config["code_version"]),
        },
        tables={
            "key_figures": ("Kennzahlen", build_masking_key_figures(key.overall)),
            "result_masking": (
                "MAE mask minus replay je Cutover [W], negativ = besser",
                relabel(
                    table,
                    MASKING_HEADERS,
                    {"kind": KIND_LABELS, "phase": MASKING_PHASE_LABELS},
                ),
            ),
        },
        notes=[
            f"replay trifft SYS2 an {format_number(key.replay_match_pct, DECIMALS)} % der Tage"
        ],
        images=[],
        decimals=DECIMALS,
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
