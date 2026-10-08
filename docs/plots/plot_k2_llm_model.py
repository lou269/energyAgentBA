from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from docs.plots.plot_style import SYSTEM_COLORS, save_figure
from experiments.k2_llm.k2_config import BASELINE_ID

OTHER_MODEL_COLOR = "#8C8C8C"


def build_k2_plot(
    models: pd.DataFrame,
    output_directory: Path,
    *,
    production_model: str,
) -> None:
    figure, axis = plt.subplots(figsize=(7, 4.5))

    for model_id, model, seconds, macro_f1 in zip(
        models["model_id"],
        models["model"],
        models["mean_generation_seconds"].astype(float),
        models["macro_f1"].astype(float),
    ):
        # Regel wie SYS2, Produktivmodell wie SYS3 eingefärbt
        if model_id == BASELINE_ID:
            color, label = SYSTEM_COLORS["SYS2"], "Regel"
        elif model == production_model:
            color, label = SYSTEM_COLORS["SYS3"], str(model)
        else:
            color, label = OTHER_MODEL_COLOR, str(model)

        axis.scatter(seconds, macro_f1, color=color, s=40)
        axis.annotate(
            label,
            (seconds, macro_f1),
            xytext=(5, 4),
            textcoords="offset points",
            fontsize=8,
        )

    axis.set_title("Einzelfälle: Macro-F1 gegen Antwortzeit je Modell", loc="left")
    axis.set_xlabel("Antwortzeit je Aufruf, Mittel (s)")
    axis.set_ylabel("Macro-F1")
    axis.set_ylim(0, 1.05)
    axis.grid(alpha=0.25)

    save_figure(figure, output_directory, "k2_quality_vs_time")
