# python docs/plots/plot_anomalie_zeitreihe.py
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.patches import Patch


PROJECT_ROOT = Path(__file__).resolve().parents[2]
INPUT_PATH = (
    PROJECT_ROOT
    / "output"
    / "numerical_analysis"
    / "anomaly_scores_hourly.csv"
)
FIGURE_DIR = PROJECT_ROOT / "docs" / "diagrams" / "generated"

SPLIT_BG_COLORS = {
    "train": "#B0B0B0",
    "validation": "#4C78A8",
    "test": "#54A24B",
}

LEVEL_COLORS = {
    "unusual": "#F58518",
    "strong_anomaly": "#E45756",
}

LEVEL_LABELS = {
    "unusual": "Unusual",
    "strong_anomaly": "Strong Anomaly",
}

SCALE_ORDER = ["short_term", "daily", "weekly", "long_term"]
SCALE_LABELS = {
    "short_term": "Kurzfristig",
    "daily": "Täglich",
    "weekly": "Wöchentlich",
    "long_term": "Langfristig",
}

UNUSUAL_THRESHOLD = 2.0
STRONG_ANOMALY_THRESHOLD = 3.0


def shade_splits(axis, splits: pd.DataFrame) -> None:
    for split_name, group in splits.groupby("split"):
        axis.axvspan(
            group["timestamp"].min(),
            group["timestamp"].max(),
            color=SPLIT_BG_COLORS[str(split_name)],
            alpha=0.10,
            linewidth=0,
        )


