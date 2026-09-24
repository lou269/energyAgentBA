from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from docs.plots.plot_style import RESET_MODE_COLORS, grouped_bars, save_figure


def build_k3_plot(
    gate_open: pd.DataFrame,
    extra_notifications: pd.DataFrame,
    output_directory: Path,
    *,
    mode_labels: dict[str, str],
    target_rate_pct: float,
) -> None:
    """beide Tabellen: Zeilen = Referenzfenster, Spalten = Modus"""
    figure, (rate_axis, notification_axis) = plt.subplots(1, 2, figsize=(11, 4))

    grouped_bars(rate_axis, gate_open, RESET_MODE_COLORS, mode_labels)
    rate_axis.axhline(
        target_rate_pct,
        color="#333333",
        linewidth=1,
        linestyle="--",
        label=f"Ziel {target_rate_pct:.0f} %",
    )
    rate_axis.set_title("Gate offen ohne Ereignis (Kontrolllauf)", loc="left")
    rate_axis.set_ylabel("Anteil Tage (%)")
    rate_axis.legend(fontsize=8)

    grouped_bars(notification_axis, extra_notifications, RESET_MODE_COLORS, mode_labels)
    notification_axis.set_title("Zusätzliche Meldungen durch die Stufe", loc="left")
    notification_axis.set_ylabel("Meldungen, alle Cutover zusammen")

    save_figure(figure, output_directory, "k3_closed_loop")
