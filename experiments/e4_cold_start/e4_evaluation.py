from dataclasses import dataclass

import pandas as pd

from experiments.common.evaluation import (
    FIRST_ANALYZED_DAY,
    join_scale_names,
    SCALE_VALUE_COLUMNS,
    SCALE_SUSTAINED_COLUMNS,
    count_notifications,
    days_since_date,
    merge_cycle_days,
    spread_over_repeats,
    summarize_paired_differences,
)
from experiments.common.standard_config import (
    NOTIFICATION_CLASSIFICATIONS,
    NOTIFICATION_PERIOD_DAYS,
)
from experiments.e4_cold_start.e4_config import CLEAN_SCENARIO
from src.structured_state.structured_state_schema import SCALE_NAMES

# neben den vier Skalen: die erste Gate-Skala und alle vier zusammen (Einschwingzeit)
GATE_SCALE = "gate"
ALL_SCALES = "all"

SYSTEM_COLUMNS = (
    [
        "start_date",
        "coldstart_days",
        "scenario",
        "injection_day",
        "decision_time",
        "analyzed_day",
        "classification",
        "reference_reset",
        "gate_open",
        "dominant_scale",
        "explanation",
        "error",
        "mae_w",
        "mape_pct",
    ]
    + SCALE_VALUE_COLUMNS
    + SCALE_SUSTAINED_COLUMNS
)


def read_system_days(
    summary: pd.DataFrame,
    anomaly: pd.DataFrame,
    *,
    start_date: str,
    coldstart_days: int,
    scenario: str,
    injection_day: int | None,
) -> pd.DataFrame:
    """Je Entscheidungstag eines E4b-Laufs Einordnung, Gate, Reset, Skalen und der Prognosefehler im Kreislauf"""
    days = merge_cycle_days(summary, anomaly).assign(
        start_date=start_date,
        coldstart_days=coldstart_days,
        scenario=scenario,
        injection_day=injection_day,
    )

    return days[SYSTEM_COLUMNS]


def add_windows(days: pd.DataFrame, window_edges_days: tuple[int, ...]) -> pd.DataFrame:
    lower_edges = (0,) + window_edges_days[:-1]

    return days.assign(
        window=pd.cut(
            days["day_since_start"],
            bins=[0] + list(window_edges_days),
            right=False,
            labels=[
                f"{lower}-{upper - 1}"
                for lower, upper in zip(lower_edges, window_edges_days)
            ],
        )
    )


def find_settling_day(
    deviations: pd.DataFrame,
    *,
    group_columns: list[str],
    point_column: str,
    deviation_column: str,
    points: tuple[int, ...],
) -> pd.Series:
    next_point = dict(zip(points, points[1:]))
    groups = deviations.groupby(group_columns).size().index
    last_deviation = (
        deviations.loc[deviations[deviation_column]]
        .groupby(group_columns)[point_column]
        .max()
        .reindex(groups)
    )

    return (
        last_deviation.map(next_point)
        .where(last_deviation.notna(), points[0])
        .rename("settling_day")
    )


# E4a Prognose


def summarize_windows(
    windowed: pd.DataFrame, *, reference_model_id: str
) -> pd.DataFrame:
    """MAE und MAPE je Kaltstart-Länge, Fenster und Modell über alle Termine, dazu der Skill gegenüber reference_model_id in %"""
    keys = ["coldstart_days", "window"]
    metrics = windowed.groupby(keys + ["model_id"], observed=True, as_index=False).agg(
        mae_w=("mae_w", "mean"), mape_pct=("mape_pct", "mean")
    )
    reference = metrics.loc[
        metrics["model_id"].eq(reference_model_id), keys + ["mae_w"]
    ]
    metrics = metrics.merge(reference, on=keys, suffixes=("", "_reference"))
    metrics["mae_skill_pct"] = (1 - metrics["mae_w"] / metrics["mae_w_reference"]) * 100

    return metrics


