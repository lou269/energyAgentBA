from dataclasses import dataclass

import pandas as pd

from experiments.common.evaluation import (
    EVENT_KEYS,
    FIRST_ANALYZED_DAY,
    add_days_since_cutover,
    pair_with_control,
    summarize_event_response,
)
from experiments.common.standard_config import (
    EXPECTED_DETECTION,
    GOLDSTANDARD_EXPECTED,
)

from experiments.e1_seasonality.e1_config import DETECTION_SIGNAL

DETECTION_RESULT_COLUMNS = [
    "config",
    "kind",
    "cutover_date",
    "decision_time",
    "dominant_scale",
    "alarm",
    "sustained_drift",
]

PAIR_KEYS = ["config", "cutover_date", "days_since_cutover"]
SIGNAL_FLAGS = ("alarm", "sustained_drift")


SILENT = "silent"
SUSTAINED_SCALES = "weekly + long_term"
ONSET_COLUMNS = {
    "weekly_sustained": "first_weekly_day",
    "long_term_sustained": "first_long_term_day",
    "sustained_drift": "first_both_day",
}


@dataclass(frozen=True)
class DetectionSummary:
    cases: pd.DataFrame
    overview: pd.DataFrame
    criteria: pd.DataFrame
    sustained_mean_day: float


def summarize_criteria(cases: pd.DataFrame) -> pd.DataFrame:
    built_in = cases.loc[cases["expected"].ne(SILENT) & cases["evaluable"]]
    slow = cases.loc[cases["expected"].eq(SILENT)]
    rows = []
    for criterion, group in (("built_in", built_in), ("slow_ramps", slow)):
        detected = int(group["first_event_day"].notna().sum())
        share = 100 * detected / len(group) if len(group) else float("nan")
        fulfilled = share >= 90 if criterion == "built_in" else detected == 0
        rows.append((criterion, detected, len(group), share, fulfilled))

    return pd.DataFrame(
        rows, columns=["criterion", "detected", "cases", "share_pct", "fulfilled"]
    )


def summarize_detection(results: pd.DataFrame) -> DetectionSummary:
    """Erkennung je System, Cutover und Art (cases) und je System und Art über die Cutover (overview)"""
    days = add_days_since_cutover(
        results.assign(sustained_drift=results["sustained_drift"].eq(True))
    )
    paired = pair_with_control(days, PAIR_KEYS, SIGNAL_FLAGS)

    uses_alarm = paired["kind"].map(DETECTION_SIGNAL).eq("alarm")
    in_window = ~uses_alarm | paired["days_since_cutover"].eq(FIRST_ANALYZED_DAY)
    paired = paired.assign(
        uses_alarm=uses_alarm,
        event_signal=paired["event_alarm"].where(
            uses_alarm, paired["event_sustained_drift"]
        )
        & in_window,
        control_signal=paired["alarm_control"].where(
            uses_alarm, paired["sustained_drift_control"]
        )
        & in_window,
    )
    after_cutover = paired.loc[paired["days_since_cutover"].ge(FIRST_ANALYZED_DAY)]

    control_days = after_cutover.groupby(EVENT_KEYS, as_index=False).agg(
        control_signal_days=("control_signal", "sum")
    )
    first_spike = (
        after_cutover.loc[after_cutover["event_signal"] & after_cutover["uses_alarm"]]
        .sort_values("days_since_cutover")
        .groupby(EVENT_KEYS)
        .head(1)
        .rename(columns={"dominant_scale": "trigger_scale"})
    )

    cases = (
        summarize_event_response(paired, EVENT_KEYS, "event_signal")
        .merge(control_days)
        .merge(first_spike[EVENT_KEYS + ["trigger_scale"]], how="left")
    )
    cases.insert(
        3,
        "expected",
        cases["kind"].map(GOLDSTANDARD_EXPECTED).map(EXPECTED_DETECTION),
    )
    uses_alarm_kind = cases["kind"].map(DETECTION_SIGNAL).eq("alarm")
    cases["evaluable"] = ~(uses_alarm_kind & cases["control_signal_days"].gt(0))
    cases["detecting_scales"] = cases["trigger_scale"].where(
        uses_alarm_kind | cases["first_event_day"].isna(), SUSTAINED_SCALES
    )

    overview = cases.groupby(
        ["config", "kind", "expected"], as_index=False, sort=False
    ).agg(
        cases=("kind", "size"),
        detected=("first_event_day", "count"),
        evaluable_cases=("evaluable", "sum"),
        detected_evaluable=(
            "first_event_day",
            lambda days: days[cases.loc[days.index, "evaluable"]].count(),
        ),
        mean_day=("first_event_day", "mean"),
        first_day=("first_event_day", "min"),
        last_day=("first_event_day", "max"),
        control_days_min=("control_signal_days", "min"),
        control_days_max=("control_signal_days", "max"),
        trigger_scale=(
            "trigger_scale",
            lambda scales: ", ".join(sorted(scales.dropna().unique())) or pd.NA,
        ),
        detecting_scales=(
            "detecting_scales",
            lambda scales: ", ".join(sorted(scales.dropna().unique())) or pd.NA,
        ),
    )
    day_columns = ["first_day", "last_day"]
    # eine Spitze zählt nur an Tag 1, Mittel und Spanne sagen dort nichts
    overview.loc[
        overview["kind"].map(DETECTION_SIGNAL).eq("alarm"), day_columns + ["mean_day"]
    ] = float("nan")
    overview[day_columns] = overview[day_columns].astype("Int64")
    sustained = cases.loc[cases["expected"].eq("reset"), "first_event_day"]

    return DetectionSummary(
        cases=cases.assign(first_event_day=cases["first_event_day"].astype("Int64")),
        overview=overview,
        criteria=summarize_criteria(cases),
        sustained_mean_day=float(sustained.mean()),
    )


def summarize_scale_onsets(anomaly: pd.DataFrame) -> pd.DataFrame:
    days = add_days_since_cutover(anomaly)
    days = days.loc[days["days_since_cutover"].ge(FIRST_ANALYZED_DAY)].sort_values(
        ["kind", "cutover_date", "days_since_cutover"]
    )
    rows = []
    for (kind, cutover_date), case in days.groupby(
        ["kind", "cutover_date"], sort=False
    ):
        onsets = {
            column: case.loc[case[flag].eq(True), "days_since_cutover"].min()
            for flag, column in ONSET_COLUMNS.items()
        }
        first_both = onsets["first_both_day"]
        before = case
        if not pd.isna(first_both):
            before = case.loc[case["days_since_cutover"].lt(first_both)]
        weekly = before["weekly_sustained"].eq(True)
        ended = weekly.shift(fill_value=False) & weekly.eq(False)
        rows.append(
            {"kind": kind, "cutover_date": cutover_date}
            | onsets
            | {"weekly_breaks": int(ended.sum())}
        )

    return pd.DataFrame(rows).astype(
        {column: "Int64" for column in ONSET_COLUMNS.values()}
    )
