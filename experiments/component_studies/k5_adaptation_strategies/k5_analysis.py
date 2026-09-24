# conda activate forecasting-env
# python -m experiments.component_studies.k5_adaptation_strategies.k5_analysis [run_directory]

import sys

import pandas as pd

from docs.plots.plot_k5_adaptation_strategies import build_k5_plot
from experiments.component_studies.k5_adaptation_strategies.k5_config import (
    K5_KEY_FIGURE_KIND,
    K5_KEY_FIGURE_LATE_WEEK,
    K5_KIND_LABELS,
    K5_STRATEGY_LABELS,
)
from experiments.component_studies.k5_adaptation_strategies.k5_evaluation import (
    error_curve,
    excess_without_reaction,
    net_of_control,
    pair_with_none,
    summarize_after_trigger,
)
from experiments.shared_analysis import SPREAD_LABELS, spread_over_repeats
from src.common.result_report import (
    format_commit,
    format_number,
    key_figures_table,
    write_result_report,
)
from src.config.project_config import ProjectConfig
from src.pipeline.io import (
    RAW_SUBDIR,
    read_raw_json,
    resolve_run_directory,
    user_output_directory,
)

KEYS = ["kind", "trigger_day", "strategy"]
HEADERS = {
    "kind": "Ereignis",
    "trigger_day": "Trigger-Tag",
    "strategy": "Aktion",
    "mean_pct": "Mittel [%]",
    **SPREAD_LABELS,
}


def _labeled(table: pd.DataFrame) -> pd.DataFrame:
    labeled = table.assign(
        kind=table["kind"].map(K5_KIND_LABELS),
        strategy=table["strategy"].map(K5_STRATEGY_LABELS),
        trigger_day=table["trigger_day"].astype(int),
    )

    return labeled.rename(columns=HEADERS)


def excess_by_week(excess: pd.DataFrame) -> pd.DataFrame:
    return excess.pivot(index="kind", columns="week_since_cutover", values="excess_w")


def _labeled_excess(table: pd.DataFrame) -> pd.DataFrame:
    labeled = table.rename(index=K5_KIND_LABELS, columns=lambda week: f"Woche {week}")

    return labeled.rename_axis(index="Ereignis", columns=None).reset_index()


def build_net_table(net: pd.DataFrame) -> pd.DataFrame:
    table = spread_over_repeats(net, KEYS, "net_delta_w", count_same_direction=True)
    # relativ zum MAE ohne Aktion, damit sich die Größenordnung neben ~130 W einordnen lässt
    mae_none = net.groupby(KEYS, as_index=False)["mae_none_w"].mean()
    table = table.merge(mae_none, on=KEYS)
    table["mean_pct"] = table["mean"] / table["mae_none_w"] * 100

    return table.drop(columns="mae_none_w")


def build_control_table(summary: pd.DataFrame) -> pd.DataFrame:
    control = summary.loc[summary["kind"].eq("control")]

    return spread_over_repeats(control, KEYS, "mae_delta_w", count_same_direction=True)


def build_setup(run_config: dict, decimals: int) -> dict[str, str]:
    k3_config, k5_config = run_config["k3_config"], run_config["k5_config"]

    return {
        "Cutover": ", ".join(k3_config["cutover_dates"]),
        "Ereignisse": (
            f"Dauerlast +{format_number(k3_config['step_injection_w'], 0)} W, proportional jede Stunde × "
            f"{format_number(k5_config['scale_factor'], decimals)}, dazu keine Änderung als Kontrolle"
        ),
        "Trigger": (
            f"Aktion fest an Tag {' und '.join(str(day) for day in k5_config['trigger_days'])} nach dem Cutover (Orakel), "
            "t_c wie die Adaptionsregel"
        ),
        "Auswertung": f"{k5_config['evaluation_days']} Prognosetage ab Trigger, gepaart gegen keine Aktion am selben Tag",
        "Commit": format_commit(run_config["code_version"]),
    }


def build_key_figures(
    net: pd.DataFrame, excess: pd.DataFrame, decimals: int
) -> pd.DataFrame:
    kind_label = K5_KIND_LABELS[K5_KEY_FIGURE_KIND]
    event = net.loc[net["kind"].eq(K5_KEY_FIGURE_KIND)]
    earliest, latest = int(event["trigger_day"].min()), int(event["trigger_day"].max())

    rows = [
        (
            f"{K5_STRATEGY_LABELS[row['strategy']]}, Trigger Tag {earliest}: Netto-Effekt bei {kind_label} [W]",
            row["mean"],
            f"{format_number(row['mean_pct'], decimals)} % MAE, gleiche Richtung {row['same_direction']} Cutover",
        )
        for row in event.loc[event["trigger_day"].eq(earliest)].to_dict("records")
    ]
    rows.append(
        (
            f"Trigger Tag {latest}: bester Netto-Effekt bei {kind_label} [W]",
            event.loc[event["trigger_day"].eq(latest), "mean"].min(),
            "späte Erkennung",
        )
    )
    rows.append(
        (
            f"ohne Aktion: Mehrfehler bei {kind_label} in Woche 0 [W]",
            excess.at[K5_KEY_FIGURE_KIND, 0],
            f"Woche {K5_KEY_FIGURE_LATE_WEEK}: {format_number(excess.at[K5_KEY_FIGURE_KIND, K5_KEY_FIGURE_LATE_WEEK], decimals)} W",
        )
    )
    return key_figures_table(rows)


def main() -> None:
    project_config = ProjectConfig()
    decimals = project_config.result_decimals

    run_directory = resolve_run_directory(
        project_config.k5_output_dir, "k5", sys.argv[1] if len(sys.argv) > 1 else None
    )
    run_config = read_raw_json(run_directory, "run_config")

    results = pd.read_csv(
        run_directory / RAW_SUBDIR / "k5_results.csv", dtype={"cutover_date": str}
    )
    paired = pair_with_none(results, run_config["k5_config"]["evaluation_days"])
    summary = summarize_after_trigger(paired)

    net = build_net_table(net_of_control(summary))
    excess = excess_by_week(excess_without_reaction(results))

    tables = {
        "key_figures": ("Kennzahlen", build_key_figures(net, excess, decimals)),
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
            _labeled(build_control_table(summary)).drop(columns="Ereignis"),
        ),
    }

    output_directory = user_output_directory(run_directory)
    build_k5_plot(
        error_curve(paired),
        output_directory,
        kind=K5_KEY_FIGURE_KIND,
        kind_label=K5_KIND_LABELS[K5_KEY_FIGURE_KIND],
        strategy_labels=K5_STRATEGY_LABELS,
    )

    write_result_report(
        output_directory,
        title=f"K5 Adaptionsstrategien, Lauf {run_directory.name}",
        setup=build_setup(run_config, decimals),
        tables=tables,
        notes=[
            "Netto: Differenz zu keiner Aktion bei echter Änderung minus Differenz derselben Aktion ohne Änderung",
            "gleiche Richtung: Cutover, deren Wert dasselbe Vorzeichen hat wie das Mittel. Die Fenster überlappen, einzelne Cutover sind nicht unabhängig",
        ],
        images=["k5_error_curve.png"],
        decimals=decimals,
    )

    print(f"Result written to {output_directory / 'ergebnis.md'}")


if __name__ == "__main__":
    main()