def compare_to_longest_coldstart(prophet: pd.DataFrame) -> pd.DataFrame:
    longest = prophet["coldstart_days"].max()
    summaries = []
    for key in prophet[["window", "model_id"]].drop_duplicates().to_dict("records"):
        days = prophet.loc[
            prophet["window"].eq(key["window"])
            & prophet["model_id"].eq(key["model_id"])
        ]
        mae = days.pivot(
            index=["start_date", "day_since_start"],
            columns="coldstart_days",
            values="mae_w",
        )
        summaries.append(
            summarize_paired_differences(mae, longest).assign(
                window=key["window"], model_id=key["model_id"]
            )
        )

    return (
        pd.concat(summaries, ignore_index=True)
        .rename(columns={"variant": "coldstart_days"})
        .astype({"window": prophet["window"].dtype})
    )


def compare_static_by_start(
    prophet: pd.DataFrame, *, adaptive_model_id: str
) -> pd.DataFrame:
    keys = ["window", "coldstart_days", "start_date"]
    means = prophet.groupby(keys + ["model_id"], observed=True, as_index=False)[
        "mae_w"
    ].mean()
    adaptive = means.loc[means["model_id"].eq(adaptive_model_id), keys + ["mae_w"]]
    differences = means.loc[means["model_id"].ne(adaptive_model_id)].merge(
        adaptive, on=keys, suffixes=("", "_adaptive")
    )
    differences["mae_difference_w"] = (
        differences["mae_w"] - differences["mae_w_adaptive"]
    )

    return spread_over_repeats(
        differences,
        ["window", "coldstart_days", "model_id"],
        "mae_difference_w",
        repeat="start_date",
        count_same_direction=True,
    )


def build_gap_curve(days: pd.DataFrame, *, smoothing_days: int) -> pd.DataFrame:
    keys = ["model_id", "day_since_start"]
    longest = days["coldstart_days"].max()
    means = days.groupby(keys + ["coldstart_days"], as_index=False)["mae_w"].mean()
    longest_means = means.loc[means["coldstart_days"].eq(longest), keys + ["mae_w"]]
    curve = means.loc[means["coldstart_days"].lt(longest)].merge(
        longest_means, on=keys, suffixes=("", "_longest")
    )
    curve["mae_gap_w"] = curve["mae_w"] - curve["mae_w_longest"]
    curve["mae_gap_w_smoothed"] = curve.groupby(["model_id", "coldstart_days"])[
        "mae_gap_w"
    ].transform(lambda gap: gap.rolling(smoothing_days, min_periods=1).mean())

    return curve


@dataclass(frozen=True)
class ForecastSummary:
    # MAE, MAPE und Skill gegenüber der Baseline je Kaltstart-Länge, Fenster und Modell
    windows: pd.DataFrame
    # Abstand zum längsten Kaltstart je Fenster und Modell, gepaart über Termin und Tag
    gap: pd.DataFrame
    # erster Tag, ab dem der Abstand im Rauschen liegt, je Modell und Kaltstart-Länge
    settling: pd.DataFrame
    # statisch minus adaptiv je Fenster und Kaltstart-Länge, je Termin und im Mittel, positiv = adaptiv besser
    static_minus_adaptive: pd.DataFrame
    gap_curve: pd.DataFrame


def summarize_forecast(
    forecast_days: pd.DataFrame,
    *,
    adaptive_model_id: str,
    static_model_id: str,
    reference_model_id: str,
    window_edges_days: tuple[int, ...],
    smoothing_days: int,
) -> ForecastSummary:
    windowed = add_windows(forecast_days, window_edges_days)
    window_starts = (0,) + window_edges_days[:-1]

    prophet = windowed.loc[
        windowed["model_id"].isin([adaptive_model_id, static_model_id])
    ]
    gap = compare_to_longest_coldstart(prophet)

    return ForecastSummary(
        windows=summarize_windows(windowed, reference_model_id=reference_model_id),
        gap=gap,
        settling=find_settling_day(
            gap.assign(
                window_start=gap["window"].cat.codes.map(dict(enumerate(window_starts)))
            ),
            group_columns=["model_id", "coldstart_days"],
            point_column="window_start",
            deviation_column="exceeds_noise",
            points=window_starts,
        ).reset_index(),
        static_minus_adaptive=compare_static_by_start(
            prophet, adaptive_model_id=adaptive_model_id
        ),
        gap_curve=build_gap_curve(
            forecast_days.loc[forecast_days["model_id"].ne(reference_model_id)],
            smoothing_days=smoothing_days,
        ),
    )


