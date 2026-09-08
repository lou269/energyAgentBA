# python docs/plots/plot_datengrundlage.py
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.patches import Patch


PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = PROJECT_ROOT / "output"
FIGURE_DIR = PROJECT_ROOT / "docs" / "diagrams" / "generated"

ROLE_COLORS = {
    "primary": "#4C78A8",
    "fallback": "#F2CF5B",
    "not_selected": "#B0B0B0",
}

SPLIT_COLORS = {
    "train": "#4C78A8",
    "validation": "#F2CF5B",
    "test": "#E45756",
}


def add_bar_labels(axis) -> None:
    for container in axis.containers:
        for bar in container:
            height = bar.get_height()

            axis.annotate(
                f"{height:.1f}",
                xy=(bar.get_x() + bar.get_width() / 2, height),
                xytext=(0, 3),
                textcoords="offset points",
                ha="center",
                va="bottom",
                fontsize=8,
            )


def main() -> None:
    profiles = pd.read_csv(OUTPUT_DIR / "selection" / "profiles.csv")
    decisions = pd.read_csv(OUTPUT_DIR / "selection" / "candidate_selection_decisions.csv")
    splits = pd.read_csv(OUTPUT_DIR / "preprocessing" / "split_manifest.csv")

    candidates = profiles.merge(
        decisions[
            [
                "candidate_id",
                "selection_rank",
                "selection_role",
                "min_longest_segment_days",
            ]
        ],
        on="candidate_id",
        how="left",
    ).sort_values("selection_rank")

    date_columns = [
        "first_start",
        "last_end",
        "longest_segment_start",
        "longest_segment_end",
    ]

    for column in date_columns:
        candidates[column] = pd.to_datetime(candidates[column], utc=True)

    splits["start"] = pd.to_datetime(splits["start"], utc=True)
    splits["end"] = pd.to_datetime(splits["end"], utc=True)
    hourly_splits = splits.loc[splits["frequency"].eq("hourly")].copy()

    figure = plt.figure(figsize=(13, 11))
    grid = figure.add_gridspec(
        3,
        3,
        height_ratios=[1.3, 0.65, 1.0],
        hspace=0.55,
        wspace=0.35,
    )

    availability_axis = figure.add_subplot(grid[0, :])
    split_axis = figure.add_subplot(grid[1, :])
    quality_axes = [
        figure.add_subplot(grid[2, index])
        for index in range(3)
    ]

    # A: Messzeiträume und längste zusammenhängende Segmente
    for position, row in enumerate(
        candidates.itertuples(index=False)
    ):
        color = ROLE_COLORS[row.selection_role]

        availability_axis.plot(
            [row.first_start, row.last_end],
            [position, position],
            color="#BDBDBD",
            linewidth=4,
        )
        availability_axis.plot(
            [
                row.longest_segment_start,
                row.longest_segment_end,
            ],
            [position, position],
            color=color,
            linewidth=10,
            solid_capstyle="butt",
        )

    availability_axis.set_yticks(range(len(candidates)))
    availability_axis.set_yticklabels(
        [
            f"{row.candidate_id} ({row.selection_role})"
            for row in candidates.itertuples(index=False)
        ]
    )
    availability_axis.invert_yaxis()
    availability_axis.set_title("A: Messzeitraum und längstes zusammenhängendes Segment", loc="left")
    availability_axis.set_xlabel("Zeit")
    availability_axis.grid(axis="x", alpha=0.25)
    availability_axis.xaxis.set_major_locator(mdates.YearLocator())
    availability_axis.xaxis.set_major_formatter( mdates.DateFormatter("%Y"))

    availability_axis.legend(
        handles=[
            Line2D(
                [0],
                [0],
                color="#BDBDBD",
                linewidth=4,
                label="Spanne zwischen erster und letzter Messung",
            ),
            Patch(
                color=ROLE_COLORS["primary"],
                label="längstes Segment: Primärkandidat",
            ),
            Patch(
                color=ROLE_COLORS["fallback"],
                label="längstes Segment: Fallback",
            ),
            Patch(
                color=ROLE_COLORS["not_selected"],
                label="längstes Segment: nicht ausgewählt",
            ),
        ],
        loc="upper right",
        fontsize=8,
    )

    # B: Chronologische Aufteilung
    for row in hourly_splits.itertuples(index=False):
        plot_end = row.end + pd.Timedelta(hours=1)
        width = plot_end - row.start

        split_axis.barh(
            0,
            width,
            left=row.start,
            height=0.55,
            color=SPLIT_COLORS[row.split],
            label=row.split,
        )

        midpoint = row.start + width / 2
        split_axis.text(
            midpoint,
            0,
            row.split.capitalize(),
            ha="center",
            va="center",
            color="white",
            fontweight="bold",
            fontsize=9,
        )

    split_axis.set_yticks([])
    split_axis.set_title("B: Chronologischer stündlicher Split", loc="left")
    split_axis.set_xlabel("Zeit")
    split_axis.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m.%Y"))
    split_axis.tick_params(axis="x", rotation=25)

    # C: Qualitätsvergleich
    candidate_ids = candidates["candidate_id"]
    colors = candidates["selection_role"].map(ROLE_COLORS)

    quality_values = [
        candidates["sampling_share"] * 100,
        candidates["total_coverage_days"],
        candidates["longest_segment_days"],
    ]
    titles = [
        "Sampling Share",
        "Gesamtabdeckung",
        "Längstes Segment",
    ]
    units = ["%", "Tage", "Tage"]

    for axis, values, title, unit in zip(
        quality_axes,
        quality_values,
        titles,
        units,
    ):
        axis.bar(
            candidate_ids,
            values,
            color=colors,
        )
        axis.set_title(title)
        axis.set_ylabel(unit)
        axis.tick_params(axis="x", rotation=25)
        axis.grid(axis="y", alpha=0.25)
        add_bar_labels(axis)

    threshold = candidates["min_longest_segment_days"].dropna().iloc[0]

    quality_axes[2].axhline(
        threshold,
        color="#E45756",
        linestyle="--",
        linewidth=1.5,
        label=f"Mindestwert: {threshold:.0f} Tage",
    )
    quality_axes[2].legend(fontsize=8)

    figure.suptitle(
        "Datengrundlage und Kandidatenauswahl",
        fontsize=15,
        fontweight="bold",
    )

    FIGURE_DIR.mkdir(parents=True, exist_ok=True)

    figure.savefig(str(FIGURE_DIR / "datengrundlage_und_auswahl.svg"), bbox_inches="tight")
    figure.savefig(str(FIGURE_DIR / "datengrundlage_und_auswahl.png"), dpi=300, bbox_inches="tight")

    plt.close(figure)


if __name__ == "__main__":
    main()