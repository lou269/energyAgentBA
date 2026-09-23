from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
import numpy as np
import pandas as pd

VARIANT_COLORS = {
    "REF_STATIC": "#4C78A8",
    "REF_EXPANDING": "#F58518",
    "REF_ROLL60": "#54A24B",
}
VARIANT_LABELS = {
    "REF_STATIC": "Statisch (heute)",
    "REF_EXPANDING": "Expanding",
    "REF_ROLL60": "Rolling 60",
}


def build_k3_plots(
    control_summary: pd.DataFrame,
    weekly_shift: pd.DataFrame,
    output_directory: Path,
    *,
    unusual_threshold: float,
) -> None:
    variants = [variant for variant in VARIANT_COLORS if variant in set(control_summary["variant"])]

    before = control_summary.loc[control_summary["phase"].eq("before")]
    cutover_dates = sorted(before["cutover_date"].unique())
    positions = np.arange(len(cutover_dates))
    bar_width = 0.8 / len(variants)

    figure, axis = plt.subplots(figsize=(9, 4))
    for offset, variant in enumerate(variants):
        rates = before.loc[before["variant"].eq(variant)].set_index("cutover_date").reindex(cutover_dates)["alarm_rate"]
        axis.bar(
            positions + (offset - (len(variants) - 1) / 2) * bar_width, rates * 100,
            width=bar_width - 0.02, color=VARIANT_COLORS[variant], label=VARIANT_LABELS[variant],
        )
    axis.set_xticks(positions, [f"Cutover {date}" for date in cutover_dates])
    axis.set_ylabel("Alarmtage vor Cutover (%)")
    axis.set_title("Fehlalarme im Kontrolllauf (60 Tage Überwachung vor dem Cutover)", loc="left")
    axis.grid(axis="y", alpha=0.25)
    axis.legend(fontsize=8)
    figure.savefig(str(output_directory / "k3_fehlalarme_kontrolle.png"), dpi=300, bbox_inches="tight")
    plt.close(figure)

    figure, axis = plt.subplots(figsize=(8, 4))
    for variant in variants:
        curve = weekly_shift.loc[weekly_shift["variant"].eq(variant)]
        axis.plot(
            curve["week_since_cutover"], curve["score_shift"],
            color=VARIANT_COLORS[variant], linewidth=2, label=VARIANT_LABELS[variant],
        )
    axis.axvline(0, color="#333333", linewidth=1)
    axis.axhline(0, color="#333333", linewidth=0.8)
    axis.axhline(unusual_threshold, color="#333333", linewidth=1, linestyle="--")
    axis.set_title("Wie lange bleibt die Stufe auffällig? (gestrichelt: unusual-Schwelle, Mittel über Cutover)", loc="left")
    axis.set_xlabel("Wochen seit Cutover")
    axis.set_ylabel("Score Stufe - Kontrolle")
    axis.xaxis.set_major_locator(MaxNLocator(integer=True))
    axis.grid(axis="y", alpha=0.25)
    axis.legend(fontsize=8)
    figure.savefig(str(output_directory / "k3_einsickern_score_shift.png"), dpi=300, bbox_inches="tight")
    plt.close(figure)