# E4b Kreislauf


def summarize_scale_days(
    clean: pd.DataFrame, *, single_day_scales: tuple[str, ...]
) -> pd.DataFrame:
    available = clean[SCALE_VALUE_COLUMNS].notna()
    available.columns = list(SCALE_NAMES)
    available[GATE_SCALE] = available[list(single_day_scales)].any(axis=1)
    available[ALL_SCALES] = available[list(SCALE_NAMES)].all(axis=1)

    by_day = pd.concat(
        [clean[["coldstart_days", "start_date", "day_since_start"]], available], axis=1
    ).melt(
        id_vars=["coldstart_days", "start_date", "day_since_start"],
        var_name="scale",
        value_name="available",
    )
    by_day["scale"] = pd.Categorical(
        by_day["scale"], categories=list(available.columns), ordered=True
    )

    first_days = (
        by_day.loc[by_day["available"]]
        .groupby(["coldstart_days", "scale", "start_date"], observed=True)[
            "day_since_start"
        ]
        .min()
    )
    scale_days = (
        first_days.groupby(["coldstart_days", "scale"], observed=True)
        .agg(starts="size", latest_day="max")
        .reset_index()
    )
    scale_days["latest_history_days"] = (
        scale_days["coldstart_days"] + scale_days["latest_day"]
    )

    return scale_days


def list_resets_in_settling(days: pd.DataFrame) -> pd.DataFrame:
    resets = days.loc[
        days["reference_reset"].eq(True) & days[SCALE_VALUE_COLUMNS].isna().any(axis=1)
    ]

    return resets[
        [
            "start_date",
            "coldstart_days",
            "scenario",
            "injection_day",
            "analyzed_day",
            "day_since_start",
            "classification",
        ]
    ].assign(
        available_scales=join_scale_names(resets[SCALE_VALUE_COLUMNS].notna(), ", "),
        sustained_scales=join_scale_names(
            resets[SCALE_SUSTAINED_COLUMNS].eq(True), ", "
        ),
    )


def compare_clean_gate(
    clean: pd.DataFrame, *, shortest: int, longest: int
) -> pd.DataFrame:
    gate = clean.pivot(
        index=["start_date", "day_since_start"],
        columns="coldstart_days",
        values="gate_open",
    ).eq(True)

    return pd.DataFrame(
        {
            "only_shortest": gate[shortest] & ~gate[longest],
            "only_longest": ~gate[shortest] & gate[longest],
        }
    ).reset_index()


def summarize_gate_deviations(
    gate_days: pd.DataFrame, *, evaluation_days: int
) -> pd.DataFrame:
    by_start = gate_days.groupby("start_date").agg(
        only_shortest=("only_shortest", "sum"), only_longest=("only_longest", "sum")
    )
    by_start["settling_day"] = find_settling_day(
        gate_days.assign(
            deviates=gate_days["only_shortest"] | gate_days["only_longest"]
        ),
        group_columns=["start_date"],
        point_column="day_since_start",
        deviation_column="deviates",
        points=tuple(range(evaluation_days)),
    )

    return by_start.reset_index()


