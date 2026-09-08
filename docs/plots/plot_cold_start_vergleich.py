# python docs/plots/plot_cold_start_vergleich.py
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FORECASTING_DIR = PROJECT_ROOT / "output" / "forecasting"
FIGURE_DIR = PROJECT_ROOT / "docs" / "diagrams" / "generated"

BASELINE_COLORS = {
    "B1": "#B0B0B0",
    "B2": "#8C8C8C",
    "B3": "#4C78A8",
}
BASELINE_LABELS = {
    "B1": "B1: Naiv (letzter Wert)",
    "B2": "B2: Naiv (täglich)",
    "B3": "B3: Naiv (wöchentlich)",
}
VARIANT_COLORS = {
    "C1": "#F2CF5B",
    "C2": "#E45756",
    "C3": "#54A24B",
}
VARIANT_LABELS = {
    "C1": "C1: Statisch\n(kein Retraining)",
    "C2": "C2: Expanding\n+ Retraining",
    "C3": "C3: Rolling 7-Tage\n+ Retraining",
}


def add_bar_labels(axis, fmt: str = "{:.0f}") -> None:
    for container in axis.containers:
        for bar in container:
            height = bar.get_height()

            axis.annotate(
                fmt.format(height),
                xy=(bar.get_x() + bar.get_width() / 2, height,),
                xytext=(0, 3),
                textcoords="offset points",
                ha="center",
                va="bottom",
                fontsize=7,
            )


