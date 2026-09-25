from dataclasses import dataclass

import pandas as pd

from experiments.common.evaluation import (
    add_overall_rows,
    days_since_date,
    spread_over_repeats,
)

ALL_STARTS = "alle"


def add_days_since_start(origin_metrics: pd.DataFrame) -> pd.DataFrame:
    return origin_metrics.assign(
        day_since_start=days_since_date(
            origin_metrics["forecast_origin"], origin_metrics["start_date"]
        )
    )


def build_learning_curve(daily: pd.DataFrame, *, smoothing_days: int) -> pd.DataFrame:
    keys = ["start_date", "coldstart_days", "model_id"]
    # "alle" mittelt jeden Tag über die Starttermine, die einzelnen Termine bleiben zum Vergleich der Streuung drin
    curve = (
        add_overall_rows(daily, "start_date", ALL_STARTS)
        .groupby(keys + ["day_since_start"], as_index=False)[["mae_w", "mape_pct"]]
        .mean()
    )
    # nur rückwärts mitteln, damit der Break-even-Tag keine Information aus späteren Tagen enthält
    curve["mae_w_smoothed"] = curve.groupby(keys)["mae_w"].transform(
        lambda mae: mae.rolling(smoothing_days, min_periods=1).mean()
    )

    return curve


def find_break_even_days(
    curve: pd.DataFrame, *, variant_id: str, reference_model_id: str
) -> pd.DataFrame:
    keys = ["start_date", "coldstart_days", "day_since_start"]
    variant = curve.loc[curve["model_id"].eq(variant_id), keys + ["mae_w_smoothed"]]
    reference = curve.loc[
        curve["model_id"].eq(reference_model_id), keys + ["mae_w_smoothed"]
    ]
    paired = variant.merge(reference, on=keys, suffixes=("", "_reference"))

    ahead = paired.loc[paired["mae_w_smoothed"] < paired["mae_w_smoothed_reference"]]
    break_even = (
        ahead.groupby(["start_date", "coldstart_days"])["day_since_start"]
        .min()
        .rename("break_even_day")
    )

    # NaN = im ganzen Auswertungszeitraum nie besser als die Baseline
    return (
        paired[["start_date", "coldstart_days"]]
        .drop_duplicates()
        .merge(break_even.reset_index(), how="left")
        .reset_index(drop=True)
    )


def summarize_windows(
    daily: pd.DataFrame,
    *,
    variant_id: str,
    reference_model_id: str,
    window_edges_days: tuple[int, ...],
) -> pd.DataFrame:
    lower_edges = (0,) + window_edges_days[:-1]
    labels = [
        f"{lower}-{upper - 1}" for lower, upper in zip(lower_edges, window_edges_days)
    ]

    windowed = add_overall_rows(daily, "start_date", ALL_STARTS)
    windowed["window"] = pd.cut(
        windowed["day_since_start"],
        bins=[0] + list(window_edges_days),
        right=False,
        labels=labels,
    )

    keys = ["start_date", "coldstart_days", "window"]
    metrics = (
        windowed.groupby(keys + ["model_id"], observed=True)
        .agg(
            mae_w=("mae_w", "mean"),
            mape_pct=("mape_pct", "mean"),
            origins=("mae_w", "count"),
        )
        .reset_index()
    )

    variant = metrics.loc[metrics["model_id"].eq(variant_id)].drop(columns="model_id")
    reference = metrics.loc[
        metrics["model_id"].eq(reference_model_id), keys + ["mae_w"]
    ]
    summary = variant.merge(reference, on=keys, suffixes=("", "_reference"))
    summary["mae_skill"] = 1 - summary["mae_w"] / summary["mae_w_reference"]

    # wie viel ein kürzerer Kaltstart im selben Fenster gegenüber dem längsten verliert
    steady_state = summary.loc[
        summary["coldstart_days"].eq(summary["coldstart_days"].max()),
        ["start_date", "window", "mae_w"],
    ]
    summary = summary.merge(
        steady_state, on=["start_date", "window"], suffixes=("", "_steady_state")
    )
    summary["mae_gap_to_steady_state_w"] = (
        summary["mae_w"] - summary["mae_w_steady_state"]
    )

    return (
        summary.drop(columns="mae_w_steady_state")
        .sort_values(keys)
        .reset_index(drop=True)
    )


