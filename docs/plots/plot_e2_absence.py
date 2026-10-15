from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from docs.plots.plot_style import CONTEXT_COLORS, save_figure, style_axis

DAYS_PER_WEEK = 7


def build_e2_return_plot(
    curve: pd.DataFrame,
    output_directory: Path,
    *,
    context_label: str,
    reference_label: str,
) -> None:
    figure, axis = plt.subplots(figsize=(6.4, 3.4))

    weeks = curve["day_since_return"] / DAYS_PER_WEEK
    axis.axhline(0, color="black", linewidth=0.8)
    axis.plot(weeks, curve["delta"], color=CONTEXT_COLORS["SYS3_CTX1"], linewidth=2)
    axis.set_xticks(np.arange(0, np.ceil(weeks.max()) + 1))
    axis.set_xlabel("Wochen nach der Rückkehr")
    axis.set_ylabel(f"Differenz Tagesfehler [W]\n{context_label} − {reference_label}")
    style_axis(axis)

    save_figure(figure, output_directory, "e2_return")
