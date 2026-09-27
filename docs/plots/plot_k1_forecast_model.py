from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from docs.plots.plot_style import MODEL_COLORS, save_figure
from src.config.config_forecasting import MODEL_LABELS


def add_bar_labels(axis, fmt: str = "{:.0f}") -> None:
    for container in axis.containers:
        for bar in container:
            height = bar.get_height()

            axis.annotate(
                fmt.format(height),
                xy=(
                    bar.get_x() + bar.get_width() / 2,
                    height,
                ),
                xytext=(0, 3),
                textcoords="offset points",
                ha="center",
                va="bottom",
                fontsize=7,
            )


def build_forecast_model_plot(
    overall: pd.DataFrame,
    origin_metrics: pd.DataFrame,
    output_directory: Path,
    *,
    split: str,
    comparison_mode: str,
    baseline_model_ids: tuple[str, ...],
    variant_model_ids: tuple[str, ...],
    reference_baseline: str,
) -> None:
    all_model_order = list(baseline_model_ids) + list(variant_model_ids)
    model_colors = [MODEL_COLORS[model_id] for model_id in all_model_order]

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

    # A: MAE je Forecast-Origin über die Zeit
    for model_id in variant_model_ids:
        model_origins = origin_metrics.loc[
            origin_metrics["model_id"].eq(model_id)
        ].sort_values("forecast_day")

        timeline_axis.plot(
            pd.to_datetime(model_origins["forecast_day"]),
            model_origins["mae_w"],
            marker="o",
            markersize=4,
            linewidth=2,
            color=MODEL_COLORS[model_id],
            label=MODEL_LABELS[model_id],
        )

    timeline_axis.set_title(
        f"A: MAE je Forecast-Origin über die Zeit ({split.capitalize()})", loc="left"
    )
    timeline_axis.set_xlabel("Prognosetag (Ortszeit)")
    timeline_axis.set_ylabel("MAE (W)")
    timeline_axis.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m."))
    timeline_axis.tick_params(axis="x", rotation=25)
    timeline_axis.grid(axis="y", alpha=0.25)
    timeline_axis.legend(fontsize=8)

    # B: Gesamtfehler je Modell
    overall = overall.loc[all_model_order]
    x_positions = np.arange(len(all_model_order))
    bar_width = 0.35

    overall_axis.bar(
        x_positions - bar_width / 2,
        overall["mae_w"],
        width=bar_width,
        color=model_colors,
        label="MAE",
    )
    overall_axis.bar(
        x_positions + bar_width / 2,
        overall["rmse_w"],
        width=bar_width,
        color=model_colors,
        alpha=0.55,
        hatch="//",
        label="RMSE",
    )

    overall_axis.set_xticks(x_positions)
    overall_axis.set_xticklabels(all_model_order)
    overall_axis.set_title(
        f"B: Gesamtfehler je Modell ({split.capitalize()})", loc="left"
    )
    overall_axis.set_ylabel("Fehler (W)")
    overall_axis.grid(axis="y", alpha=0.25)
    add_bar_labels(overall_axis)
    overall_axis.legend(fontsize=8)

    # C: MAE-Skill der Prophet-Varianten gegenüber der Referenz-Baseline
    skill_pct = overall.loc[list(variant_model_ids), "skill_pct"]

    skill_axis.bar(
        variant_model_ids,
        skill_pct,
        color=[MODEL_COLORS[model_id] for model_id in variant_model_ids],
    )

    skill_axis.axhline(0, color="#333333", linewidth=1)
    skill_axis.set_title(
        f"C: MAE-Skill ggü. Baseline {reference_baseline} ({split.capitalize()})",
        loc="left",
    )
    skill_axis.set_ylabel(f"Verbesserung ggü. {reference_baseline} (%)")
    # negativer Skill (schlechter als die Baseline) muss sichtbar bleiben
    skill_axis.set_ylim(
        min(0, skill_pct.min() * 1.3),
        skill_pct.max() * 1.3,
    )
    skill_axis.grid(axis="y", alpha=0.25)
    add_bar_labels(skill_axis, "{:.1f}%")

    # D: Retraining-Aufwand je Modell
    cost_axis.bar(
        x_positions,
        overall["retraining_count"],
        color=model_colors,
        label="Retraining-Vorgänge",
    )
    cost_axis.set_xticks(x_positions)
    cost_axis.set_xticklabels(all_model_order)
    cost_axis.set_ylabel("Retraining-Vorgänge (n)")
    cost_axis.set_title(
        f"D: Retraining-Aufwand je Modell ({split.capitalize()})", loc="left"
    )
    cost_axis.grid(axis="y", alpha=0.25)
    add_bar_labels(cost_axis)

    runtime_axis = cost_axis.twinx()
    runtime_axis.plot(
        x_positions,
        overall["refit_seconds"],
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
    cost_axis.legend(
        lines_1 + lines_2, labels_1 + labels_2, fontsize=8, loc="upper left"
    )

    figure.suptitle(
        f"K1: Retraining-Varianten im Vergleich ({comparison_mode.capitalize()}, {split.capitalize()})",
        fontsize=15,
        fontweight="bold",
    )

    output_directory.mkdir(parents=True, exist_ok=True)

    save_figure(figure, output_directory, "forecast_model_comparison")
