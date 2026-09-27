from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
import pandas as pd

from docs.plots.plot_style import STRATEGY_COLORS, save_figure

TRIGGER_LINESTYLES = ("-", "--", ":")


def build_k4_plot(
    curve: pd.DataFrame,
    output_directory: Path,
    *,
    kind: str,
    kind_label: str,
    strategy_labels: dict[str, str],
) -> None:
    trigger_days = sorted(curve["trigger_day"].unique())
    figure, axis = plt.subplots(figsize=(9, 4))

    for strategy, color in STRATEGY_COLORS.items():
        for trigger_day, linestyle in zip(trigger_days, TRIGGER_LINESTYLES):
            line = curve.loc[
                curve["kind"].eq(kind)
                & curve["strategy"].eq(strategy)
                & curve["trigger_day"].eq(trigger_day)
            ]
            axis.plot(
                line["week_since_trigger"],
                line["mae_delta_w"],
                color=color,
                linestyle=linestyle,
                marker="o",
                label=f"{strategy_labels[strategy]}, Trigger Tag {trigger_day:.0f}",
            )

    axis.axhline(0, color="#333333", linewidth=0.8)
    axis.set_title(
        f"MAE-Differenz zu keiner Aktion nach dem Trigger ({kind_label}, Mittel über Cutover)",
        loc="left",
    )
    axis.set_xlabel("Woche seit Trigger")
    axis.xaxis.set_major_locator(MaxNLocator(integer=True))
    axis.set_ylabel("MAE-Differenz (W), negativ = besser")
    axis.grid(axis="y", alpha=0.25)
    axis.legend(fontsize=8)

    save_figure(figure, output_directory, "k4_error_curve")
