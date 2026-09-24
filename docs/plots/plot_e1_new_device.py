from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from docs.plots.plot_style import SYSTEM_COLORS, save_figure
from experiments.shared_analysis import forecast_days_since_event
from src.config.config_forecasting import SYS_LABELS


def build_e1_plot(
    comparison: pd.DataFrame,
    control_comparison: pd.DataFrame | None,
    output_directory: Path,
    *,
    cutover_time: pd.Timestamp,
    reference_config: str,
    local_timezone: str,
) -> None:
    figure, axis = plt.subplots(figsize=(9, 4))

    if control_comparison is not None:
        control = control_comparison.loc[
            control_comparison["config"].eq(reference_config)
        ]
        axis.plot(
            forecast_days_since_event(control, cutover_time, local_timezone),
            control["mae_w"],
            color="#999999",
            linewidth=1.2,
            linestyle="--",
            label=f"{reference_config} Kontrolle (Gerät durchgehend)",
        )

    for config, color in SYSTEM_COLORS.items():
        runs = comparison.loc[comparison["config"].eq(config)]
        if runs.empty:
            continue

        days = forecast_days_since_event(runs, cutover_time, local_timezone)
        adapted = runs["adaption_action"].ne("none").to_numpy()
        axis.plot(
            days, runs["mae_w"], color=color, linewidth=1.8, label=SYS_LABELS[config]
        )
        axis.scatter(
            days[adapted],
            runs.loc[adapted, "mae_w"],
            color=color,
            marker="x",
            s=60,
            zorder=3,
        )

    # Tag 0 ist der erste Prognosetag mit Gerät, die Linie liegt davor
    axis.axvline(-0.5, color="#333333", linewidth=1)
    axis.set_title(
        "Tagesfehler der Prognose um den Cutover (x: erste Prognose nach einer Adaption)",
        loc="left",
    )
    axis.set_xlabel("Prognosetag seit Cutover (Ortszeit)")
    axis.set_ylabel("MAE (W)")
    axis.grid(axis="y", alpha=0.25)
    axis.legend(fontsize=8)
    save_figure(figure, output_directory, "e1_timeline")
