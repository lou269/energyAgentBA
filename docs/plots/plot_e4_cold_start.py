from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from docs.plots.plot_style import (
    COLDSTART_COLORS,
    MODEL_COLORS,
    save_figure,
    style_axis,
)


DAYS_PER_WEEK = 7


def build_e4_forecast_plot(
    gap_curve: pd.DataFrame,
    curve: pd.DataFrame,
    output_directory: Path,
    *,
    adaptive_model_id: str,
    static_model_id: str,
    shortest: int,
    longest: int,
) -> None:
    figure, (gap_axis, model_axis) = plt.subplots(2, 1, figsize=(6.4, 5.6), sharex=True)

    gap_axis.axhline(0, color="black", linewidth=0.8)
    gap_axis.plot(
        gap_curve["day_since_start"] / DAYS_PER_WEEK,
        gap_curve["delta"],
        color=COLDSTART_COLORS[shortest],
        linewidth=2,
    )
    gap_axis.set_ylabel(
        f"(a) Differenz Tagesfehler [W]\n{adaptive_model_id}, {shortest} − {longest} Tage"
    )

    line = curve.loc[curve["coldstart_days"].eq(shortest)]
    model_axis.plot(
        line["day_since_start"] / DAYS_PER_WEEK,
        line["static"],
        color=MODEL_COLORS[static_model_id],
        linewidth=2,
        label=static_model_id,
    )
    model_axis.plot(
        line["day_since_start"] / DAYS_PER_WEEK,
        line["adaptive"],
        color=MODEL_COLORS[adaptive_model_id],
        linewidth=2,
        label=adaptive_model_id,
    )
    model_axis.set_ylabel(f"(b) Tagesfehler [W]\n{shortest} Tage Starthistorie")
    model_axis.set_xlabel("Wochen nach dem Start")
    model_axis.set_xticks(
        np.arange(0, line["day_since_start"].max() / DAYS_PER_WEEK + 1)
    )
    model_axis.legend(fontsize=8)

    for axis in (gap_axis, model_axis):
        style_axis(axis)

    save_figure(figure, output_directory, "e4_forecast")


def build_e4_detection_plot(
    weeks: pd.DataFrame,
    output_directory: Path,
    *,
    shortest: int,
    longest: int,
) -> None:
    by_week = weeks.dropna(subset=["week", "injections"])
    positions = np.arange(len(by_week))
    width = 0.38
    figure, axis = plt.subplots(figsize=(6.4, 3.4))

    for offset, (coldstart_days, column) in zip(
        (-width / 2, width / 2),
        ((shortest, "detected_shortest"), (longest, "detected_longest")),
    ):
        axis.bar(
            positions + offset,
            by_week[column],
            width=width,
            color=COLDSTART_COLORS[coldstart_days],
            label=f"{coldstart_days} Tage Starthistorie",
        )
    axis.step(
        np.append(positions - 0.5, positions[-1] + 0.5),
        np.append(by_week["injections"].to_numpy(), by_week["injections"].iloc[-1]),
        where="post",
        color="#222222",
        linewidth=1,
        label="eingebaute Einzelanomalien",
    )

    axis.set_xticks(positions, [str(int(week)) for week in by_week["week"]])
    axis.set_xlabel("Woche nach dem Start")
    axis.set_ylabel("erkannte Einzelanomalien")
    axis.set_ylim(0, by_week["injections"].max() + 0.5)
    axis.legend(
        fontsize=8,
        ncol=3,
        loc="lower center",
        bbox_to_anchor=(0.5, 1.0),
        frameon=False,
    )
    style_axis(axis)

    save_figure(figure, output_directory, "e4_detection")
