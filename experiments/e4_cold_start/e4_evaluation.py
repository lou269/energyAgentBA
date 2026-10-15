from dataclasses import dataclass

import pandas as pd

from experiments.common.evaluation import (
    FIRST_ANALYZED_DAY,
    SCALE_VALUE_COLUMNS,
    SCALE_SUSTAINED_COLUMNS,
    add_weeks,
    days_since_date,
    merge_cycle_days,
    streak_scale_names,
    summarize_forecast_errors,
    summarize_paired_differences,
)
from experiments.common.standard_config import (
    GOLDSTANDARD_EXPECTED,
    LOCAL_TIMEZONE,
    NOTIFICATION_CLASSIFICATIONS,
)
from experiments.e4_cold_start.e4_config import CLEAN_SCENARIO
from src.common.timestamps import local_daily_mean
from src.forecasting.evaluation import score_daily_means
from src.structured_state.structured_state_schema import SCALE_NAMES

# neben den vier Skalen: alle vier zusammen (Einschwingzeit)
ALL_SCALES = "all"
WEEKDAY_SCALE = "weekday"
RESET_CLASSIFICATION = "new_pattern"

# Einschwingwoche je Größe, Schlüssel in summarize_settling
SETTLING_MEASURES = ("forecast", "notifications", "detection")

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
        "day_error_w",
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


def find_settling_day(
    deviations: pd.DataFrame,
    *,
    group_columns: list[str],
    point_column: str,
    deviation_column: str,
    points: tuple[int, ...],
) -> pd.Series:
    """Erster Punkt je Gruppe, ab dem es bis zum Ende keine Abweichung mehr gibt. Weicht der letzte Punkt ab: NaN"""
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


def add_day_errors(
    origin_metrics: pd.DataFrame, forecasts: pd.DataFrame, target_series: pd.Series
) -> pd.DataFrame:
    """Tagesfehler je Modell und Prognosetag neben MAE und MAPE aus dem Walk-Forward, wie day_error_w im Harness"""
    # Horizont ein Tag, jede Prognose startet auf der lokalen Mitternacht ihres Tages
    days = score_daily_means(
        forecasts,
        local_daily_mean(target_series, LOCAL_TIMEZONE).tz_convert("UTC"),
        group_column="model_id",
        day_column="forecast_origin",
    )

    return origin_metrics.merge(
        days[["model_id", "forecast_origin", "day_error_w"]],
        on=["model_id", "forecast_origin"],
        how="left",
    )


@dataclass(frozen=True)
class ForecastSummary:
    # Tagesfehler von adaptiv, statisch und Baseline, adaptiv minus statisch bzw. Baseline und MAPE adaptiv, je Kaltstart-Länge über alle Termine und Tage
    overall: pd.DataFrame
    # Differenzen und Abstand zum langen Kaltstart je Woche, eine Spalte je Größe und Kaltstart-Länge
    weeks: pd.DataFrame
    # Tagesfehler adaptiv: kurzer minus langer Kaltstart je Woche und insgesamt, gepaart über Termin und Tag
    gap: pd.DataFrame
    gap_total: pd.DataFrame
    # geglätteter Tagesfehler je Tag seit Start, nur für den Plot
    curve: pd.DataFrame
    gap_curve: pd.DataFrame