@dataclass(frozen=True)
class ColdStartSummary:
    curve: pd.DataFrame
    overall: pd.DataFrame
    gap: pd.DataFrame
    break_even: pd.DataFrame
    # Zahlen für die Kennzahlen, alle zum kürzesten Kaltstart
    shortest: int
    mae_shortest_w: float
    mae_longest_w: float
    reference_mae_shortest_w: float
    first_window: str
    first_window_gap_w: float
    first_window_same_direction: str
    # NaN = beim kürzesten Kaltstart an keinem Starttermin unter der Referenz
    latest_break_even_day: float


def summarize_cold_start(
    origin_metrics: pd.DataFrame,
    *,
    variant_id: str,
    reference_model_id: str,
    smoothing_days: int,
    evaluation_days: int,
    window_edges_days: tuple[int, ...],
) -> ColdStartSummary:
    """Lernkurve, Gesamtfehler, Abstand zum längsten Kaltstart, Break-even und die Zahlen für die Kennzahlen"""
    daily = add_days_since_start(origin_metrics)
    curve = build_learning_curve(daily, smoothing_days=smoothing_days)

    break_even = find_break_even_days(
        curve, variant_id=variant_id, reference_model_id=reference_model_id
    )
    break_even = break_even.loc[break_even["start_date"].ne(ALL_STARTS)]
    break_even_table = spread_over_repeats(
        break_even, ["coldstart_days"], "break_even_day", repeat="start_date"
    )
    start_dates = sorted(break_even["start_date"].unique())
    break_even_table[start_dates] = break_even_table[start_dates].astype("Int64")

    # ein einziges Fenster über alle Auswertungstage ergibt die Gesamtzahlen
    overall = summarize_windows(
        daily,
        variant_id=variant_id,
        reference_model_id=reference_model_id,
        window_edges_days=(evaluation_days,),
    )
    overall = overall.loc[overall["start_date"].eq(ALL_STARTS)].reset_index(drop=True)
    overall["mae_skill_pct"] = overall["mae_skill"] * 100

    # der längste Kaltstart ist die Referenz, sein Abstand zu sich selbst ist immer 0
    windows = summarize_windows(
        daily,
        variant_id=variant_id,
        reference_model_id=reference_model_id,
        window_edges_days=window_edges_days,
    )
    shorter = windows.loc[
        windows["start_date"].ne(ALL_STARTS)
        & windows["coldstart_days"].lt(windows["coldstart_days"].max())
    ]
    gap = spread_over_repeats(
        shorter,
        ["coldstart_days", "window"],
        "mae_gap_to_steady_state_w",
        repeat="start_date",
        count_same_direction=True,
    )

    by_coldstart = overall.set_index("coldstart_days")
    shortest, longest = by_coldstart.index.min(), by_coldstart.index.max()
    shortest_row, longest_row = by_coldstart.loc[shortest], by_coldstart.loc[longest]
    first_window = gap.loc[gap["coldstart_days"].eq(shortest)].iloc[0]

    return ColdStartSummary(
        curve=curve,
        overall=overall,
        gap=gap,
        break_even=break_even_table,
        shortest=shortest,
        mae_shortest_w=shortest_row["mae_w"],
        mae_longest_w=longest_row["mae_w"],
        reference_mae_shortest_w=shortest_row["mae_w_reference"],
        first_window=first_window["window"],
        first_window_gap_w=first_window["mean"],
        first_window_same_direction=first_window["same_direction"],
        latest_break_even_day=break_even.loc[
            break_even["coldstart_days"].eq(shortest), "break_even_day"
        ].max(),
    )
