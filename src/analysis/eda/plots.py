from __future__ import annotations

import logging
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from matplotlib.ticker import PercentFormatter
from pandas.plotting import register_matplotlib_converters

register_matplotlib_converters()

logger = logging.getLogger(__name__)

DEFAULT_DPI = 200


def _validate_columns(
    df: pd.DataFrame,
    required_columns: Sequence[str],
    dataframe_name: str,
) -> None:
    missing = [
        column
        for column in required_columns
        if column not in df.columns
    ]

    if missing:
        raise ValueError(
            f"Missing columns in {dataframe_name}: {missing}"
        )


def _format_appliances(value: Any) -> str:
    if value is None:
        return "unknown"

    if isinstance(value, (list, tuple, set)):
        values = [
            str(item).strip()
            for item in value
            if str(item).strip()
        ]
        return ", ".join(values) if values else "unknown"

    text = str(value).strip()
    return text if text else "unknown"


def _channel_label(row: pd.Series) -> str:
    appliance = _format_appliances(row.get("appliances"))
    return (
        f"H{row['house']} | "
        f"M{row['meter_instance']} | "
        f"{appliance}"
    )


def _prepare_channel_quality(
    channel_quality: pd.DataFrame,
) -> pd.DataFrame:
    required_columns = [
        "house",
        "meter_instance",
        "appliances",
        "start",
        "end",
        "duration_days",
        "good_duration_days",
        "longest_good_section_days",
        "dropout_rate",
    ]
    _validate_columns(channel_quality, required_columns, "channel_quality")

    df = channel_quality.copy()

    df["start"] = pd.to_datetime(df["start"], errors="coerce", utc=True)
    df["end"] = pd.to_datetime(df["end"], errors="coerce", utc=True)

    numeric_columns = [
        "duration_days",
        "good_duration_days",
        "longest_good_section_days",
        "dropout_rate",
    ]

    for column in numeric_columns:
        df[column] = pd.to_numeric(df[column], errors="coerce")

    df["channel_label"] = df.apply(_channel_label, axis=1)

    return df


def _selection_keys(
    selected_channels: pd.DataFrame | None,
) -> set[tuple[Any, Any]]:
    if selected_channels is None or selected_channels.empty:
        return set()

    _validate_columns(selected_channels, ["house", "meter_instance"], "selected_channels")

    return {
        (row.house, row.meter_instance)
        for row in selected_channels[
            ["house", "meter_instance"]
        ].drop_duplicates().itertuples(index=False)
    }


def _add_selection_flag(
    df: pd.DataFrame,
    selected_channels: pd.DataFrame | None,
) -> pd.DataFrame:
    result = df.copy()
    keys = _selection_keys(selected_channels)

    result["selected"] = [
        (house, meter_instance) in keys
        for house, meter_instance in zip(
            result["house"],
            result["meter_instance"],
        )
    ]

    return result


def _save_figure(
    figure: Figure,
    output_path: str | Path,
    dpi: int = DEFAULT_DPI,
) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    figure.savefig(str(path), dpi=dpi, bbox_inches="tight")
    plt.close(figure)

    logger.info("Saved plot to %s", path)
    return path

def _set_percentage_axis(
    ax: Axes,
    values: pd.Series,
    axis: str = "x",
) -> None:
    clean_values = values.apply(
        pd.to_numeric,
        errors="coerce",
    ).dropna()

    if clean_values.empty:
        return

    xmax = (
        1.0
        if float(clean_values.max()) <= 1.0
        else 100.0
    )

    formatter = PercentFormatter(
        xmax=xmax,
        decimals=0,
    )

    if axis == "x":
        ax.xaxis.set_major_formatter(formatter)
    elif axis == "y":
        ax.yaxis.set_major_formatter(formatter)
    else:
        raise ValueError("axis must be 'x' or 'y'")