def summarize_forecast(
    forecast_days: pd.DataFrame,
    *,
    adaptive_model_id: str,
    static_model_id: str,
    reference_model_id: str,
    week_days: int,
    smoothing_days: int,
) -> ForecastSummary:
    days = add_weeks(forecast_days, week_days)
    longest = days["coldstart_days"].max()
    by_day = ["start_date", "day_since_start"]
    adaptive_days = days.loc[days["model_id"].eq(adaptive_model_id)]

    gap = pd.concat(
        [
            summarize_paired_differences(
                week_days_frame.pivot(
                    index=by_day, columns="coldstart_days", values="day_error_w"
                ),
                longest,
            ).assign(week=week)
            for week, week_days_frame in adaptive_days.groupby("week")
        ],
        ignore_index=True,
    ).rename(columns={"variant": "coldstart_days"})
    gap_total = summarize_paired_differences(
        adaptive_days.pivot(
            index=by_day, columns="coldstart_days", values="day_error_w"
        ),
        longest,
    ).rename(columns={"variant": "coldstart_days"})
    gap_by_week = gap.pivot(index="week", columns="coldstart_days", values="mean_delta")
    gap_by_week.columns = [f"gap_{coldstart}" for coldstart in gap_by_week.columns]

    paired = days.rename(
        columns={"model_id": "config", "forecast_origin": "decision_time"}
    )

    def against(reference_id: str, keys: list[str]) -> pd.DataFrame:
        table = summarize_forecast_errors(
            paired, keys, reference_id, pair_keys=("start_date", "decision_time")
        )
        return table.loc[table["config"].eq(adaptive_model_id)].set_index(keys)

    overall_keys = ["coldstart_days"]
    week_keys = ["coldstart_days", "week"]
    overall = (
        against(static_model_id, overall_keys)[
            [
                "mean_day_error_w",
                "mean_mape_pct",
                "mean_delta",
                "delta_standard_error",
                "exceeds_noise",
            ]
        ]
        .rename(
            columns={
                "mean_day_error_w": "adaptive",
                "mean_mape_pct": "mape_pct",
                "mean_delta": "minus_static",
                "delta_standard_error": "minus_static_standard_error",
                "exceeds_noise": "minus_static_reliable",
            }
        )
        .join(
            against(reference_model_id, overall_keys)["mean_delta"].rename(
                "minus_reference"
            )
        )
    )
    weeks = (
        against(static_model_id, week_keys)["mean_delta"]
        .unstack("coldstart_days")
        .add_prefix("minus_static_")
        .join(
            against(reference_model_id, week_keys)["mean_delta"]
            .unstack("coldstart_days")
            .add_prefix("minus_reference_")
        )
        .join(gap_by_week)
    )

    curve = (
        days.groupby(["coldstart_days", "day_since_start", "model_id"])["day_error_w"]
        .mean()
        .unstack("model_id")
        .rename(
            columns={
                adaptive_model_id: "adaptive",
                static_model_id: "static",
                reference_model_id: "reference",
            }
        )
    )
    curve = (
        curve.groupby(level="coldstart_days")
        .transform(lambda errors: errors.rolling(smoothing_days, min_periods=1).mean())
        .reset_index()
    )

    adaptive_curve = curve.pivot(
        index="day_since_start", columns="coldstart_days", values="adaptive"
    )
    gap_curve = (
        (adaptive_curve[adaptive_curve.columns.min()] - adaptive_curve[longest])
        .rename("delta")
        .reset_index()
    )

    return ForecastSummary(
        overall=overall.reset_index(),
        weeks=weeks.reset_index(),
        gap=gap,
        gap_total=gap_total,
        curve=curve,
        gap_curve=gap_curve,
    )


# E4b Kreislauf


def summarize_scale_days(clean: pd.DataFrame) -> pd.DataFrame:
    available = clean[SCALE_VALUE_COLUMNS].notna()
    available.columns = list(SCALE_NAMES)
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


def compare_clean_notifications(
    clean: pd.DataFrame, *, shortest: int, longest: int, week_days: int
) -> pd.DataFrame:
    """Je sauberem Tag, ob nur der kurze bzw. nur der lange Kaltstart meldet. Gemeldet heißt eine Klasse, die den Nutzer erreicht, low und unknown nicht"""
    notified = (
        clean.assign(
            notified=clean["classification"].isin(NOTIFICATION_CLASSIFICATIONS)
        )
        .pivot(
            index=["start_date", "day_since_start"],
            columns="coldstart_days",
            values="notified",
        )
        .astype(bool)
    )
    paired = pd.DataFrame(
        {
            "only_shortest": notified[shortest] & ~notified[longest],
            "only_longest": ~notified[shortest] & notified[longest],
        }
    ).reset_index()

    return add_weeks(paired, week_days)


