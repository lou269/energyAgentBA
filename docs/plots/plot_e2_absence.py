from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.lines import Line2D

from docs.plots.plot_style import CLASSIFICATION_COLORS, CONTEXT_COLORS, save_figure

ADAPTION_MARKERS = {"advance_history_start": "x", "exclude_window": "s"}
ADAPTION_LABELS = {"advance_history_start": "Reset", "exclude_window": "Ausschluss"}


def build_e2_plot(
    timeline: pd.DataFrame,
    output_directory: Path,
    *,
    configs: tuple[str, ...],
    config_labels: dict[str, str],
    name: str,
) -> None:
    figure, (consumption_axis, decision_axis) = plt.subplots(
        2,
        1,
        figsize=(10, 5.5),
        sharex=True,
        gridspec_kw={"height_ratios": [3, 1]},
    )

    vacation = timeline.loc[timeline["phase"].eq("absence"), "absence_day"]
    for axis in (consumption_axis, decision_axis):
        axis.axvspan(
            vacation.min() - 0.5, vacation.max() + 0.5, color="#DDDDDD", zorder=0
        )

    actual = timeline.drop_duplicates("analyzed_day")
    consumption_axis.plot(
        actual["absence_day"],
        actual["actual_w"],
        color="#222222",
        linewidth=2,
        label="Verbrauch (Tagesmittel)",
    )

    for row, config in enumerate(configs):
        days = timeline.loc[timeline["config"].eq(config)]
        consumption_axis.plot(
            days["absence_day"],
            days["forecast_w"],
            color=CONTEXT_COLORS[config],
            linewidth=1.2,
            label=f"Prognose {config_labels[config]}",
        )

        classified = days.loc[days["classification"].isin(CLASSIFICATION_COLORS)]
        decision_axis.scatter(
            classified["absence_day"],
            [row] * len(classified),
            color=classified["classification"].map(CLASSIFICATION_COLORS),
            s=40,
            zorder=3,
        )
        for action, marker in ADAPTION_MARKERS.items():
            adapted = days.loc[days["adaption_action"].eq(action)]
            decision_axis.scatter(
                adapted["absence_day"],
                [row] * len(adapted),
                marker=marker,
                s=110,
                # das Kreuz hat keine Fläche, das Quadrat bleibt hohl
                facecolors="none" if marker == "s" else "#222222",
                edgecolors="#222222" if marker == "s" else None,
                zorder=4,
            )

    consumption_axis.set_title(
        "Verbrauch und Prognose um den Urlaub (grau), darunter die Einordnung je Tag",
        loc="left",
    )
    consumption_axis.set_ylabel("Leistung (W)")
    consumption_axis.grid(axis="y", alpha=0.25)
    consumption_axis.legend(fontsize=8, loc="upper left")

    decision_axis.set_yticks(
        range(len(configs)), [config_labels[config] for config in configs]
    )
    # erstes System oben wie in der Legende
    decision_axis.set_ylim(len(configs) - 0.4, -0.6)
    decision_axis.set_xlabel("Tag seit Urlaubsbeginn (eingeordneter Tag, Ortszeit)")
    decision_axis.legend(
        handles=[
            Line2D(
                [],
                [],
                marker="o",
                linestyle="",
                color=color,
                label=classification,
            )
            for classification, color in CLASSIFICATION_COLORS.items()
        ]
        + [
            Line2D(
                [],
                [],
                marker=marker,
                linestyle="",
                markerfacecolor="none" if marker == "s" else "#222222",
                markeredgecolor="#222222",
                label=ADAPTION_LABELS[action],
            )
            for action, marker in ADAPTION_MARKERS.items()
        ],
        fontsize=7,
        ncol=4,
        loc="upper left",
        bbox_to_anchor=(0, -0.45),
        frameon=False,
    )

    save_figure(figure, output_directory, name)
