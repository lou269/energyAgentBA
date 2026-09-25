# conda activate forecasting-env
# python -m experiments.e4_cold_start.e4_report [run_directory]

import pandas as pd

from docs.plots.plot_e4_cold_start import build_e4_plot
from experiments.common.report import (
    format_commit,
    format_number,
    key_figures_table,
    write_result_report,
)
from experiments.common.standard_config import DECIMALS, PROJECT_CONFIG
from experiments.e4_cold_start.e4_config import ORIGIN_METRICS_FILE, RUN_PREFIX
from experiments.e4_cold_start.e4_evaluation import (
    ColdStartSummary,
    summarize_cold_start,
)
from src.pipeline.io import (
    RAW_SUBDIR,
    read_raw_json,
    run_directory_from_argv,
    user_output_directory,
)

KEY_HEADERS = {
    "coldstart_days": "Kaltstart [Tage]",
    "window": "Tage seit Start",
    "mean": "Mittel",
    "same_direction": "gleiche Richtung",
}


def build_overall_table(overall: pd.DataFrame, reference_model_id: str) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Kaltstart [Tage]": overall["coldstart_days"],
            "MAE [W]": overall["mae_w"],
            f"MAE {reference_model_id} [W]": overall["mae_w_reference"],
            f"Skill ggü. {reference_model_id} [%]": overall["mae_skill_pct"],
            "MAPE [%]": overall["mape_pct"],
            "Abstand zum längsten Kaltstart [W]": overall["mae_gap_to_steady_state_w"],
        }
    )


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
    summary: ColdStartSummary, reference_model_id: str
) -> pd.DataFrame:
    shortest = summary.shortest

    return key_figures_table(
        [
            (
                f"Kaltstart {shortest} Tage: MAE über die Auswertung [W]",
                summary.mae_shortest_w,
                f"längster Kaltstart {format_number(summary.mae_longest_w, DECIMALS)} W, "
                f"{reference_model_id} {format_number(summary.reference_mae_shortest_w, DECIMALS)} W",
            ),
            (
                f"Kaltstart {shortest} Tage: Abstand zum längsten Kaltstart in Tag {summary.first_window} [W]",
                summary.first_window_gap_w,
                f"gleiche Richtung {summary.first_window_same_direction} Starttermine",
            ),
            (
                f"Kaltstart {shortest} Tage: spätester Break-even gegen {reference_model_id} [Tag]",
                summary.latest_break_even_day,
                "über alle Starttermine",
            ),
        ]
    )


def main() -> None:
    run_directory = run_directory_from_argv(PROJECT_CONFIG.e4_output_dir, RUN_PREFIX)
    run_config = read_raw_json(run_directory, "run_config")
    e4_config = run_config["e4_config"]
    variant_id = run_config["prophet_variant"]["model_id"]
    reference_model_id = run_config["reference_baseline"]

    origin_metrics = pd.read_csv(
        run_directory / RAW_SUBDIR / f"{ORIGIN_METRICS_FILE}.csv",
        dtype={"start_date": str},
    )
    summary = summarize_cold_start(
        origin_metrics,
        variant_id=variant_id,
        reference_model_id=reference_model_id,
        smoothing_days=e4_config["smoothing_days"],
        evaluation_days=e4_config["evaluation_days"],
        window_edges_days=tuple(e4_config["window_edges_days"]),
    )

    tables = {
        "key_figures": (
            "Kennzahlen",
            build_key_figures(summary, reference_model_id),
        ),
        "result_overall": (
            f"{variant_id} über alle Auswertungstage, Mittel über Starttermine",
            build_overall_table(summary.overall, reference_model_id),
        ),
        "result_gap": (
            "Abstand zum längsten Kaltstart je Fenster und Starttermin [W], positiv = schlechter",
            summary.gap.rename(columns=KEY_HEADERS),
        ),
        "result_break_even": (
            f"Break-even: erster Tag, an dem die Lernkurve unter {reference_model_id} liegt",
            summary.break_even.rename(columns=KEY_HEADERS),
        ),
    }

    output_directory = user_output_directory(run_directory)
    build_e4_plot(
        summary.curve,
        output_directory,
        variant_id=variant_id,
        reference_model_id=reference_model_id,
        smoothing_days=e4_config["smoothing_days"],
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
        decimals=DECIMALS,
    )

    print(f"Result written to {output_directory / 'ergebnis.md'}")


if __name__ == "__main__":
    main()