def build_cold_start_plot(
    run_directory: Path,
    output_directory: Path,
    *,
    split: str,
    baseline_model_ids: tuple[str, ...],
    variant_model_ids: tuple[str, ...],
    reference_baseline: str,
) -> None:
    model_colors = {**BASELINE_COLORS, **VARIANT_COLORS}
    model_labels = {**BASELINE_LABELS, **VARIANT_LABELS}
    all_model_order = [*baseline_model_ids, *variant_model_ids]

    origin_metrics = pd.read_csv(run_directory / "origin_metrics.csv")
    overall_metrics = pd.read_csv(run_directory / "overall_metrics.csv").set_index("model_id")
    mae_skill = pd.read_csv(run_directory / "mae_skill.csv")

    origin_metrics["forecast_origin"] = pd.to_datetime(origin_metrics["forecast_origin"], utc=True)

    figure = plt.figure(figsize=(13, 12))
    grid = figure.add_gridspec(
        3,
        2,
        height_ratios=[1.0, 1.0, 0.85],
        hspace=0.6,
        wspace=0.3,
    )

    timeline_axis = figure.add_subplot(grid[0, :])
    overall_axis = figure.add_subplot(grid[1, 0])
    skill_axis = figure.add_subplot(grid[1, 1])
    cost_axis = figure.add_subplot(grid[2, :])

    # A: MAE je Forecast-Origin über die Zeit (Cold-Start-Verlauf)
    for model_id in variant_model_ids:
        model_origins = origin_metrics.loc[origin_metrics["model_id"].eq(model_id)].sort_values("forecast_origin")

        timeline_axis.plot(
            model_origins["forecast_origin"],
            model_origins["mae_w"],
            marker="o",
            markersize=4,
            linewidth=2,
            color=model_colors[model_id],
            label=model_labels[model_id].replace("\n", " "),
        )

    timeline_axis.set_title(f"A: MAE je Forecast-Origin über die Zeit ({split.capitalize()})", loc="left")
    timeline_axis.set_xlabel("Forecast-Origin")
    timeline_axis.set_ylabel("MAE (W)")
    timeline_axis.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m."))
    timeline_axis.tick_params(axis="x", rotation=25)
    timeline_axis.grid(axis="y", alpha=0.25)
    timeline_axis.legend(fontsize=8)

    # B: Gesamtfehler je Modell
    overall_metrics = overall_metrics.loc[all_model_order]
    x_positions = np.arange(len(all_model_order))
    bar_width = 0.35

    overall_axis.bar(
        x_positions - bar_width / 2,
        overall_metrics["mae_w"],
        width=bar_width,
        color=[model_colors[m] for m in all_model_order],
        label="MAE",
    )
    overall_axis.bar(
        x_positions + bar_width / 2,
        overall_metrics["rmse_w"],
        width=bar_width,
        color=[model_colors[m] for m in all_model_order],
        alpha=0.55,
        hatch="//",
        label="RMSE",
    )

    overall_axis.set_xticks(x_positions)
    overall_axis.set_xticklabels(all_model_order)
    overall_axis.set_title(f"B: Gesamtfehler je Modell ({split.capitalize()})", loc="left")
    overall_axis.set_ylabel("Fehler (W)")
    overall_axis.grid(axis="y", alpha=0.25)
    add_bar_labels(overall_axis)
    overall_axis.legend(fontsize=8)

    # C: MAE-Skill der Prophet-Varianten gegenüber der Referenz-Baseline
    skill_plot = mae_skill.loc[
        mae_skill["model_id"].isin(variant_model_ids)
        & mae_skill["reference_model_id"].eq(reference_baseline)
    ].set_index("model_id").loc[list(variant_model_ids)]

    skill_plot["mae_skill_pct"] = skill_plot["mae_skill"] * 100

    bars = skill_axis.bar(
        variant_model_ids,
        skill_plot["mae_skill_pct"],
        color=[model_colors[m] for m in variant_model_ids],
    )

    skill_axis.axhline(0, color="#333333", linewidth=1)
    skill_axis.set_title(f"C: MAE-Skill ggü. Baseline {reference_baseline} ({split.capitalize()})", loc="left")
    skill_axis.set_ylabel(f"Verbesserung ggü. {reference_baseline} (%)")
    skill_axis.set_ylim(0, skill_plot["mae_skill_pct"].max() * 1.3)
    skill_axis.grid(axis="y", alpha=0.25)

    for bar, value in zip(bars, skill_plot["mae_skill_pct"]):
        skill_axis.annotate(
            f"{value:.1f}%",
            xy=(bar.get_x() + bar.get_width() / 2, value),
            xytext=(0, 3),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=8,
        )

    # D: Retraining-Aufwand je Modell
    retrain_positions = np.arange(len(all_model_order))

    cost_axis.set_xticks(retrain_positions)
    cost_axis.set_xticklabels(all_model_order)
    cost_axis.set_ylabel("Retraining-Vorgänge (n)")
    cost_axis.set_title(f"D: Retraining-Aufwand je Modell ({split.capitalize()})", loc="left")
    cost_axis.grid(axis="y", alpha=0.25)
    add_bar_labels(cost_axis)

    runtime_axis = cost_axis.twinx()
    runtime_axis.plot(
        retrain_positions,
        overall_metrics["total_refit_runtime_seconds"],
        color="#333333",
        marker="D",
        markersize=6,
        linewidth=1.5,
        linestyle="--",
        label="Refit-Laufzeit gesamt (s)",
    )
    runtime_axis.set_ylabel("Refit-Laufzeit gesamt (s)")

    lines_1, labels_1 = cost_axis.get_legend_handles_labels()
    lines_2, labels_2 = runtime_axis.get_legend_handles_labels()
    cost_axis.legend(lines_1 + lines_2, labels_1 + labels_2, fontsize=8, loc="upper left")

    figure.suptitle(
        f"K2: Cold Start und Retraining – Prophet-Varianten im Vergleich ({split.capitalize()})",
        fontsize=15,
        fontweight="bold",
    )

    output_directory.mkdir(parents=True, exist_ok=True)

    figure.savefig(str(output_directory / "cold_start_vergleich.svg"), bbox_inches="tight")
    figure.savefig(str(output_directory / "cold_start_vergleich.png"), dpi=300, bbox_inches="tight")

    plt.close(figure)


def main() -> None:
    from src.pipeline.io import latest_sequential_number

    split = "validation"
    study_dir = FORECASTING_DIR / "cold_start"

    run_number = latest_sequential_number(study_dir, prefix="cs_val")
    if run_number is None:
        raise FileNotFoundError(f"No cold-start run found in {study_dir}.")

    run_directory = study_dir / f"cs_val_{run_number:03d}"
    primary_naive_reference = pd.read_csv(run_directory / "primary_naive_reference.csv")["model_id"].iloc[0]

    build_cold_start_plot(
        run_directory,
        FIGURE_DIR,
        split=split,
        baseline_model_ids=("B1", "B2", "B3"),
        variant_model_ids=("C1", "C2", "C3"),
        reference_baseline=primary_naive_reference,
    )


if __name__ == "__main__":
    main()