def compare_injections(
    days: pd.DataFrame, *, shortest: int, longest: int
) -> pd.DataFrame:
    injected = days.loc[
        days["scenario"].ne(CLEAN_SCENARIO)
        & days["day_since_start"].eq(days["injection_day"] + FIRST_ANALYZED_DAY)
    ].astype({"injection_day": int})
    pairs = injected.pivot(
        index=["start_date", "scenario", "injection_day"],
        columns="coldstart_days",
        values=["gate_open", "classification"],
    )

    injections = pd.DataFrame(
        {
            "reference_detected": pairs[("gate_open", longest)].eq(True),
            "detected": pairs[("gate_open", shortest)].eq(True),
            "reference_classification": pairs[("classification", longest)],
            "classification": pairs[("classification", shortest)],
        }
    ).reset_index()

    injections["missed"] = injections["reference_detected"] & ~injections["detected"]
    other_class = (
        injections["reference_detected"]
        & injections["detected"]
        & injections["classification"].ne(injections["reference_classification"])
    )
    injections["class_unknown"] = other_class & injections["classification"].eq(
        "unknown"
    )
    injections["class_other"] = other_class & ~injections["class_unknown"]
    injections["class_deviation"] = other_class

    return injections


def summarize_injection_price(injections: pd.DataFrame) -> pd.DataFrame:
    return injections.groupby("scenario", as_index=False).agg(
        injections=("reference_detected", "size"),
        reference_detected=("reference_detected", "sum"),
        missed=("missed", "sum"),
        class_other=("class_other", "sum"),
        class_unknown=("class_unknown", "sum"),
    )


@dataclass(frozen=True)
class SystemSummary:
    # erster Tag je Skala, Gate-Skala und alle vier, saubere Läufe
    scale_days: pd.DataFrame
    # Resets, solange nicht alle Skalen einen Score haben, alle Läufe
    resets: pd.DataFrame
    # Meldungen und unknown je Fenster, saubere Läufe
    notifications: pd.DataFrame
    # zusätzliche und fehlende Meldetage je Termin mit Einschwingtag Meldungen
    gate_deviations: pd.DataFrame
    # Einschwingtag Erkennung und Einordnung je Termin und Art
    injection_settling: pd.DataFrame
    injection_price: pd.DataFrame
    # nur für den Plot: Abweichungen im Gate je Tag und Ergebnis je Injektionstag, summiert über die Termine
    gate_by_day: pd.DataFrame
    injection_by_day: pd.DataFrame


def summarize_system(
    system_days: pd.DataFrame,
    *,
    single_day_scales: tuple[str, ...],
    injection_days: tuple[int, ...],
    window_edges_days: tuple[int, ...],
) -> SystemSummary:
    shortest = system_days["coldstart_days"].min()
    longest = system_days["coldstart_days"].max()
    clean = system_days.loc[system_days["scenario"].eq(CLEAN_SCENARIO)]

    gate_days = compare_clean_gate(clean, shortest=shortest, longest=longest)
    injections = compare_injections(system_days, shortest=shortest, longest=longest)
    injection_settling = pd.DataFrame(
        {
            f"{name}_settling_day": find_settling_day(
                injections,
                group_columns=["start_date", "scenario"],
                point_column="injection_day",
                deviation_column=deviation_column,
                points=injection_days,
            )
            for name, deviation_column in (
                ("detection", "missed"),
                ("classification", "class_deviation"),
            )
        }
    ).reset_index()

    return SystemSummary(
        scale_days=summarize_scale_days(clean, single_day_scales=single_day_scales),
        resets=list_resets_in_settling(system_days),
        notifications=count_notifications(
            add_windows(clean, window_edges_days),
            ["coldstart_days", "window"],
            notification_classes=NOTIFICATION_CLASSIFICATIONS,
            period_days=NOTIFICATION_PERIOD_DAYS,
        ),
        gate_deviations=summarize_gate_deviations(
            gate_days, evaluation_days=window_edges_days[-1]
        ),
        injection_settling=injection_settling,
        injection_price=summarize_injection_price(injections),
        gate_by_day=gate_days.groupby("day_since_start", as_index=False)[
            ["only_shortest", "only_longest"]
        ].sum(),
        injection_by_day=injections.groupby(
            ["scenario", "injection_day"], as_index=False
        ).agg(
            reference_detected=("reference_detected", "sum"),
            missed=("missed", "sum"),
            class_deviation=("class_deviation", "sum"),
        ),
    )


