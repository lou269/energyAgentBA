from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from docs.plots.plot_style import COLDSTART_COLORS, save_figure


def build_e4_forecast_plot(
    curve: pd.DataFrame,
    output_directory: Path,
    *,
    adaptive_model_id: str,
    static_model_id: str,
    reference_model_id: str,
    smoothing_days: int,
) -> None:
    figure, axis = plt.subplots(figsize=(9, 4.5))

    for coldstart_days, line in curve.groupby("coldstart_days"):
        color = COLDSTART_COLORS[coldstart_days]  # type: ignore
        axis.plot(
            line["day_since_start"],
            line["adaptive"],
            color=color,
            linewidth=2,
            label=f"{adaptive_model_id}, Kaltstart {coldstart_days} Tage",
        )
        axis.plot(
            line["day_since_start"],
            line["static"],
            color=color,
            linestyle="--",
            linewidth=1.2,
            label=f"{static_model_id}, Kaltstart {coldstart_days} Tage",
        )

    # die Baseline hängt nicht an der Kaltstart-Länge
    baseline = curve.groupby("day_since_start")["reference"].mean()
    axis.plot(
        baseline.index,
        baseline,
        color="#8C8C8C",
        linestyle=":",
        linewidth=1.5,
        label=reference_model_id,
    )

    axis.set_title(
        f"Tagesfehler der Prognose (Mittel über Starttermine, {smoothing_days} Tage geglättet)",
        loc="left",
    )
    axis.set_xlabel("Tage seit Start")
    axis.set_ylabel("Tagesfehler (W)")
    axis.grid(axis="y", alpha=0.25)
    axis.legend(fontsize=8, ncols=2)

    save_figure(figure, output_directory, "e4_forecast")
