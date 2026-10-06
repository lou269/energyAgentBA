from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from docs.plots.plot_style import SYSTEM_COLORS, save_figure
from src.config.config_forecasting import SYS_LABELS


def build_e5_plot(
    results: pd.DataFrame,
    output_directory: Path,
    *,
    event_days: list[int],
) -> None:
    event_series = results.loc[results["series"].eq("events")]
    cutover_dates = sorted(event_series["cutover_date"].unique())
    figure, axes = plt.subplots(
        len(cutover_dates), 1, figsize=(9, 3.2 * len(cutover_dates)), squeeze=False
    )

    for axis, cutover_date in zip(axes[:, 0], cutover_dates):
        for config, color in SYSTEM_COLORS.items():
            days = event_series.loc[
                event_series["cutover_date"].eq(cutover_date)
                & event_series["config"].eq(config)
            ]
            if days.empty:
                continue

            reset = days["adaption_action"].eq("advance_history_start")
            axis.plot(
                days["days_since_cutover"],
                days["day_error_w"],
                color=color,
                linewidth=1.5,
                label=SYS_LABELS[config],
            )
            axis.scatter(
                days.loc[reset, "days_since_cutover"],
                days.loc[reset, "day_error_w"],
                color=color,
                marker="x",
                s=60,
                zorder=3,
            )

        # der Ereignistag ist schon der erste Prognosetag mit Ereignis, die Linie liegt davor
        for day in event_days:
            axis.axvline(day - 0.5, linewidth=1)
        axis.set_title(f"Cutover {cutover_date}", loc="left")
        axis.set_ylabel("Tagesfehler (W)")
        axis.grid(axis="y", alpha=0.25)

    axes[0, 0].legend(fontsize=8)
    axes[-1, 0].set_xlabel("Prognosetag seit Cutover (senkrecht: Ereignisse, x: Reset)")
    save_figure(figure, output_directory, "e5_timeline")
