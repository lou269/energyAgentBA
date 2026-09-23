import pandas as pd

from src.common.timestamps import local_day_index

ALL_STARTS = "alle"


def assign_days_since_start(origin_metrics: pd.DataFrame, local_timezone: str) -> pd.DataFrame:
    origin = pd.DatetimeIndex(pd.to_datetime(origin_metrics["forecast_origin"], utc=True))
    origin_day = local_day_index(origin, local_timezone).tz_localize(None)
    start_day = pd.DatetimeIndex(pd.to_datetime(origin_metrics["start_date"]))

    return origin_metrics.assign(day_since_start=(origin_day - start_day).days)


def _with_all_starts(daily: pd.DataFrame) -> pd.DataFrame:
    # "alle" mittelt jeden Tag über die Starttermine, die einzelnen Termine bleiben zum Vergleich der Streuung drin
    return pd.concat([daily, daily.assign(start_date=ALL_STARTS)], ignore_index=True)


def build_learning_curve(daily: pd.DataFrame, *, smoothing_days: int) -> pd.DataFrame:
    keys = ["start_date", "coldstart_days", "model_id"]
    curve = (
        _with_all_starts(daily)
        .groupby([*keys, "day_since_start"], as_index=False)[["mae_w", "mape_pct"]]
        .mean()
    )
    # nur rückwärts mitteln, damit der Break-even-Tag keine Information aus späteren Tagen enthält
    curve["mae_w_smoothed"] = curve.groupby(keys)["mae_w"].transform(
        lambda mae: mae.rolling(smoothing_days, min_periods=1).mean()
    )

    return curve


def find_break_even_days(curve: pd.DataFrame, *, variant_id: str, reference_model_id: str) -> pd.DataFrame:
    keys = ["start_date", "coldstart_days", "day_since_start"]
    variant = curve.loc[curve["model_id"].eq(variant_id), [*keys, "mae_w_smoothed"]]
    reference = curve.loc[curve["model_id"].eq(reference_model_id), [*keys, "mae_w_smoothed"]]
    paired = variant.merge(reference, on=keys, suffixes=("", "_reference"))

    ahead = paired.loc[paired["mae_w_smoothed"] < paired["mae_w_smoothed_reference"]]
    break_even = ahead.groupby(["start_date", "coldstart_days"])["day_since_start"].min().rename("break_even_day")

    # NaN = im ganzen Auswertungszeitraum nie besser als die Baseline
    return (
        paired[["start_date", "coldstart_days"]].drop_duplicates()
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
    lower_edges = (0, *window_edges_days[:-1])
    labels = [f"{lower}-{upper - 1}" for lower, upper in zip(lower_edges, window_edges_days)]

    windowed = _with_all_starts(daily)
    windowed["window"] = pd.cut(windowed["day_since_start"], bins=[0, *window_edges_days], right=False, labels=labels)

    keys = ["start_date", "coldstart_days", "window"]
    metrics = windowed.groupby([*keys, "model_id"], observed=True).agg(
        mae_w=("mae_w", "mean"), mape_pct=("mape_pct", "mean"), origins=("mae_w", "count"),
    ).reset_index()

    variant = metrics.loc[metrics["model_id"].eq(variant_id)].drop(columns="model_id")
    reference = metrics.loc[metrics["model_id"].eq(reference_model_id), [*keys, "mae_w"]]
    summary = variant.merge(reference, on=keys, suffixes=("", "_reference"))
    summary["mae_skill"] = 1 - summary["mae_w"] / summary["mae_w_reference"]

    # wie viel ein kürzerer Kaltstart im selben Fenster gegenüber dem längsten verliert
    steady_state = summary.loc[summary["coldstart_days"].eq(summary["coldstart_days"].max()), ["start_date", "window", "mae_w"]]
    summary = summary.merge(steady_state, on=["start_date", "window"], suffixes=("", "_steady_state"))
    summary["mae_gap_to_steady_state_w"] = summary["mae_w"] - summary["mae_w_steady_state"]

    return summary.drop(columns="mae_w_steady_state").sort_values(keys).reset_index(drop=True)