def compare_cycle_forecast(
    system_days: pd.DataFrame, forecast_days: pd.DataFrame, *, adaptive_model_id: str
) -> pd.DataFrame:
    run_keys = ["start_date", "coldstart_days"]
    clean = system_days.loc[system_days["scenario"].eq(CLEAN_SCENARIO)].sort_values(
        run_keys + ["day_since_start"]
    )
    # ab dem Reset-Tag prognostiziert der Kreislauf schon mit der gekürzten Historie
    before_reset = ~clean.groupby(run_keys)["reference_reset"].cummax().eq(True)
    walk_forward = forecast_days.loc[
        forecast_days["model_id"].eq(adaptive_model_id),
        run_keys + ["day_since_start", "mae_w"],
    ]

    paired = clean.loc[before_reset, run_keys + ["day_since_start", "mae_w"]].merge(
        walk_forward, on=run_keys + ["day_since_start"], suffixes=("", "_walk_forward")
    )
    paired["mae_difference_w"] = (paired["mae_w"] - paired["mae_w_walk_forward"]).abs()

    return paired.groupby("coldstart_days", as_index=False).agg(
        days=("mae_difference_w", "size"),
        max_mae_difference_w=("mae_difference_w", "max"),
    )


def summarize_price(
    forecast: ForecastSummary, system: SystemSummary, *, adaptive_model_id: str
) -> pd.DataFrame:
    shortest = system.scale_days["coldstart_days"].min()
    longest = system.scale_days["coldstart_days"].max()
    first_window = forecast.windows["window"].cat.categories[0]

    adaptive = forecast.windows.loc[forecast.windows["model_id"].eq(adaptive_model_id)]
    longest_mae = adaptive.loc[adaptive["coldstart_days"].eq(longest)].set_index(
        "window"
    )["mae_w"]
    gap = forecast.gap.loc[
        forecast.gap["model_id"].eq(adaptive_model_id)
        & forecast.gap["coldstart_days"].eq(shortest)
    ]
    notifications = system.notifications.loc[
        system.notifications["coldstart_days"].eq(shortest)
    ]
    first_week = notifications.loc[notifications["window"].eq(first_window)].iloc[0]
    clean_days = notifications["days"].sum()

    rows = (
        [
            (
                "mae_gap_w",
                row["window"],
                None,
                row["mean_delta"],
                longest_mae[row["window"]],
            )
            for row in gap.to_dict("records")
        ]
        + [
            (column, None, None, system.gate_deviations[column].sum(), clean_days)
            for column in ("only_shortest", "only_longest")
        ]
        + [
            (
                "unknown",
                first_window,
                None,
                first_week["unknown_days"],
                first_week["days"],
            )
        ]
        + [
            (column, None, row["scenario"], row[column], row["reference_detected"])
            for column in ("missed", "class_other", "class_unknown")
            for row in system.injection_price.to_dict("records")
        ]
    )
    # object, sonst werden Zählungen zu 16,0
    price = pd.DataFrame(
        rows, columns=["price", "window", "scenario", "value", "total"], dtype=object
    )
    price["share_pct"] = (
        price["value"].astype(float) / price["total"].astype(float) * 100
    )

    return price


