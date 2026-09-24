# python -m docs.plots.plot_k2_forecast_model
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from docs.plots.plot_style import BASELINE_COLORS, FORECAST_VARIANT_COLORS, save_figure
from experiments.component_studies.k2_forecast_model.k2_config import (
    SPLIT_DIRECTORY_SUFFIX,
    ForecastModelExperimentConfig,
)
from src.config.project_config import ProjectConfig
from src.pipeline.io import RAW_SUBDIR, latest_sequential_number

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FIGURE_DIR = PROJECT_ROOT / "docs" / "diagrams" / "generated"

BASELINE_LABELS = {
    "B1": "B1: Naiv (letzter Wert)",
    "B2": "B2: Naiv (täglich)",
    "B3": "B3: Naiv (wöchentlich)",
}
VARIANT_LABELS = {
    "C1": "C1: Statisch\n(kein Retraining)",
    "C2": "C2: Expanding\n+ Retraining",
    "C3_7": "C3: Rolling 7-Tage\n+ Retraining",
    "C3_30": "C3: Rolling 30-Tage\n+ Retraining",
    "C3_60": "C3: Rolling 60-Tage\n+ Retraining",
}


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
    run_directory: Path,
    output_directory: Path,
    *,
    split: str,
    comparison_mode: str,
    baseline_model_ids: tuple[str, ...],
    variant_model_ids: tuple[str, ...],
    reference_baseline: str,
) -> None:
    model_colors = {**BASELINE_COLORS, **FORECAST_VARIANT_COLORS}
    model_labels = {**BASELINE_LABELS, **VARIANT_LABELS}
    all_model_order = [*baseline_model_ids, *variant_model_ids]

    origin_metrics = pd.read_csv(run_directory / "origin_metrics.csv")
    overall_metrics = pd.read_csv(run_directory / "overall_metrics.csv").set_index(
        "model_id"
    )
    mae_skill = pd.read_csv(run_directory / "mae_skill.csv")

    origin_metrics["forecast_day"] = pd.to_datetime(origin_metrics["forecast_day"])

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
            model_origins["forecast_day"],
            model_origins["mae_w"],
            marker="o",
            markersize=4,
            linewidth=2,
            color=model_colors[model_id],
            label=model_labels[model_id].replace("\n", " "),
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
    overall_axis.set_title(
        f"B: Gesamtfehler je Modell ({split.capitalize()})", loc="left"
    )
    overall_axis.set_ylabel("Fehler (W)")
    overall_axis.grid(axis="y", alpha=0.25)
    add_bar_labels(overall_axis)
    overall_axis.legend(fontsize=8)

    # C: MAE-Skill der Prophet-Varianten gegenüber der Referenz-Baseline
    skill_plot = (
        mae_skill.loc[
            mae_skill["model_id"].isin(variant_model_ids)
            & mae_skill["reference_model_id"].eq(reference_baseline)
        ]
        .set_index("model_id")
        .loc[list(variant_model_ids)]
    )

    skill_plot["mae_skill_pct"] = skill_plot["mae_skill"] * 100

    skill_axis.bar(
        variant_model_ids,
        skill_plot["mae_skill_pct"],
        color=[model_colors[m] for m in variant_model_ids],
    )

    skill_axis.axhline(0, color="#333333", linewidth=1)
    skill_axis.set_title(
        f"C: MAE-Skill ggü. Baseline {reference_baseline} ({split.capitalize()})",
        loc="left",
    )
    skill_axis.set_ylabel(f"Verbesserung ggü. {reference_baseline} (%)")
    # negativer Skill (schlechter als die Baseline) muss sichtbar bleiben
    skill_axis.set_ylim(
        min(0, skill_plot["mae_skill_pct"].min() * 1.3),
        skill_plot["mae_skill_pct"].max() * 1.3,
    )
    skill_axis.grid(axis="y", alpha=0.25)
    add_bar_labels(skill_axis, "{:.1f}%")

    # D: Retraining-Aufwand je Modell
    retrain_positions = np.arange(len(all_model_order))

    cost_axis.bar(
        retrain_positions,
        overall_metrics["retraining_count"],
        color=[model_colors[m] for m in all_model_order],
        label="Retraining-Vorgänge",
    )
    cost_axis.set_xticks(retrain_positions)
    cost_axis.set_xticklabels(all_model_order)
    cost_axis.set_ylabel("Retraining-Vorgänge (n)")
    cost_axis.set_title(
        f"D: Retraining-Aufwand je Modell ({split.capitalize()})", loc="left"
    )
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
    cost_axis.legend(
        lines_1 + lines_2, labels_1 + labels_2, fontsize=8, loc="upper left"
    )

    figure.suptitle(
        f"K2: Retraining-Varianten im Vergleich ({comparison_mode.capitalize()}, {split.capitalize()})",
        fontsize=15,
        fontweight="bold",
    )

    output_directory.mkdir(parents=True, exist_ok=True)

    save_figure(figure, output_directory, "forecast_model_comparison")


def main() -> None:
    experiment_config = ForecastModelExperimentConfig()
    split = experiment_config.split

    k2_output_dir = ProjectConfig().k2_output_dir

    run_number = latest_sequential_number(k2_output_dir, prefix="k2")
    if run_number is None:
        raise FileNotFoundError(f"No k2_forecast_model run found in {k2_output_dir}.")

    run_root = k2_output_dir / f"k2_{run_number:03d}" / RAW_SUBDIR

    for mode in experiment_config.comparison_modes:
        run_directory = run_root / f"{mode}_{SPLIT_DIRECTORY_SUFFIX[split]}"

        if not run_directory.exists():
            continue

        primary_naive_reference = pd.read_csv(
            run_directory / "primary_naive_reference.csv"
        )["model_id"].iloc[0]

        build_forecast_model_plot(
            run_directory,
            FIGURE_DIR / mode,
            split=split,
            comparison_mode=mode,
            baseline_model_ids=experiment_config.baseline_model_ids,
            variant_model_ids=tuple(
                variant.model_id for variant in experiment_config.prophet_variants
            ),
            reference_baseline=primary_naive_reference,
        )


if __name__ == "__main__":
    main()