def find_extra_resets(
    days: pd.DataFrame, *, shortest: int, longest: int, week_days: int
) -> pd.DataFrame:
    """Je Lauf der erste Tag mit new_pattern beim kurzen Kaltstart, an dem der lange keins hat, dazu die Skalen, die bei dem kurzen anhalten"""
    run_keys = ["start_date", "scenario", "injection_day"]
    flags = days.assign(reset=days["classification"].eq(RESET_CLASSIFICATION))
    keys = run_keys + ["day_since_start"]
    paired = flags.loc[
        flags["coldstart_days"].eq(shortest),
        keys + ["reset"] + SCALE_SUSTAINED_COLUMNS,
    ].merge(
        flags.loc[flags["coldstart_days"].eq(longest), keys + ["reset"]],
        on=keys,
        suffixes=("", "_longest"),
    )
    extra = paired.loc[paired["reset"] & ~paired["reset_longest"]]
    first_days = (
        extra.sort_values("day_since_start")
        .groupby(run_keys, dropna=False)
        .head(1)
        .reset_index(drop=True)
    )
    first_days["trigger_scale"] = streak_scale_names(first_days)

    return add_weeks(first_days[keys + ["trigger_scale"]], week_days)


def judge_injections(days: pd.DataFrame) -> pd.DataFrame:
    """Je Injektion die Klasse am Tag nach dem Injektionstag. Erkannt heißt die erwartete Klasse, nicht erst irgendwann später"""
    injected = days.loc[
        days["scenario"].ne(CLEAN_SCENARIO)
        & days["day_since_start"].eq(days["injection_day"] + FIRST_ANALYZED_DAY)
    ].astype({"injection_day": int})
    injected = injected.assign(expected=injected["scenario"].map(GOLDSTANDARD_EXPECTED))
    injected["detected"] = injected["classification"].eq(injected["expected"])

    return injected[
        [
            "start_date",
            "coldstart_days",
            "scenario",
            "injection_day",
            "expected",
            "classification",
            "detected",
        ]
    ].reset_index(drop=True)


def pair_injections(
    injections: pd.DataFrame, *, shortest: int, longest: int, week_days: int
) -> pd.DataFrame:
    detected = injections.pivot(
        index=["start_date", "scenario", "injection_day"],
        columns="coldstart_days",
        values="detected",
    )
    pairs = pd.DataFrame(
        {
            "detected_shortest": detected[shortest],
            "detected_longest": detected[longest],
        }
    ).reset_index()
    pairs["missed"] = pairs["detected_longest"] & ~pairs["detected_shortest"]
    # Woche des Entscheidungstags, an dem die Injektion eingeordnet wird
    pairs["week"] = (pairs["injection_day"] + FIRST_ANALYZED_DAY) // week_days + 1

    return pairs


def build_injection_matrix(injections: pd.DataFrame) -> pd.DataFrame:
    matrix = injections.pivot(
        index=["scenario", "injection_day"],
        columns=["start_date", "coldstart_days"],
        values="detected",
    )
    matrix.columns = [f"{start}_{days}" for start, days in matrix.columns]

    return matrix.reset_index()


@dataclass(frozen=True)
class SystemSummary:
    # erster Tag je Skala und alle vier, saubere Läufe
    scale_days: pd.DataFrame
    # je sauberem Tag: nur beim kurzen bzw. nur beim langen Kaltstart gemeldet
    notifications: pd.DataFrame
    # Läufe mit new_pattern nur beim kurzen Kaltstart, und wie viele Läufe der kurze insgesamt hat
    extra_resets: pd.DataFrame
    runs: int
    # eine Zeile je Injektion und Kaltstart-Länge, dazu der Vergleich kurz gegen lang
    injections: pd.DataFrame
    injection_pairs: pd.DataFrame
    # Art und Injektionstag gegen Starttermin und Kaltstart-Länge ("Termin_Länge"), erkannt ja/nein
    injection_matrix: pd.DataFrame