def plot_channel_availability(
    channel_quality: pd.DataFrame,
    output_path: str | Path,
    selected_channels: pd.DataFrame | None = None,
    title: str = "Channel availability",
) -> Path:
    df = _prepare_channel_quality(channel_quality)
    df = _add_selection_flag(df, selected_channels)

    df = df.dropna(
        subset=["start", "end"],
    ).sort_values(
        ["house", "meter_instance"],
        ascending=[True, True],
    )

    if df.empty:
        raise ValueError(
            "No valid start/end timestamps available."
        )

    figure_height = max(5.0, 0.38 * len(df))
    figure, ax = plt.subplots(
        figsize=(14, figure_height),
    )

    for y_position, row in enumerate(
        df.itertuples(index=False)
    ):
        linewidth = 5 if row.selected else 3
        alpha = 1.0 if row.selected else 0.45

        ax.hlines(
            y=y_position,
            xmin=row.start,
            xmax=row.end,
            linewidth=linewidth,
            alpha=alpha,
        )

        ax.plot(
            row.start,
            y_position,
            marker="|",
            markersize=8,
            alpha=alpha,
        )
        ax.plot(
            row.end,
            y_position,
            marker="|",
            markersize=8,
            alpha=alpha,
        )

    ax.set_yticks(range(len(df)))
    ax.set_yticklabels(df["channel_label"])
    ax.set_xlabel("Date")
    ax.set_ylabel("Channel")
    ax.set_title(title)
    ax.grid(axis="x", alpha=0.25)

    locator = mdates.AutoDateLocator()
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(
        mdates.ConciseDateFormatter(locator)
    )

    figure.tight_layout()
    return _save_figure(figure, output_path)


def plot_quality_metric(
    channel_quality: pd.DataFrame,
    metric: str,
    output_path: str | Path,
    selected_channels: pd.DataFrame | None = None,
    threshold: float | None = None,
    title: str | None = None,
    x_label: str | None = None,
    percentage: bool = False,
) -> Path:
    df = _prepare_channel_quality(channel_quality)

    if metric not in df.columns:
        raise ValueError(
            f"Column '{metric}' is missing in channel_quality."
        )

    df = _add_selection_flag(df, selected_channels)
    df[metric] = pd.to_numeric(
        df[metric],
        errors="coerce",
    )
    df = df.dropna(
        subset=[metric],
    ).sort_values(
        metric,
        ascending=True,
    )

    if df.empty:
        raise ValueError(
            f"No valid values available for '{metric}'."
        )

    figure_height = max(5.0, 0.38 * len(df))
    figure, ax = plt.subplots(
        figsize=(12, figure_height),
    )

    bars = ax.barh(
        df["channel_label"],
        df[metric],
        alpha=0.8,
    )

    for bar, selected in zip(
        bars,
        df["selected"],
    ):
        if selected:
            bar.set_linewidth(2)
            bar.set_edgecolor("black")

    if threshold is not None:
        ax.axvline(
            threshold,
            linestyle="--",
            linewidth=1.5,
            label=f"Threshold: {threshold:g}",
        )
        ax.legend()

    ax.set_xlabel(
        x_label or metric.replace("_", " ").title()
    )
    ax.set_ylabel("Channel")
    ax.set_title(
        title or metric.replace("_", " ").title()
    )
    ax.grid(axis="x", alpha=0.25)

    if percentage:
        _set_percentage_axis(
            ax,
            df[metric],
            axis="x",
        )

    figure.tight_layout()
    return _save_figure(figure, output_path)


