from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from docs.plots.plot_style import RESET_MODE_COLORS, grouped_bars, save_figure
from experiments.k3_detection.k3_config import MODE_LABELS, REFERENCE_WINDOW_LABELS


def _by_mode(table: pd.DataFrame, value: str) -> pd.DataFrame:
    # Zeilen = Referenzfenster, Spalten = Modus, jeweils in fester Reihenfolge
    wide = table.pivot(index="variant", columns="mode", values=value)
    variants = [variant for variant in REFERENCE_WINDOW_LABELS if variant in wide.index]

    return wide.reindex(variants)[list(MODE_LABELS)].rename(
        index=REFERENCE_WINDOW_LABELS
    )


def build_k3_plot(
    gate_open: pd.DataFrame,
    notifications: pd.DataFrame,
    output_directory: Path,
    *,
    target_rate_pct: float,
) -> None:
    figure, (rate_axis, notification_axis) = plt.subplots(1, 2, figsize=(11, 4))

    grouped_bars(
        rate_axis, _by_mode(gate_open, "gate_open_pct"), RESET_MODE_COLORS, MODE_LABELS
    )
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

    grouped_bars(
        notification_axis,
        _by_mode(notifications, "extra_notifications"),
        RESET_MODE_COLORS,
        MODE_LABELS,
    )
    notification_axis.set_title("Zusätzliche Meldungen durch die Stufe", loc="left")
    notification_axis.set_ylabel("Meldungen, alle Cutover zusammen")

    save_figure(figure, output_directory, "k3_closed_loop")
