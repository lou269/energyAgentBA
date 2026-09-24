# conda activate forecasting-env
# python -m experiments.proposal_experiments.e4_cold_start.e4_analysis [run_directory]

import sys

import pandas as pd

from docs.plots.plot_e4_cold_start import build_e4_plot
from experiments.proposal_experiments.e4_cold_start.e4_evaluation import (
    ALL_STARTS,
    assign_days_since_start,
    build_learning_curve,
    find_break_even_days,
    summarize_windows,
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

KEY_HEADERS = {
    "coldstart_days": "Kaltstart [Tage]",
    "window": "Tage seit Start",
    **SPREAD_LABELS,
}


def summarize_overall(overall: pd.DataFrame) -> pd.DataFrame:
    table = overall.loc[overall["start_date"].eq(ALL_STARTS)]

    return table[
        [
            "coldstart_days",
            "mae_w",
            "mae_w_reference",
            "mae_skill",
            "mape_pct",
            "mae_gap_to_steady_state_w",
        ]
    ].reset_index(drop=True)


def build_overall_table(overall: pd.DataFrame, reference_model_id: str) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Kaltstart [Tage]": overall["coldstart_days"],
            "MAE [W]": overall["mae_w"],
            f"MAE {reference_model_id} [W]": overall["mae_w_reference"],
            f"Skill ggü. {reference_model_id} [%]": overall["mae_skill"] * 100,
            "MAPE [%]": overall["mape_pct"],
            "Abstand zum längsten Kaltstart [W]": overall["mae_gap_to_steady_state_w"],
        }
    )


def summarize_gap(windows: pd.DataFrame) -> pd.DataFrame:
    # der längste Kaltstart ist die Referenz, sein Abstand zu sich selbst ist immer 0
    shorter = windows.loc[
        windows["start_date"].ne(ALL_STARTS)
        & windows["coldstart_days"].lt(windows["coldstart_days"].max())
    ]

    return spread_over_repeats(
        shorter,
        ["coldstart_days", "window"],
        "mae_gap_to_steady_state_w",
        repeat="start_date",
        count_same_direction=True,
    )


def summarize_break_even(break_even: pd.DataFrame) -> pd.DataFrame:
    table = spread_over_repeats(
        break_even, ["coldstart_days"], "break_even_day", repeat="start_date"
    )
    start_dates = sorted(break_even["start_date"].unique())
    table[start_dates] = table[start_dates].astype("Int64")

    return table


def build_setup(run_config: dict) -> dict[str, str]:
    e4_config = run_config["e4_config"]

    return {
        "Starttermine": ", ".join(e4_config["start_dates"]),
        "Kaltstart": f"{', '.join(str(days) for days in e4_config['coldstart_days'])} Tage Historie vor dem Start",
        "Auswertung": f"{e4_config['evaluation_days']} Tage ab Start, je Starttermin dieselben Kalendertage für alle Kaltstart-Längen",
        "Prognosemodell": run_config["prophet_variant"]["model_id"],
        "Naive Referenz": run_config["reference_baseline"],
        "Lernkurve": f"rückwärts gerichtetes Mittel über {e4_config['smoothing_days']} Tage",
        "Commit": format_commit(run_config["code_version"]),
    }


def build_key_figures(
    overall: pd.DataFrame,
    gap: pd.DataFrame,
    break_even: pd.DataFrame,
    *,
    reference_model_id: str,
    decimals: int,
) -> pd.DataFrame:
    by_coldstart = overall.set_index("coldstart_days")
    shortest, longest = by_coldstart.index.min(), by_coldstart.index.max()
    first_window = gap.loc[gap["coldstart_days"].eq(shortest)].iloc[0]
    latest_break_even = break_even.loc[
        break_even["coldstart_days"].eq(shortest), "break_even_day"
    ].max()

    return key_figures_table(
        [
            (
                f"Kaltstart {shortest} Tage: MAE über die Auswertung [W]",
                by_coldstart.at[shortest, "mae_w"],
                f"längster Kaltstart {format_number(by_coldstart.at[longest, 'mae_w'], decimals)} W, "
                f"{reference_model_id} {format_number(by_coldstart.at[shortest, 'mae_w_reference'], decimals)} W",
            ),
            (
                f"Kaltstart {shortest} Tage: Abstand zum längsten Kaltstart in Tag {first_window['window']} [W]",
                first_window["mean"],
                f"gleiche Richtung {first_window['same_direction']} Starttermine",
            ),
            (
                f"Kaltstart {shortest} Tage: spätester Break-even gegen {reference_model_id} [Tag]",
                latest_break_even,
                "über alle Starttermine",
            ),
        ]
    )


def main() -> None:
    project_config = ProjectConfig()
    decimals = project_config.result_decimals

    run_directory = resolve_run_directory(
        project_config.e4_output_dir, "e4", sys.argv[1] if len(sys.argv) > 1 else None
    )
    run_config = read_raw_json(run_directory, "run_config")
    e4_config = run_config["e4_config"]
    variant_id = run_config["prophet_variant"]["model_id"]
    reference_model_id = run_config["reference_baseline"]

    origin_metrics = pd.read_csv(
        run_directory / RAW_SUBDIR / "origin_metrics.csv", dtype={"start_date": str}
    )
    daily = assign_days_since_start(origin_metrics, project_config.timezone)
    curve = build_learning_curve(daily, smoothing_days=e4_config["smoothing_days"])
    break_even = find_break_even_days(
        curve, variant_id=variant_id, reference_model_id=reference_model_id
    )
    break_even = break_even.loc[break_even["start_date"].ne(ALL_STARTS)]

    windows = summarize_windows(
        daily,
        variant_id=variant_id,
        reference_model_id=reference_model_id,
        window_edges_days=tuple(e4_config["window_edges_days"]),
    )
    # ein einziges Fenster über alle Auswertungstage ergibt die Gesamtzahlen
    overall = summarize_overall(
        summarize_windows(
            daily,
            variant_id=variant_id,
            reference_model_id=reference_model_id,
            window_edges_days=(e4_config["evaluation_days"],),
        )
    )
    gap = summarize_gap(windows)

    tables = {
        "key_figures": (
            "Kennzahlen",
            build_key_figures(
                overall,
                gap,
                break_even,
                reference_model_id=reference_model_id,
                decimals=decimals,
            ),
        ),
        "result_overall": (
            f"{variant_id} über alle Auswertungstage, Mittel über Starttermine",
            build_overall_table(overall, reference_model_id),
        ),
        "result_gap": (
            "Abstand zum längsten Kaltstart je Fenster und Starttermin [W], positiv = schlechter",
            gap.rename(columns=KEY_HEADERS),
        ),
        "result_break_even": (
            f"Break-even: erster Tag, an dem die Lernkurve unter {reference_model_id} liegt",
            summarize_break_even(break_even).rename(columns=KEY_HEADERS),
        ),
    }

    output_directory = user_output_directory(run_directory)
    build_e4_plot(
        curve,
        output_directory,
        variant_id=variant_id,
        reference_model_id=reference_model_id,
    )

    write_result_report(
        output_directory,
        title=f"E4 Kaltstart, Lauf {run_directory.name}",
        setup=build_setup(run_config),
        tables=tables,
        notes=[
            "Break-even leer = im ganzen Auswertungszeitraum nie unter der Referenz"
        ],
        images=["e4_learning_curve.png"],
        decimals=decimals,
    )

    print(f"Result written to {output_directory / 'ergebnis.md'}")


if __name__ == "__main__":
    main()