def plot_dropout_vs_good_section(
    channel_quality: pd.DataFrame,
    output_path: str | Path,
    selected_channels: pd.DataFrame | None = None,
    annotate_selected: bool = True,
    title: str = (
        "Dropout rate vs. longest continuous good section"
    ),
) -> Path:
    df = _prepare_channel_quality(channel_quality)
    df = _add_selection_flag(df, selected_channels)

    df = df.dropna(subset=["dropout_rate", "longest_good_section_days",])

    if df.empty:
        raise ValueError(
            "No valid dropout and good-section values available."
        )

    figure, ax = plt.subplots(figsize=(11, 7))

    for house, house_df in df.groupby(
        "house",
        sort=True,
    ):
        ax.scatter(
            house_df["dropout_rate"],
            house_df["longest_good_section_days"],
            label=f"House {house}",
            alpha=0.75,
        )

    selected_df = df.loc[df["selected"]]

    if not selected_df.empty:
        ax.scatter(
            selected_df["dropout_rate"],
            selected_df["longest_good_section_days"],
            facecolors="none",
            edgecolors="black",
            linewidths=1.5,
            s=110,
            label="Selected",
        )

        if annotate_selected:
            for row in selected_df.itertuples(index=False):
                ax.annotate(
                    row.channel_label,
                    (
                        row.dropout_rate,
                        row.longest_good_section_days,
                    ),
                    xytext=(5, 5),
                    textcoords="offset points",
                    fontsize=8,
                )

    ax.set_xlabel("Dropout rate")
    ax.set_ylabel("Longest continuous good section [days]")
    ax.set_title(title)
    ax.grid(alpha=0.25)
    ax.legend()

    _set_percentage_axis(
        ax,
        df["dropout_rate"],
        axis="x",
    )

    figure.tight_layout()
    return _save_figure(figure, output_path)


def plot_selection_counts_by_house(
    channel_quality: pd.DataFrame,
    selected_channels: pd.DataFrame,
    output_path: str | Path,
    title: str = "Available and selected channels by house",
) -> Path:
    _validate_columns(
        channel_quality,
        ["house", "meter_instance"],
        "channel_quality",
    )
    _validate_columns(
        selected_channels,
        ["house", "meter_instance"],
        "selected_channels",
    )

    total_counts = (
        channel_quality[
            ["house", "meter_instance"]
        ]
        .drop_duplicates()
        .groupby("house")
        .size()
        .rename("Available")
    )

    selected_counts = (
        selected_channels[
            ["house", "meter_instance"]
        ]
        .drop_duplicates()
        .groupby("house")
        .size()
        .rename("Selected")
    )

    counts = (
        pd.concat(
            [total_counts, selected_counts],
            axis=1,
        )
        .fillna(0)
        .astype(int)
        .sort_index()
    )

    figure, ax = plt.subplots(figsize=(10, 6))

    counts.plot(
        kind="bar",
        ax=ax,
        width=0.8,
    )

    ax.set_xlabel("House")
    ax.set_ylabel("Number of channels")
    ax.set_title(title)
    ax.tick_params(
        axis="x",
        rotation=0,
    )
    ax.grid(axis="y", alpha=0.25)

    containers = getattr(ax, "containers", [])

    for bar in ax.patches:
        height = bar.get_height()

        ax.annotate(
            f"{height:.0f}",
            xy=(
                bar.get_x() + bar.get_width() / 2,
                height,
            ),
            xytext=(0, 3),
            textcoords="offset points",
            ha="center",
            va="bottom",
        )
            
    figure.tight_layout()
    return _save_figure(figure, output_path)


def plot_canonical_ac_type_by_house(
    channel_quality: pd.DataFrame,
    output_path: str | Path,
    title: str = "Canonical AC type availability by house",
) -> Path:
    _validate_columns(
        channel_quality,
        ["house", "has_canonical_ac_type"],
        "channel_quality",
    )

    df = channel_quality.copy()
    df["has_canonical_ac_type"] = (
        df["has_canonical_ac_type"]
        .fillna(False)
        .astype(bool)
    )

    counts = (
        df.groupby(
            ["house", "has_canonical_ac_type"]
        )
        .size()
        .unstack(fill_value=0)
        .rename(
            columns={
                False: "Missing canonical AC type",
                True: "Canonical AC type available",
            }
        )
        .sort_index()
    )

    figure, ax = plt.subplots(
        figsize=(10, 6),
    )

    counts.plot(
        kind="bar",
        stacked=True,
        ax=ax,
        width=0.8,
    )

    ax.set_xlabel("House")
    ax.set_ylabel("Number of channels")
    ax.set_title(title)
    ax.tick_params(
        axis="x",
        rotation=0,
    )
    ax.grid(axis="y", alpha=0.25)
    ax.legend(
        title=None,
        loc="upper right",
    )

    figure.tight_layout()
    return _save_figure(figure, output_path)