def main() -> None:
    scores = pd.read_csv(INPUT_PATH)
    scores["timestamp"] = pd.to_datetime(scores["timestamp"], utc=True)
    scores = scores.sort_values("timestamp")

    anomalies = scores.loc[scores["anomaly_level"].isin(LEVEL_COLORS)]
    top_event = scores.loc[scores["anomaly_score"].idxmax()]

    figure = plt.figure(figsize=(13, 13))
    grid = figure.add_gridspec(
        4,
        2,
        height_ratios=[1.0, 0.9, 0.9, 1.0],
        hspace=0.65,
        wspace=0.3,
    )

    power_axis = figure.add_subplot(grid[0, :])
    score_axis = figure.add_subplot(grid[1, :], sharex=power_axis)
    scale_axis = figure.add_subplot(grid[2, 0])
    direction_axis = figure.add_subplot(grid[2, 1])
    zoom_axis = figure.add_subplot(grid[3, :])

    # A: Leistung über die Zeit mit markierten Anomalien
    shade_splits(power_axis, scores[["timestamp", "split"]])
    power_axis.plot(
        scores["timestamp"],
        scores["current_power"],
        color="#444444",
        linewidth=0.6,
    )

    for level in ["unusual", "strong_anomaly"]:
        level_points = anomalies.loc[anomalies["anomaly_level"].eq(level)]
        power_axis.scatter(
            level_points["timestamp"],
            level_points["current_power"],
            color=LEVEL_COLORS[level],
            s=16 if level == "unusual" else 26,
            zorder=3,
            label=LEVEL_LABELS[level],
        )

    power_axis.set_title(
        "A: Leistung mit erkannten Anomalien (Train / Validation / Test)",
        loc="left",
    )
    power_axis.set_ylabel("Leistung (W)")
    power_axis.legend(
        handles=[
            Patch(
                color=SPLIT_BG_COLORS["train"], alpha=0.3, label="Train"
            ),
            Patch(
                color=SPLIT_BG_COLORS["validation"],
                alpha=0.3,
                label="Validation",
            ),
            Patch(
                color=SPLIT_BG_COLORS["test"], alpha=0.3, label="Test"
            ),
            Line2D(
                [0],
                [0],
                marker="o",
                color="none",
                markerfacecolor=LEVEL_COLORS["unusual"],
                markersize=7,
                label=LEVEL_LABELS["unusual"],
            ),
            Line2D(
                [0],
                [0],
                marker="o",
                color="none",
                markerfacecolor=LEVEL_COLORS["strong_anomaly"],
                markersize=8,
                label=LEVEL_LABELS["strong_anomaly"],
            ),
        ],
        fontsize=7.5,
        ncol=5,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.28),
    )

    # B: Anomaly Score über die Zeit mit Schwellenwerten
    shade_splits(score_axis, scores[["timestamp", "split"]])
    score_axis.plot(
        scores["timestamp"],
        scores["anomaly_score"],
        color="#444444",
        linewidth=0.7,
    )
    score_axis.axhline(
        UNUSUAL_THRESHOLD,
        color=LEVEL_COLORS["unusual"],
        linestyle="--",
        linewidth=1.3,
        label=f"Unusual-Schwelle ({UNUSUAL_THRESHOLD:.1f})",
    )
    score_axis.axhline(
        STRONG_ANOMALY_THRESHOLD,
        color=LEVEL_COLORS["strong_anomaly"],
        linestyle="--",
        linewidth=1.3,
        label=f"Strong-Anomaly-Schwelle ({STRONG_ANOMALY_THRESHOLD:.1f})",
    )
    score_axis.annotate(
        f"Max: {top_event['anomaly_score']:.1f}\n"
        f"({top_event['timestamp']:%d.%m.%Y %H:%M})",
        xy=(top_event["timestamp"], top_event["anomaly_score"]),
        xytext=(10, 8),
        textcoords="offset points",
        fontsize=7.5,
        arrowprops=dict(arrowstyle="->", color="#333333", linewidth=0.8),
    )

    score_axis.set_title(
        "B: Anomaly Score über die Zeit", loc="left"
    )
    score_axis.set_ylabel("Anomaly Score")
    score_axis.set_xlabel("Zeit")
    score_axis.xaxis.set_major_formatter(mdates.DateFormatter("%m/%Y"))
    score_axis.legend(fontsize=8, loc="upper left")

    # C: Anomalien nach dominanter Skala
    counts = (
        anomalies.groupby(["dominant_scale", "anomaly_level"])
        .size()
        .unstack(fill_value=0)
        .reindex(SCALE_ORDER)
    )

    x_positions = np.arange(len(SCALE_ORDER))
    bar_width = 0.35

    for offset, level in zip([-bar_width / 2, bar_width / 2], LEVEL_COLORS):
        scale_axis.bar(
            x_positions + offset,
            counts[level],
            width=bar_width,
            color=LEVEL_COLORS[level],
            label=LEVEL_LABELS[level],
        )

    scale_axis.set_xticks(x_positions)
    scale_axis.set_xticklabels([SCALE_LABELS[s] for s in SCALE_ORDER])
    scale_axis.set_title(
        "C: Anomalien nach dominanter Skala", loc="left"
    )
    scale_axis.set_ylabel("Anzahl Stunden")
    scale_axis.grid(axis="y", alpha=0.25)
    scale_axis.legend(fontsize=8)

    # D: Anomalien nach Richtung (über/unter Erwartung)
    direction_counts = (
        anomalies.groupby(["anomaly_direction", "anomaly_level"])
        .size()
        .unstack(fill_value=0)
        .reindex(["high", "low"])
    )

    direction_positions = np.arange(2)

    bottoms = np.zeros(2)
    for level in LEVEL_COLORS:
        values = direction_counts[level].to_numpy()
        direction_axis.bar(
            direction_positions,
            values,
            bottom=bottoms,
            width=0.5,
            color=LEVEL_COLORS[level],
            label=LEVEL_LABELS[level],
        )
        bottoms += values

    direction_axis.set_xticks(direction_positions)
    direction_axis.set_xticklabels(
        ["Über Erwartung\n(high)", "Unter Erwartung\n(low)"]
    )
    direction_axis.set_title(
        "D: Anomalien nach Richtung", loc="left"
    )
    direction_axis.set_ylabel("Anzahl Stunden")
    direction_axis.grid(axis="y", alpha=0.25)
    direction_axis.legend(fontsize=8)

    # E: Zoom auf die stärkste Anomalie
    window_start = top_event["timestamp"] - pd.Timedelta(hours=48)
    window_end = top_event["timestamp"] + pd.Timedelta(hours=48)
    window = scores.loc[
        scores["timestamp"].between(window_start, window_end)
    ]

    zoom_axis.plot(
        window["timestamp"],
        window["current_power"],
        color="#222222",
        marker="o",
        markersize=3,
        linewidth=1.3,
        label="Ist-Leistung",
    )
    zoom_axis.plot(
        window["timestamp"],
        window["daily_expected"],
        color="#4C78A8",
        linestyle="--",
        linewidth=1.3,
        label="Tageserwartung",
    )
    zoom_axis.plot(
        window["timestamp"],
        window["weekly_expected"],
        color="#54A24B",
        linestyle="--",
        linewidth=1.3,
        label="Wochenerwartung",
    )
    zoom_axis.scatter(
        [top_event["timestamp"]],
        [top_event["current_power"]],
        color=LEVEL_COLORS["strong_anomaly"],
        s=90,
        zorder=4,
        marker="*",
        label="Erkannte Anomalie",
    )

    zoom_axis.set_title(
        "E: Zoom auf die stärkste Anomalie "
        f"({top_event['timestamp']:%d.%m.%Y %H:%M}, "
        f"Score={top_event['anomaly_score']:.1f}, "
        f"dominant: {SCALE_LABELS[str(top_event['dominant_scale'])]})",
        loc="left",
    )
    zoom_axis.set_xlabel("Zeit")
    zoom_axis.set_ylabel("Leistung (W)")
    zoom_axis.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m. %H:%M"))
    zoom_axis.tick_params(axis="x", rotation=20)
    zoom_axis.grid(axis="y", alpha=0.25)
    zoom_axis.legend(fontsize=8)

    figure.suptitle(
        "Multi-Scale-Anomalieerkennung: Scores und erkannte Ereignisse",
        fontsize=15,
        fontweight="bold",
    )

    FIGURE_DIR.mkdir(parents=True, exist_ok=True)

    figure.savefig(
        str(FIGURE_DIR / "anomalie_zeitreihe.svg"),
        bbox_inches="tight",
    )
    figure.savefig(
        str(FIGURE_DIR / "anomalie_zeitreihe.png"),
        dpi=300,
        bbox_inches="tight",
    )

    plt.close(figure)


if __name__ == "__main__":
    main()
