from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from docs.plots.plot_style import SYSTEM_COLORS, save_figure, style_axis

DAYS_PER_WEEK = 7


def build_e3_week_plot(
    curve: pd.DataFrame,
    notifications: pd.DataFrame,
    output_directory: Path,
    *,
    reference: str,
    llm: str,
) -> None:
    figure, (delta_axis, notification_axis) = plt.subplots(
        2, 1, figsize=(6.4, 5.6), sharex=True
    )

    delta_axis.axhline(0, color="black", linewidth=0.8)
    delta_axis.plot(
        curve["day_since_reset"] / DAYS_PER_WEEK,
        curve["delta"],
        color=SYSTEM_COLORS[llm],
        linewidth=2,
    )
    delta_axis.set_ylabel(f"(a) Differenz Tagesfehler [W]\n{llm} − {reference}")

    width = 0.38
    for offset, config in ((-width / 2, reference), (width / 2, llm)):
        shares = notifications.loc[notifications["config"].eq(config)]
        notification_axis.bar(
            shares["week"] - 0.5 + offset,
            shares["notification_share_pct"],
            width=width,
            color=SYSTEM_COLORS[config],
            label=config,
        )
    notification_axis.set_ylabel("(b) Tage mit Meldung [%]")
    notification_axis.set_xlabel("Wochen ab dem Zurücksetzen")
    notification_axis.set_xticks(np.arange(0, notifications["week"].max() + 1))
    notification_axis.legend(fontsize=8, frameon=False)

    for axis in (delta_axis, notification_axis):
        style_axis(axis)

    save_figure(figure, output_directory, "e3_weeks")