def plot_power_timeseries(
    power_data: pd.Series | pd.DataFrame,
    output_path: str | Path,
    start: str | pd.Timestamp | None = None,
    end: str | pd.Timestamp | None = None,
    resample_rule: str | None = None,
    title: str = "Example power time series",
    y_label: str = "Power [W]",
) -> Path:
    if isinstance(power_data, pd.Series):
        column_name = (
            str(power_data.name)
            if power_data.name is not None
            else "power"
        )
        df = power_data.to_frame(column_name)
    else:
        df = power_data.copy()

    if not isinstance(df.index, pd.DatetimeIndex):
        raise ValueError(
            "power_data must have a DatetimeIndex."
        )

    df = df.sort_index()

    if start is not None:
        df = df.loc[df.index >= pd.Timestamp(start)]

    if end is not None:
        df = df.loc[df.index <= pd.Timestamp(end)]

    if resample_rule is not None:
        df = df.resample(resample_rule).mean()

    df = df.dropna(
        how="all",
    )

    if df.empty:
        raise ValueError(
            "No power values available for the selected period."
        )

    figure, ax = plt.subplots(
        figsize=(14, 6),
    )

    for column in df.columns:
        ax.plot(
            df.index,
            df[column],
            label=str(column),
            linewidth=1.0,
        )

    ax.set_xlabel("Time")
    ax.set_ylabel(y_label)
    ax.set_title(title)
    ax.grid(alpha=0.25)

    if len(df.columns) > 1:
        ax.legend()

    locator = mdates.AutoDateLocator()
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(
        mdates.ConciseDateFormatter(locator)
    )

    figure.tight_layout()
    return _save_figure(figure, output_path)

def build_channel_quality_plots(
    channel_quality: pd.DataFrame,
    selected_channels: pd.DataFrame,
    output_dir: Path,
    min_overlap_days: float = 180,
    max_dropout_rate: float | None = None,
) -> list[Path]:
    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    return [
        plot_channel_availability(
            channel_quality=channel_quality,
            selected_channels=selected_channels,
            output_path=output_dir / "channel_availability.png",
        ),

        plot_quality_metric(
            channel_quality=channel_quality,
            metric="longest_good_section_days",
            output_path=output_dir / "longest_good_sections.png",
            selected_channels=selected_channels,
            threshold=min_overlap_days,
            title="Longest continuous good section by channel",
            x_label="Longest good section [days]",
        ),

        plot_quality_metric(
            channel_quality=channel_quality,
            metric="dropout_rate",
            output_path=output_dir / "dropout_rates.png",
            selected_channels=selected_channels,
            threshold=max_dropout_rate,
            title="Dropout rate by channel",
            x_label="Dropout rate",
            percentage=True,
        ),

        plot_dropout_vs_good_section(
            channel_quality=channel_quality,
            selected_channels=selected_channels,
            output_path=output_dir / "dropout_vs_good_section.png",
        ),

        plot_selection_counts_by_house(
            channel_quality=channel_quality,
            selected_channels=selected_channels,
            output_path=output_dir / "selection_counts_by_house.png",
        ),

        plot_canonical_ac_type_by_house(
            channel_quality=channel_quality,
            output_path=output_dir / "canonical_ac_type_by_house.png",
        ),
    ]

  
