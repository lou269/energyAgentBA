from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from docs.plots.plot_style import SYSTEM_COLORS, save_figure
from src.config.config_forecasting import SYS_LABELS


def build_e3_plot(
    results: pd.DataFrame,
    output_directory: Path,
    *,
    event_days: dict[str, list[int]],
    series_labels: dict[str, str],
) -> None:
    cutover_dates = sorted(results["cutover_date"].unique())
    panels = [
        (cutover_date, series)
        for cutover_date in cutover_dates
        for series in event_days
    ]
    figure, axes = plt.subplots(
        len(panels), 1, figsize=(9, 3.2 * len(panels)), squeeze=False
    )

    for axis, (cutover_date, series) in zip(axes[:, 0], panels):
        series_days = results.loc[
            results["series"].eq(series) & results["cutover_date"].eq(cutover_date)
        ]
        for config, color in SYSTEM_COLORS.items():
            days = series_days.loc[series_days["config"].eq(config)]
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
        for day in event_days[series]:
            axis.axvline(day - 0.5, linewidth=1)
        axis.set_title(f"Cutover {cutover_date}, {series_labels[series]}", loc="left")
        axis.set_ylabel("Tagesfehler (W)")
        axis.grid(axis="y", alpha=0.25)

    axes[0, 0].legend(fontsize=8)
    axes[-1, 0].set_xlabel("Prognosetag seit Cutover (senkrecht: Ereignisse, x: Reset)")
    save_figure(figure, output_directory, "e3_timeline")
