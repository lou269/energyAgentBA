# python docs/plots/plot_forecast_ergebnis.py
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Patch

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
ACTIVE_MODEL_COLOR = "#E45756"


def add_bar_labels(axis, fmt: str = "{:.0f}") -> None:
    for container in axis.containers:
        for bar in container:
            height = bar.get_height()

            axis.annotate(
                fmt.format(height),
                xy=(bar.get_x() + bar.get_width() / 2, height),
                xytext=(0, 3),
                textcoords="offset points",
                ha="center",
                va="bottom",
                fontsize=7,
            )


def build_forecast_plot(
    run_directory: Path,
    output_directory: Path,
    *,
    split: str,
    active_model_id: str,
    baseline_model_ids: tuple[str, ...],
    reference_baseline: str,
) -> None:
    model_order = [*baseline_model_ids, active_model_id]
    model_colors = {**BASELINE_COLORS, active_model_id: ACTIVE_MODEL_COLOR}
    model_labels = {**BASELINE_LABELS, active_model_id: f"{active_model_id}: Adaptives Modell"}

    horizon_metrics = pd.read_csv(run_directory / f"horizon_metrics_{split}.csv")
    overall_metrics = pd.read_csv(run_directory / f"overall_metrics_{split}.csv")
    mae_skill = pd.read_csv(run_directory / f"mae_skill_{split}.csv")
    origin_metrics = pd.read_csv(run_directory / f"origin_metrics_{split}.csv")
    forecasts = pd.read_csv(run_directory / f"forecasts_{split}.csv")

    forecasts["target_timestamp"] = pd.to_datetime(forecasts["target_timestamp"], utc=True)
    forecasts["forecast_origin"] = pd.to_datetime(forecasts["forecast_origin"], utc=True)

    # Repräsentativer Origin: Median-MAE des adaptiven Modells
    active_origin_mae = origin_metrics.loc[
        origin_metrics["model_id"].eq(active_model_id)
    ].sort_values("mae_w").reset_index(drop=True)

    median_row = active_origin_mae.iloc[len(active_origin_mae) // 2]
    example_origin = pd.Timestamp(median_row["forecast_origin"], tz="UTC")

    figure = plt.figure(figsize=(13, 12))
    grid = figure.add_gridspec(
        3,
        2,
        height_ratios=[1.1, 1.0, 1.1],
        hspace=0.55,
        wspace=0.3,
    )

    horizon_axis = figure.add_subplot(grid[0, :])
    overall_axis = figure.add_subplot(grid[1, 0])
    skill_axis = figure.add_subplot(grid[1, 1])
    example_axis = figure.add_subplot(grid[2, :])

    # A: MAE über den Prognosehorizont
    for model_id in model_order:
        model_horizon = horizon_metrics.loc[horizon_metrics["model_id"].eq(model_id)].sort_values("horizon_step")

        horizon_axis.plot(
            model_horizon["horizon_step"],
            model_horizon["mae_w"],
            marker="o",
            markersize=3,
            linewidth=2 if model_id == active_model_id else 1.3,
            color=model_colors[model_id],
            label=model_labels[model_id],
        )

    horizon_axis.set_title(f"A: MAE über den Prognosehorizont ({split.capitalize()})", loc="left")
    horizon_axis.set_xlabel("Prognosehorizont (Stunden)")
    horizon_axis.set_ylabel("MAE (W)")
    horizon_axis.grid(axis="y", alpha=0.25)
    horizon_axis.legend(fontsize=8, loc="upper left")

    # B: Gesamtfehler je Modell
    overall_metrics = overall_metrics.set_index("model_id").loc[model_order]
    x_positions = np.arange(len(model_order))
    bar_width = 0.35

    overall_axis.bar(
        x_positions - bar_width / 2,
        overall_metrics["mae_w"],
        width=bar_width,
        color=[model_colors[m] for m in model_order],
        label="MAE",
    )
    overall_axis.bar(
        x_positions + bar_width / 2,
        overall_metrics["rmse_w"],
        width=bar_width,
        color=[model_colors[m] for m in model_order],
        alpha=0.55,
        label="RMSE",
        hatch="//",
    )

    overall_axis.set_xticks(x_positions)
    overall_axis.set_xticklabels(model_order)
    overall_axis.set_title(f"B: Gesamtfehler je Modell ({split.capitalize()})", loc="left")
    overall_axis.set_ylabel("Fehler (W)")
    overall_axis.grid(axis="y", alpha=0.25)
    add_bar_labels(overall_axis)
    overall_axis.legend(
        handles=[
            Patch(facecolor="#606060", label="MAE"),
            Patch(facecolor="#606060", alpha=0.55, hatch="//", label="RMSE"),
        ],
        fontsize=8,
    )

    # C: MAE-Skill des adaptiven Modells gegenüber den Baselines
    skill_plot = mae_skill.loc[mae_skill["model_id"].eq(active_model_id)].copy()
    skill_plot["reference_label"] = skill_plot["reference_model_id"].map(model_labels)
    skill_plot["mae_skill_pct"] = skill_plot["mae_skill"] * 100

    bars = skill_axis.bar(
        skill_plot["reference_model_id"],
        skill_plot["mae_skill_pct"],
        color=[model_colors[m] for m in skill_plot["reference_model_id"]]
    )

    skill_axis.axhline(0, color="#333333", linewidth=1)
    skill_axis.set_title(f"C: MAE-Skill von {active_model_id} gegenüber Baselines", loc="left")
    skill_axis.set_ylabel("Verbesserung ggü. Baseline (%)")
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

    # D: Beispielhafte 24h-Prognose für einen Origin (Median-MAE des adaptiven Modells)
    example_active = forecasts.loc[
        forecasts["model_id"].eq(active_model_id)
        & forecasts["forecast_origin"].eq(example_origin)
    ].sort_values("target_timestamp")
    example_reference = forecasts.loc[
        forecasts["model_id"].eq(reference_baseline)
        & forecasts["forecast_origin"].eq(example_origin)
    ].sort_values("target_timestamp")

    example_axis.fill_between(
        example_active["target_timestamp"],
        example_active["y_lower"],
        example_active["y_upper"],
        color=model_colors[active_model_id],
        alpha=0.15,
        label=f"{active_model_id}: 80%-Prognoseintervall",
    )
    example_axis.plot(
        example_active["target_timestamp"],
        example_active["y_true"],
        color="#222222",
        marker="o",
        markersize=3,
        linewidth=1.5,
        label="Ist-Wert",
    )
    example_axis.plot(
        example_active["target_timestamp"],
        example_active["y_pred"],
        color=model_colors[active_model_id],
        marker="o",
        markersize=3,
        linewidth=2,
        label=model_labels[active_model_id],
    )
    example_axis.plot(
        example_reference["target_timestamp"],
        example_reference["y_pred"],
        color=model_colors[reference_baseline],
        linestyle="--",
        linewidth=1.3,
        label=model_labels[reference_baseline],
    )

    example_axis.set_title(
        "D: Beispielhafte 24h-Prognose "
        f"(Origin {example_origin:%d.%m.%Y %H:%M}, "
        f"Median-MAE {active_model_id} = {median_row['mae_w']:.0f} W)",
        loc="left",
    )
    example_axis.set_xlabel("Zeit")
    example_axis.set_ylabel("Leistung (W)")
    example_axis.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    example_axis.grid(axis="y", alpha=0.25)
    example_axis.legend(fontsize=8, loc="upper right")

    figure.suptitle(
        f"Forecast-Ergebnisse: Baselines vs. adaptives Modell ({split.capitalize()})",
        fontsize=15,
        fontweight="bold",
    )

    output_directory.mkdir(parents=True, exist_ok=True)

    figure.savefig(str(output_directory / f"forecast_ergebnis_{split}.svg"), bbox_inches="tight")
    figure.savefig(str(output_directory / f"forecast_ergebnis_{split}.png"), dpi=300, bbox_inches="tight")

    plt.close(figure)


def main() -> None:
    from src.config.config_forecasting import ForecastingConfig
    from src.pipeline.io import latest_sequential_number

    split = "validation"
    forecasting_config = ForecastingConfig()

    run_number = latest_sequential_number(FORECASTING_DIR, prefix="fc_val")
    if run_number is None:
        raise FileNotFoundError(f"No forecast run found in {FORECASTING_DIR}.")

    run_directory = FORECASTING_DIR / f"fc_val_{run_number:03d}"
    primary_naive_reference = pd.read_csv(run_directory / "primary_naive_reference_validation.csv")["model_id"].iloc[0]

    build_forecast_plot(
        run_directory,
        FIGURE_DIR,
        split=split,
        active_model_id=forecasting_config.selected_prophet_variant.model_id,
        baseline_model_ids=forecasting_config.baseline_model_ids,
        reference_baseline=primary_naive_reference,
    )


if __name__ == "__main__":
    main()
