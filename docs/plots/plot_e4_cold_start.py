from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from docs.plots.plot_style import COLDSTART_COLORS, MODEL_COLORS, save_figure
from experiments.e4_cold_start.e4_evaluation import ALL_STARTS


def build_e4_plot(
    curve: pd.DataFrame,
    output_directory: Path,
    *,
    variant_id: str,
    reference_model_id: str,
    smoothing_days: int,
) -> None:
    mean_curve = curve.loc[curve["start_date"].eq(ALL_STARTS)]
    coldstart_days = sorted(mean_curve["coldstart_days"].unique())

    figure, axis = plt.subplots(figsize=(9, 4.5))
    for days in coldstart_days:
        line = mean_curve.loc[
            mean_curve["coldstart_days"].eq(days)
            & mean_curve["model_id"].eq(variant_id)
        ]
        axis.plot(
            line["day_since_start"],
            line["mae_w_smoothed"],
            color=COLDSTART_COLORS[days],
            linewidth=2,
            label=f"{variant_id}, Kaltstart {days} Tage",
        )

    reference = mean_curve.loc[
        mean_curve["coldstart_days"].eq(coldstart_days[-1])
        & mean_curve["model_id"].eq(reference_model_id)
    ]
    axis.plot(
        reference["day_since_start"],
        reference["mae_w_smoothed"],
        color=MODEL_COLORS[reference_model_id],
        linewidth=1.5,
        linestyle="--",
        label=reference_model_id,
    )

    axis.set_title(
        f"Lernkurve nach dem Kaltstart (Mittel über Starttermine, {smoothing_days} Tage geglättet)",
        loc="left",
    )
    axis.set_xlabel("Tage seit Start")
    axis.set_ylabel("MAE (W)")
    axis.grid(axis="y", alpha=0.25)
    axis.legend(fontsize=8)

    save_figure(figure, output_directory, "e4_learning_curve")
