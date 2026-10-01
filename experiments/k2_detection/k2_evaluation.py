from dataclasses import dataclass

import pandas as pd

from experiments.common.evaluation import (
    FIRST_ANALYZED_DAY,
    SCALE_VALUE_COLUMNS,
    SCALE_SUSTAINED_COLUMNS,
    detection_scales,
    merge_cycle_days,
    spread_over_repeats,
)
from experiments.k2_detection.k2_config import STREAK_THRESHOLD_COLUMNS

# gepaart wird je Modus, Variante und Cutover Tag für Tag
PAIR_KEYS = ["mode", "variant", "cutover_date", "days_since_cutover"]

RESULT_COLUMNS = (
    [
        "mode",
        "kind",
        "cutover_date",
        "variant",
        "decision_time",
        "analyzed_day",
        "anomaly_level",
        "anomaly_score",
        "dominant_scale",
    ]
    + SCALE_VALUE_COLUMNS
    + SCALE_SUSTAINED_COLUMNS
    + [
        "sustained_drift",
        "classification",
        "alarm",
        "gate_open",
        "new_pattern",
        "reference_reset",
    ]
)


def read_scenario_results(
    summary: pd.DataFrame,
    anomaly: pd.DataFrame,
    *,
    mode: str,
    kind: str,
    cutover_date: str,
) -> pd.DataFrame:
    results = (
        merge_cycle_days(summary, anomaly)
        .rename(columns={"config": "variant"})
        .assign(mode=mode, kind=kind, cutover_date=cutover_date)
    )

    return results[RESULT_COLUMNS]


def summarize_gate_open(results: pd.DataFrame) -> pd.DataFrame:
    """Fehlalarme und Resets ohne Ereignis über das ganze Fenster, erst je Cutover, dann gemittelt"""
    control = results.loc[results["kind"].eq("control")]
    by_cutover = control.groupby(["mode", "variant", "cutover_date"]).agg(
        alarm_rate=("alarm", "mean"),
        gate_open_rate=("gate_open", "mean"),
        resets=("reference_reset", "sum"),
    )
    rates = by_cutover.groupby(["variant", "mode"]).mean().reset_index()

    return rates.assign(
        gate_open_pct=rates["gate_open_rate"] * 100, alarm_pct=rates["alarm_rate"] * 100
    )


def summarize_quiet_days(gate_open: pd.DataFrame) -> pd.DataFrame:
    adaption = gate_open.set_index(["variant", "mode"]).xs("adaption", level="mode")

    return (
        pd.DataFrame(
            {
                "gate_open_adaption_pct": adaption["gate_open_pct"],
                "alarm_adaption_pct": adaption["alarm_pct"],
                "control_resets": adaption["resets"],
            }
        )
        .rename_axis("variant")
        .reset_index()
    )


@dataclass(frozen=True)
class DetectionSummary:
    table: pd.DataFrame
    # falsche Resets je Fenster über alle Ereignisse und Cutover, eine Zeile je Variante
    false_resets: pd.DataFrame


def summarize_detection(
    paired: pd.DataFrame,
    single_day_kinds: tuple[str, ...],
    *,
    control_reset_tolerance_days: int,
    uncounted_cutovers: tuple[str, ...],
) -> DetectionSummary:
    keys = ["variant", "kind"]
    adaption = paired.loc[paired["mode"].eq("adaption")]
    own_reset = adaption["event_new_pattern"] & ~near_control_new_pattern(
        adaption, control_reset_tolerance_days
    )
    after_cutover = adaption.assign(own_reset=own_reset).loc[
        adaption["days_since_cutover"].ge(FIRST_ANALYZED_DAY)
    ]
    single_day = after_cutover["kind"].isin(single_day_kinds)

    hit = after_cutover["own_reset"].where(
        ~single_day,
        after_cutover["event_alarm"]
        & after_cutover["days_since_cutover"].eq(FIRST_ANALYZED_DAY),
    )
    first_hits = (
        after_cutover.loc[hit]
        .sort_values("days_since_cutover")
        .groupby(keys + ["cutover_date"])
        .head(1)
    )
    first_hits = first_hits.assign(
        day=first_hits["days_since_cutover"],
        scales=detection_scales(first_hits, first_hits["kind"].isin(single_day_kinds)),
    )

    days = (
        after_cutover[keys + ["cutover_date"]]
        .drop_duplicates()
        .merge(
            first_hits[keys + ["cutover_date", "day", "scales"]],
            on=keys + ["cutover_date"],
            how="left",
        )
    )
    # die Begründung betrifft nur die Streak-Bedingung, Einzeltag-Spitzen zählen dort mit
    uncounted = days["cutover_date"].isin(uncounted_cutovers) & ~days["kind"].isin(
        single_day_kinds
    )
    counted_days = days.loc[~uncounted]
    # getrennt, sonst stünden die nicht gezählten Cutover bei den Dauerlasten im Nenner von erkannt
    spread = pd.concat(
        [
            spread_over_repeats(group, keys, "day", count_detected=True)
            for _, group in counted_days.groupby(
                counted_days["kind"].isin(single_day_kinds)
            )
        ]
    )
    wide = (
        days.pivot(index=keys, columns="cutover_date", values="day")
        .rename_axis(columns=None)
        .reset_index()
    )

    scales = counted_days.groupby(keys, as_index=False).agg(
        scales=("scales", lambda scales: ", ".join(sorted(scales.dropna().unique())))
    )
    # über alle Cutover, auch die nicht gezählten, gerade dort tritt es auf
    resets = after_cutover.groupby(keys + ["cutover_date"], as_index=False).agg(
        own=("own_reset", "sum")
    )
    is_detection = resets["own"].gt(0) & resets["kind"].isin(single_day_kinds).eq(False)
    resets["false_resets"] = resets["own"] - is_detection.astype(int)
    false_resets = resets.groupby(keys, as_index=False).agg(
        false_resets=("false_resets", "mean")
    )
    false_resets_overall = resets.groupby("variant", as_index=False).agg(
        false_resets=("false_resets", "mean")
    )

    cutovers = sorted(days["cutover_date"].unique())
    table = (
        wide.merge(spread[keys + ["mean", "detected"]], on=keys)
        .merge(scales, on=keys)
        .merge(false_resets, on=keys, how="left")
    )
    table[cutovers] = table[cutovers].astype("Int64")

    return DetectionSummary(
        table[keys + cutovers + ["mean", "detected", "false_resets", "scales"]],
        false_resets_overall,
    )


