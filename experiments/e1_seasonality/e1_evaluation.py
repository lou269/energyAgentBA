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


@dataclass(frozen=True)
class DetectionSummary:
    cases: pd.DataFrame
    overview: pd.DataFrame


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

    overview = cases.groupby(
        ["config", "kind", "expected"], as_index=False, sort=False
    ).agg(
        cases=("kind", "size"),
        detected=("first_event_day", "count"),
        mean_day=("first_event_day", "mean"),
        first_day=("first_event_day", "min"),
        last_day=("first_event_day", "max"),
        control_days_min=("control_signal_days", "min"),
        control_days_max=("control_signal_days", "max"),
        trigger_scale=(
            "trigger_scale",
            lambda scales: ", ".join(sorted(scales.dropna().unique())) or pd.NA,
        ),
    )
    day_columns = ["first_day", "last_day"]
    # eine Spitze zählt nur an Tag 1, Mittel und Spanne sagen dort nichts
    overview.loc[
        overview["kind"].map(DETECTION_SIGNAL).eq("alarm"), day_columns + ["mean_day"]
    ] = float("nan")
    overview[day_columns] = overview[day_columns].astype("Int64")

    return DetectionSummary(
        cases=cases.assign(first_event_day=cases["first_event_day"].astype("Int64")),
        overview=overview,
    )
