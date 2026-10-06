from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from docs.plots.plot_style import SYSTEM_COLORS, save_figure
from experiments.common.evaluation import add_days_since_cutover
from src.config.config_forecasting import SYS_LABELS


def build_e1_plot(
    results: pd.DataFrame,
    output_directory: Path,
    *,
    reference_config: str,
    kind_labels: dict[str, str],
) -> None:
    days = add_days_since_cutover(results)
    cutover_dates = sorted(days["cutover_date"].unique())
    device_kinds = [kind for kind in kind_labels if kind != "control"]
    figure, axes = plt.subplots(
        len(cutover_dates),
        len(device_kinds),
        figsize=(9 * len(device_kinds), 3.2 * len(cutover_dates)),
        squeeze=False,
    )

    for row, cutover_date in enumerate(cutover_dates):
        for column, kind in enumerate(device_kinds):
            axis = axes[row, column]
            scenario = days.loc[days["cutover_date"].eq(cutover_date)]

            control = scenario.loc[
                scenario["kind"].eq("control")
                & scenario["config"].eq(reference_config)
            ]
            axis.plot(
                control["days_since_cutover"],
                control["day_error_w"],
                color="#999999",
                linewidth=1.2,
                linestyle="--",
                label=f"{SYS_LABELS[reference_config]}, Gerät durchgehend",
            )

            for config, color in SYSTEM_COLORS.items():
                runs = scenario.loc[
                    scenario["kind"].eq(kind) & scenario["config"].eq(config)
                ]
                if runs.empty:
                    continue

                reset = runs["adaption_action"].eq("advance_history_start")
                axis.plot(
                    runs["days_since_cutover"],
                    runs["day_error_w"],
                    color=color,
                    linewidth=1.5,
                    label=SYS_LABELS[config],
                )
                axis.scatter(
                    runs.loc[reset, "days_since_cutover"],
                    runs.loc[reset, "day_error_w"],
                    color=color,
                    marker="x",
                    s=60,
                    zorder=3,
                )

            # Tag 0 ist der erste Prognosetag mit Gerät, die Linie liegt davor
            axis.axvline(-0.5, color="#333333", linewidth=1)
            axis.set_title(f"{kind_labels[kind]}, Cutover {cutover_date}", loc="left")
            axis.set_ylabel("Tagesfehler (W)")
            axis.grid(axis="y", alpha=0.25)

    axes[0, 0].legend(fontsize=8)
    for axis in axes[-1, :]:
        axis.set_xlabel("Prognosetag seit Cutover (x: Reset)")
    save_figure(figure, output_directory, "e1_timeline")