def near_control_new_pattern(paired: pd.DataFrame, tolerance_days: int) -> pd.Series:
    """Tage, an denen die Kontrolle in ±tolerance_days ein new_pattern hat. Im Kreislauf ist das ihr Reset, ohne Reset
    muss new_pattern schon auf den ersten Tag der Drift reduziert sein. Ein eigenes new_pattern dort ist derselbe natürliche
    Niveauwechsel, nur verschoben
    """
    window = ["mode", "variant", "kind", "cutover_date"]
    control_resets = paired.loc[
        paired["new_pattern_control"], window + ["days_since_cutover"]
    ].rename(columns={"days_since_cutover": "control_reset_day"})
    candidates = (
        paired[window + ["days_since_cutover"]]
        .reset_index()
        .merge(control_resets, on=window)
    )
    near = (
        (candidates["days_since_cutover"] - candidates["control_reset_day"])
        .abs()
        .le(tolerance_days)
    )

    return pd.Series(
        paired.index.isin(candidates.loc[near, "index"]), index=paired.index
    )


@dataclass(frozen=True)
class CalibrationSummary:
    gate_threshold: float
    alarm_by_window: pd.DataFrame
    streak_sensitivity: pd.DataFrame
    streak_selected: dict[str, float]


def summarize_calibration(
    calibration: dict[str, pd.DataFrame],
    uncounted_cutovers: tuple[str, ...],
    max_false_new_pattern: float,
) -> CalibrationSummary:
    gate = calibration["gate_threshold"]
    grid = calibration["streak_sensitivity"]
    threshold_columns = list(STREAK_THRESHOLD_COLUMNS.values())

    false_alarms = grid.groupby(threshold_columns, as_index=False).agg(
        false_new_pattern=("false_new_pattern", "mean")
    )
    counted = grid.loc[grid["cutover_date"].isin(uncounted_cutovers).eq(False)]
    detection = counted.groupby(threshold_columns, as_index=False).agg(
        detected=("first_event_new_pattern_day", "count"),
        detection_day=("first_event_new_pattern_day", "mean"),
        windows=("first_event_new_pattern_day", "size"),
    )
    sensitivity = false_alarms.merge(detection, on=threshold_columns)
    sensitivity["budget_excess"] = (
        sensitivity["false_new_pattern"] - max_false_new_pattern
    ).clip(lower=0)
    ranked = sensitivity.sort_values(
        ["budget_excess", "detected", "detection_day", "false_new_pattern"]
        + threshold_columns,
        ascending=[True, False, True, True] + [True] * len(threshold_columns),
    )
    selected_row = ranked.index[0]
    selected = ranked.loc[selected_row]

    return CalibrationSummary(
        gate_threshold=float(gate["gate_threshold"].iloc[0]),
        alarm_by_window=gate.assign(alarm_pct=gate["alarm_rate"] * 100),
        streak_selected={
            scale: float(selected[column])
            for scale, column in STREAK_THRESHOLD_COLUMNS.items()
        },
        streak_sensitivity=sensitivity.assign(
            selected=sensitivity.index.to_series()
            .eq(selected_row)
            .map({True: "ja", False: ""}),
            detected=sensitivity["detected"].astype(str)
            + "/"
            + sensitivity["windows"].astype(str),
        ),
    )
