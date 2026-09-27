from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from docs.plots.plot_style import MODEL_COLORS, save_figure
from experiments.k1_forecast_model.k1_config import MODEL_LABELS
from experiments.k1_forecast_model.k1_evaluation import WHOLE_YEAR


def build_seasonality_plot(
    by_month: pd.DataFrame,
    output_directory: Path,
    *,
    model_ids: list[str],
    reference_model_id: str,
) -> None:
    months = by_month.loc[by_month["month"].ne(WHOLE_YEAR)]

    figure, axis = plt.subplots(figsize=(9, 4.5))
    for model_id in model_ids:
        axis.plot(
            months["month"],
            months[model_id],
            color=MODEL_COLORS[model_id],
            linewidth=2,
            marker="o",
            markersize=3,
            label=MODEL_LABELS[model_id],
        )
    axis.plot(
        months["month"],
        months[reference_model_id],
        color=MODEL_COLORS[reference_model_id],
        linewidth=1.5,
        linestyle="--",
        label=MODEL_LABELS[reference_model_id],
    )

    axis.set_title("MAE der Tagesprognose je Monat", loc="left")
    axis.set_ylabel("MAE (W)")
    axis.tick_params(axis="x", labelrotation=45)
    axis.grid(axis="y", alpha=0.25)
    axis.legend(fontsize=8)

    save_figure(figure, output_directory, "k1_mae_by_month")
