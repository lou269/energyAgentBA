from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.axes import Axes

from docs.plots.plot_style import SYSTEM_COLORS, save_figure
from src.config.config_forecasting import SYS_LABELS


def build_e3_plot(
    results: pd.DataFrame,
    output_directory: Path,
    *,
    event_days: dict[str, list[int]],
    series_labels: dict[str, str],
) -> None:
    cutover_dates = sorted(results["cutover_date"].unique())
    panels = [
        (cutover_date, series)
        for cutover_date in cutover_dates
        for series in event_days
    ]
    figure, axes = plt.subplots(
        len(panels), 1, figsize=(9, 3.2 * len(panels)), squeeze=False
    )

    for axis, (cutover_date, series) in zip(axes[:, 0], panels):
        series_days = results.loc[
            results["series"].eq(series) & results["cutover_date"].eq(cutover_date)
        ]
        for config, color in SYSTEM_COLORS.items():
            days = series_days.loc[series_days["config"].eq(config)]
            if days.empty:
                continue

            reset = days["adaption_action"].eq("advance_history_start")
            axis.plot(
                days["days_since_cutover"],
                days["day_error_w"],
                color=color,
                linewidth=1.5,
                label=SYS_LABELS[config],
            )
            axis.scatter(
                days.loc[reset, "days_since_cutover"],
                days.loc[reset, "day_error_w"],
                color=color,
                marker="x",
                s=60,
                zorder=3,
            )

        # der Ereignistag ist schon der erste Prognosetag mit Ereignis, die Linie liegt davor
        for day in event_days[series]:
            axis.axvline(day - 0.5, linewidth=1)
        axis.set_title(f"Cutover {cutover_date}, {series_labels[series]}", loc="left")
        axis.set_ylabel("Tagesfehler (W)")
        axis.grid(axis="y", alpha=0.25)

    axes[0, 0].legend(fontsize=8)
    axes[-1, 0].set_xlabel("Prognosetag seit Cutover (senkrecht: Ereignisse, x: Reset)")
    save_figure(figure, output_directory, "e3_timeline")


@dataclass(frozen=True)
class WeekPanel:
    # eine Spalte der Wochenabbildung, gepoolt (dick) und je Fall (dünn)
    title: str
    forecast: pd.DataFrame
    case_forecast: pd.DataFrame
    notifications: pd.DataFrame
    case_notifications: pd.DataFrame


def _plot_case(axis: Axes, x: pd.Series, y: pd.Series, color: str) -> None:
    axis.plot(x, y, color=color, alpha=0.25, linewidth=0.8)


def _plot_pooled(
    axis: Axes, x: pd.Series, y: pd.Series, color: str, label: str
) -> None:
    axis.plot(x, y, color=color, linewidth=2, marker="o", markersize=4, label=label)


def build_e3_week_plot(
    panels: list[WeekPanel],
    output_directory: Path,
    *,
    name: str,
    reference: str,
    llm: str,
) -> None:
    case_keys = ["cutover_date", "series"]
    figure, axes = plt.subplots(
        3, len(panels), figsize=(5.5 * len(panels), 9), sharex="col", squeeze=False
    )
    reference_color = SYSTEM_COLORS[reference]
    llm_color = SYSTEM_COLORS[llm]

    for column, panel in enumerate(panels):
        error_axis, delta_axis, notification_axis = axes[:, column]

        for _, case in panel.case_forecast.groupby(case_keys):
            _plot_case(
                error_axis, case["week"], case["reference_day_error_w"], reference_color
            )
            _plot_case(error_axis, case["week"], case["llm_day_error_w"], llm_color)
            _plot_case(delta_axis, case["week"], case["day_error_delta_w"], llm_color)
        weeks = panel.forecast["week"]
        _plot_pooled(
            error_axis,
            weeks,
            panel.forecast["reference_day_error_w"],
            reference_color,
            SYS_LABELS[reference],
        )
        _plot_pooled(
            error_axis,
            weeks,
            panel.forecast["llm_day_error_w"],
            llm_color,
            SYS_LABELS[llm],
        )
        _plot_pooled(
            delta_axis, weeks, panel.forecast["day_error_delta_w"], llm_color, llm
        )
        delta_axis.axhline(0, color="black", linewidth=0.8)

        for config in (reference, llm):
            color = SYSTEM_COLORS[config]
            of_config = panel.case_notifications["config"].eq(config)
            for _, case in panel.case_notifications.loc[of_config].groupby(case_keys):
                _plot_case(
                    notification_axis,
                    case["week"],
                    case["notification_share_pct"],
                    color,
                )
            pooled = panel.notifications.loc[panel.notifications["config"].eq(config)]
            _plot_pooled(
                notification_axis,
                pooled["week"],
                pooled["notification_share_pct"],
                color,
                SYS_LABELS[config],
            )
            notification_axis.plot(
                pooled["week"],
                pooled["unknown_share_pct"],
                color=color,
                linestyle="--",
                linewidth=1.2,
                label=f"{SYS_LABELS[config]}, unknown",
            )

        error_axis.set_title(panel.title, loc="left")
        notification_axis.set_xticks(weeks)
        notification_axis.set_xticklabels(
            [
                f"{week}\nn={cases}"
                for week, cases in zip(weeks, panel.forecast["cases"])
            ]
        )
        notification_axis.set_xlabel("Woche ab Reset (n = Fälle)")
        notification_axis.set_ylim(-2, 102)
        if column == 0:
            error_axis.set_ylabel("Tagesfehler [W]")
            delta_axis.set_ylabel(f"Differenz {llm} − {reference} [W]")
            notification_axis.set_ylabel("Tage mit Meldung [%]")
            error_axis.legend(fontsize=8)
            notification_axis.legend(fontsize=7)
        for axis in (error_axis, delta_axis, notification_axis):
            axis.grid(axis="y", alpha=0.25)

    save_figure(figure, output_directory, name)