def evaluate_criteria(
    forecast: ForecastSummary,
    system: SystemSummary,
    *,
    adaptive_model_id: str,
    start_dates: list[str],
    window_edges_days: tuple[int, ...],
) -> pd.DataFrame:
    shortest = system.scale_days["coldstart_days"].min()
    first_window = forecast.windows["window"].cat.categories[0]

    skill = forecast.windows.loc[
        forecast.windows["model_id"].eq(adaptive_model_id)
        & forecast.windows["coldstart_days"].eq(shortest)
        & forecast.windows["window"].eq(first_window),
        "mae_skill_pct",
    ].iloc[0]
    gate_day = system.scale_days.loc[
        system.scale_days["coldstart_days"].eq(shortest)
        & system.scale_days["scale"].eq(GATE_SCALE),
        "latest_day",
    ].iloc[0]
    forecast_settling = forecast.settling.loc[
        forecast.settling["model_id"].eq(adaptive_model_id)
        & forecast.settling["coldstart_days"].eq(shortest),
        "settling_day",
    ].iloc[0]
    resets = system.resets["coldstart_days"].eq(shortest).sum()
    notification = system.gate_deviations["settling_day"]
    detection = system.injection_settling["detection_settling_day"]
    classification = system.injection_settling["classification_settling_day"]

    # ab dem zweiten Fenster soll adaptiv an jedem Termin besser sein als statisch
    by_start = forecast.static_minus_adaptive
    later = by_start.loc[by_start["window"].ne(first_window)]
    static_worse = later[start_dates].gt(0).all(axis=1)

    rows = [
        ("no_malfunction", "resets_in_settling", resets == 0, resets),
        ("usable_from_start", "forecast_skill_first_window_pct", skill > 0, skill),
        (
            "usable_from_start",
            "first_gate_scale_day",
            gate_day < window_edges_days[0],
            gate_day,
        ),
        (
            "adapts",
            "forecast_settling_day",
            pd.notna(forecast_settling),
            forecast_settling,
        ),
        (
            "adapts",
            "notification_settling_day",
            notification.notna().all(),
            notification.max(),
        ),
        ("adapts", "detection_settling_day", detection.notna().all(), detection.max()),
        (
            "adapts",
            "classification_settling_day",
            classification.notna().all(),
            classification.max(),
        ),
        (
            "adaptive_vs_static",
            "static_worse_share",
            static_worse.all(),
            static_worse.mean(),
        ),
    ]

    return pd.DataFrame(rows, columns=["criterion", "check", "fulfilled", "value"])


@dataclass(frozen=True)
class E4Summary:
    forecast: ForecastSummary
    system: SystemSummary
    # Prognose im Kreislauf gegen Walk-Forward, sollte gleich sein
    cycle_forecast: pd.DataFrame
    criteria: pd.DataFrame
    # Preis bis zum Einschwingen, kompakt für ergebnis.md
    price: pd.DataFrame
    # funktioniert mit 7 Tagen: keine Fehlfunktion, von Anfang an nutzbar, passt sich an
    works: bool


def summarize_e4(
    forecast_metrics: pd.DataFrame,
    system_results: pd.DataFrame,
    *,
    adaptive_model_id: str,
    static_model_id: str,
    reference_model_id: str,
    single_day_scales: tuple[str, ...],
    injection_days: tuple[int, ...],
    window_edges_days: tuple[int, ...],
    smoothing_days: int,
) -> E4Summary:
    # Tag 0 = erster prognostizierter Tag, eingeordnet wird an ihm der letzte Tag der Start-Historie
    forecast_days = forecast_metrics.assign(
        day_since_start=days_since_date(
            forecast_metrics["forecast_origin"], forecast_metrics["start_date"]
        )
    )
    system_days = system_results.assign(
        day_since_start=days_since_date(
            system_results["decision_time"], system_results["start_date"]
        )
    )

    forecast = summarize_forecast(
        forecast_days,
        adaptive_model_id=adaptive_model_id,
        static_model_id=static_model_id,
        reference_model_id=reference_model_id,
        window_edges_days=window_edges_days,
        smoothing_days=smoothing_days,
    )
    system = summarize_system(
        system_days,
        single_day_scales=single_day_scales,
        injection_days=injection_days,
        window_edges_days=window_edges_days,
    )
    criteria = evaluate_criteria(
        forecast,
        system,
        adaptive_model_id=adaptive_model_id,
        start_dates=sorted(forecast_days["start_date"].unique()),
        window_edges_days=window_edges_days,
    )

    return E4Summary(
        forecast=forecast,
        system=system,
        cycle_forecast=compare_cycle_forecast(
            system_days, forecast_days, adaptive_model_id=adaptive_model_id
        ),
        criteria=criteria,
        price=summarize_price(forecast, system, adaptive_model_id=adaptive_model_id),
        works=bool(
            criteria.loc[
                criteria["criterion"].isin(
                    ["no_malfunction", "usable_from_start", "adapts"]
                ),
                "fulfilled",
            ].all()
        ),
    )
