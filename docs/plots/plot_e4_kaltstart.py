from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from docs.plots.plot_forecast_model_vergleich import BASELINE_COLORS
from experiments.proposal_experiments.e4_cold_start.e4_analysis import ALL_STARTS

# Grüntöne von C3 aus K2, je länger die Historie beim Start, desto dunkler
COLDSTART_COLORS = {7: "#54A24B", 14: "#3F7A38", 30: "#2A5225"}


def build_e4_plot(curve: pd.DataFrame, output_directory: Path, *, variant_id: str, reference_model_id: str) -> None:
    mean_curve = curve.loc[curve["start_date"].eq(ALL_STARTS)]
    coldstart_days = sorted(mean_curve["coldstart_days"].unique())

    figure, axis = plt.subplots(figsize=(9, 4.5))
    for days in coldstart_days:
        line = mean_curve.loc[mean_curve["coldstart_days"].eq(days) & mean_curve["model_id"].eq(variant_id)]
        axis.plot(
            line["day_since_start"], line["mae_w_smoothed"],
            color=COLDSTART_COLORS[days], linewidth=2, label=f"{variant_id}, Kaltstart {days} Tage",
        )

    # die Baseline braucht höchstens 168h Historie, ist also für alle Kaltstart-Längen gleich
    reference = mean_curve.loc[mean_curve["coldstart_days"].eq(coldstart_days[-1]) & mean_curve["model_id"].eq(reference_model_id)]
    axis.plot(
        reference["day_since_start"], reference["mae_w_smoothed"],
        color=BASELINE_COLORS[reference_model_id], linewidth=1.5, linestyle="--", label=reference_model_id,
    )
    

    axis.set_title("Lernkurve nach dem Kaltstart (Mittel über Starttermine, 7 Tage geglättet)", loc="left")
    axis.set_xlabel("Tage seit Start")
    axis.set_ylabel("MAE (W)")
    axis.grid(axis="y", alpha=0.25)
    axis.legend(fontsize=8)

    figure.savefig(str(output_directory / "e4_lernkurve.png"), dpi=300, bbox_inches="tight")
    plt.close(figure)
    
    