def summarize_system(system_days: pd.DataFrame, *, week_days: int) -> SystemSummary:
    shortest = system_days["coldstart_days"].min()
    longest = system_days["coldstart_days"].max()
    clean = system_days.loc[system_days["scenario"].eq(CLEAN_SCENARIO)]
    injections = judge_injections(system_days)
    short_runs = system_days.loc[system_days["coldstart_days"].eq(shortest)]

    return SystemSummary(
        scale_days=summarize_scale_days(clean),
        notifications=compare_clean_notifications(
            clean, shortest=shortest, longest=longest, week_days=week_days
        ),
        extra_resets=find_extra_resets(
            system_days, shortest=shortest, longest=longest, week_days=week_days
        ),
        runs=short_runs.groupby(
            ["start_date", "scenario", "injection_day"], dropna=False
        ).ngroups,
        injections=injections,
        injection_pairs=pair_injections(
            injections, shortest=shortest, longest=longest, week_days=week_days
        ),
        injection_matrix=build_injection_matrix(injections),
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


# Zusammenfassung


def build_week_table(
    forecast: ForecastSummary, system: SystemSummary, *, shortest: int
) -> pd.DataFrame:
    """Kurzer gegen langen Kaltstart je Woche, zuletzt eine Zeile über alle Wochen (week leer)"""
    gap_columns = ["mean_delta", "delta_standard_error", "exceeds_noise"]
    gap = forecast.gap.loc[forecast.gap["coldstart_days"].eq(shortest)]
    gap_total = forecast.gap_total.loc[
        forecast.gap_total["coldstart_days"].eq(shortest)
    ]

    notifications = system.notifications.groupby("week", as_index=False).agg(
        only_shortest=("only_shortest", "sum"), only_longest=("only_longest", "sum")
    )
    injections = system.injection_pairs.groupby("week", as_index=False).agg(
        injections=("scenario", "size"),
        detected_shortest=("detected_shortest", "sum"),
        detected_longest=("detected_longest", "sum"),
        missed=("missed", "sum"),
    )
    resets = system.extra_resets.groupby("week", as_index=False).agg(
        extra_resets=("start_date", "size")
    )

    weeks = (
        gap[["week"] + gap_columns]
        .merge(notifications, on="week", how="left")
        .merge(injections, on="week", how="left")
        .merge(resets, on="week", how="left")
    )
    weeks["extra_resets"] = weeks["extra_resets"].fillna(0)

    total = weeks.drop(columns=["week"] + gap_columns).sum().to_frame().T
    total[gap_columns] = gap_total[gap_columns].to_numpy()
    total["week"] = pd.NA

    return pd.concat([weeks, total], ignore_index=True).astype({"week": "Int64"})


def summarize_settling(weeks: pd.DataFrame) -> pd.DataFrame:
    """Einschwingwoche je Größe: erste Woche, ab der es keine Abweichung zwischen kurzem und langem Kaltstart mehr gibt. NaN = in der letzten Woche noch abweichend"""
    by_week = weeks.dropna(subset=["week"]).astype({"week": int})
    deviations = pd.DataFrame(
        {
            "week": by_week["week"],
            "group": "all",
            "forecast": by_week["exceeds_noise"].astype(bool),
            "notifications": by_week["only_shortest"] + by_week["only_longest"] > 0,
            "detection": by_week["missed"].fillna(0) > 0,
        }
    )
    points = tuple(by_week["week"])

    return pd.DataFrame(
        {
            "measure": list(SETTLING_MEASURES),
            "settling_week": [
                find_settling_day(
                    deviations,
                    group_columns=["group"],
                    point_column="week",
                    deviation_column=measure,
                    points=points,
                ).iloc[0]
                for measure in SETTLING_MEASURES
            ],
        }
    )


def summarize_totals(forecast: ForecastSummary, system: SystemSummary) -> pd.DataFrame:
    """Kennzahlen über alle Wochen: je Zeile Größe, Kaltstart-Länge, Wert und Bezugsgröße (leer = keine). Meldungen und Resets nur für den kurzen Kaltstart, der lange ist dort die Referenz"""
    shortest = system.scale_days["coldstart_days"].min()
    rows: list[tuple] = []

    for row in forecast.overall.to_dict("records"):
        for measure, column in (
            ("day_error_w", "adaptive"),
            ("minus_static_w", "minus_static"),
            ("minus_reference_w", "minus_reference"),
        ):
            rows.append((measure, row["coldstart_days"], row[column], None))

    clean_days = len(system.notifications)
    rows += [
        (
            "only_shortest",
            shortest,
            system.notifications["only_shortest"].sum(),
            clean_days,
        ),
        (
            "only_longest",
            shortest,
            system.notifications["only_longest"].sum(),
            clean_days,
        ),
        ("extra_resets", shortest, len(system.extra_resets), system.runs),
    ]
    for coldstart_days, injections in system.injections.groupby("coldstart_days"):
        rows.append(
            ("detected", coldstart_days, injections["detected"].sum(), len(injections))
        )

    # object, sonst werden Zählungen zu 16,0
    return pd.DataFrame(
        rows, columns=["measure", "coldstart_days", "value", "total"], dtype=object
    )


def evaluate_criteria(forecast: ForecastSummary, system: SystemSummary) -> pd.DataFrame:
    """Die vier Kriterien der Teilfrage 4 wie in Tabelle 5.5 der Arbeit, kurze Starthistorie gegen lange und gegen das statische Modell"""
    shortest = system.scale_days["coldstart_days"].min()

    gap = forecast.gap.loc[forecast.gap["coldstart_days"].eq(shortest)]
    weeks_worse = int((gap["exceeds_noise"] & gap["mean_delta"].gt(0)).sum())

    pairs = system.injection_pairs
    detected_longest = pairs.loc[pairs["detected_longest"].astype(bool)]
    detected_both = int(detected_longest["detected_shortest"].astype(bool).sum())
    detected_share = 100 * detected_both / len(detected_longest)

    static = forecast.overall.set_index("coldstart_days").loc[shortest]
    minus_static = static["minus_static"]
    static_reliable = bool(static["minus_static_reliable"])

    rows = [
        {
            "check": "weeks_worse_than_longest",
            "fulfilled": weeks_worse == 0,
            "value": weeks_worse,
            "total": len(gap),
        },
        {
            "check": "extra_resets",
            "fulfilled": len(system.extra_resets) == 0,
            "value": len(system.extra_resets),
            "total": system.runs,
        },
        {
            "check": "detected_share",
            "fulfilled": detected_share >= 90,
            "value": detected_both,
            "total": len(detected_longest),
            "share_pct": detected_share,
        },
        {
            "check": "minus_static",
            "fulfilled": static_reliable and minus_static < 0,
            "value": minus_static,
            "two_se": 2 * static["minus_static_standard_error"],
            "reliable": static_reliable,
        },
    ]

    return pd.DataFrame(
        rows,
        columns=[
            "check",
            "fulfilled",
            "value",
            "total",
            "share_pct",
            "two_se",
            "reliable",
        ],
    )


@dataclass(frozen=True)
class E4Summary:
    forecast: ForecastSummary
    system: SystemSummary
    # Prognose im Kreislauf gegen Walk-Forward, sollte gleich sein
    cycle_forecast: pd.DataFrame
    # kurzer gegen langer Kaltstart je Woche und insgesamt
    weeks: pd.DataFrame
    settling: pd.DataFrame
    totals: pd.DataFrame
    criteria: pd.DataFrame
    works: bool


def summarize_e4(
    forecast_metrics: pd.DataFrame,
    system_results: pd.DataFrame,
    *,
    adaptive_model_id: str,
    static_model_id: str,
    reference_model_id: str,
    week_days: int,
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
        week_days=week_days,
        smoothing_days=smoothing_days,
    )
    system = summarize_system(system_days, week_days=week_days)
    shortest = system.scale_days["coldstart_days"].min()
    weeks = build_week_table(forecast, system, shortest=shortest)
    criteria = evaluate_criteria(forecast, system)

    return E4Summary(
        forecast=forecast,
        system=system,
        cycle_forecast=compare_cycle_forecast(
            system_days, forecast_days, adaptive_model_id=adaptive_model_id
        ),
        weeks=weeks,
        settling=summarize_settling(weeks),
        totals=summarize_totals(forecast, system),
        criteria=criteria,
        works=bool(criteria["fulfilled"].all()),
    )
