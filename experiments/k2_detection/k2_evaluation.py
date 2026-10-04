from dataclasses import dataclass

import numpy as np
import pandas as pd

from experiments.common.evaluation import streak_scale_names
from experiments.k2_detection.k2_config import STREAK_THRESHOLD_COLUMNS
from src.common.timestamps import analyzed_day_index


def _daily_means(series: pd.Series, local_timezone: str) -> pd.Series:
    return series.tz_convert(local_timezone).resample("D").mean().tz_localize(None)


def find_real_events(
    series: pd.Series,
    *,
    local_timezone: str,
    reference_days: int,
    transition_days: int,
    min_change_pct: float,
    min_duration_days: int,
    smoothing_days: int,
    share: float,
    merge_days: int,
) -> pd.DataFrame:
    """Echte Trends aus den Tagesmitteln, ohne Detektor: das Niveau ändert sich gegen den Median der reference_days davor
    um mindestens min_change_pct, der Übergang ist nach transition_days abgeschlossen und das neue Niveau hält
    min_duration_days. Beginn ist der erste Tag, an dem die Abweichung die halbe Mindeständerung erreicht
    """
    daily = _daily_means(series, local_timezone)
    values = daily.to_numpy()
    level = daily.rolling(smoothing_days, center=True, min_periods=1).mean().to_numpy()
    min_change = min_change_pct / 100

    candidates: list[tuple[int, float, float]] = []
    for day in range(reference_days, len(values) - transition_days - min_duration_days):
        before = np.nanmedian(values[day - reference_days : day])
        hold = values[day + transition_days : day + transition_days + min_duration_days]
        change = np.nanmedian(hold) / before - 1
        if abs(change) < min_change:
            continue
        # beide Hälften der Haltephase zeigen die Änderung in dieselbe Richtung
        half = len(hold) // 2
        halves = [
            np.nanmedian(part) / before - 1 for part in (hold[:half], hold[half:])
        ]
        if any(
            np.sign(value) != np.sign(change) or abs(value) < share * min_change
            for value in halves
        ):
            continue
        # Übergang: am Tag noch das alte Niveau, nach transition_days das neue
        new_level = before * (1 + change)
        progress_start = (level[day] - before) / (new_level - before)
        progress_end = (level[day + transition_days] - before) / (new_level - before)
        if progress_start > 1 - share or progress_end < share:
            continue
        candidates.append((day, before, change))

    # Kandidaten innerhalb von merge_days sind ein Ereignis, der Beginn kommt vom ersten
    firsts = []
    previous = None
    for candidate in candidates:
        if previous is None or candidate[0] - previous > merge_days:
            firsts.append(candidate)
        previous = candidate[0]

    starts, directions, changes = [], [], []
    for day, before, change in firsts:
        for offset in range(transition_days + min_duration_days):
            if abs(level[day + offset] / before - 1) >= min_change / 2:
                starts.append(daily.index[day + offset])
                directions.append(int(np.sign(change)))
                changes.append(change * 100)
                break

    return pd.DataFrame(
        {"start": starts, "direction": directions, "change_pct": changes}
    )


def analysis_days(
    series: pd.Series,
    *,
    local_timezone: str,
    first_day: pd.Timestamp,
    last_day: pd.Timestamp,
) -> pd.DatetimeIndex:
    days = _daily_means(series, local_timezone).index

    return pd.DatetimeIndex(days[(days >= first_day) & (days <= last_day)])


def scenario_days(
    decision_times: tuple[pd.Timestamp, ...], local_timezone: str
) -> pd.DatetimeIndex:
    return analyzed_day_index(
        pd.DatetimeIndex(decision_times), local_timezone
    ).tz_localize(None)


def _hit_windows(
    starts: pd.Series, *, hit_days_before: int, hit_days_after: int
) -> zip:
    return zip(
        starts - pd.Timedelta(days=hit_days_before),
        starts + pd.Timedelta(days=hit_days_after),
    )


def events_in_range(
    events: pd.DataFrame,
    first_day: pd.Timestamp,
    last_day: pd.Timestamp,
    *,
    hit_days_before: int,
    hit_days_after: int,
) -> pd.DataFrame:
    inside = [
        window_start >= first_day and window_end <= last_day
        for window_start, window_end in _hit_windows(
            events["start"],
            hit_days_before=hit_days_before,
            hit_days_after=hit_days_after,
        )
    ]

    return events.loc[inside].reset_index(drop=True)


def _in_event_window(
    days: pd.Series,
    events: pd.DataFrame,
    *,
    hit_days_before: int,
    hit_days_after: int,
) -> pd.Series:
    inside = pd.Series(False, index=days.index)
    for window_start, window_end in _hit_windows(
        events["start"],
        hit_days_before=hit_days_before,
        hit_days_after=hit_days_after,
    ):
        inside |= days.ge(window_start) & days.le(window_end)

    return inside


def event_hits(
    chain: pd.DataFrame,
    events: pd.DataFrame,
    *,
    hit_days_before: int,
    hit_days_after: int,
) -> pd.DataFrame:
    """Je Ereignis der erste Reset im Trefferfenster, Tage seit dem Beginn (negativ = davor)"""
    resets = chain.loc[chain["reset"], "analyzed_day"]
    first_reset = []
    for window_start, window_end in _hit_windows(
        events["start"],
        hit_days_before=hit_days_before,
        hit_days_after=hit_days_after,
    ):
        window = resets[resets.ge(window_start) & resets.le(window_end)]
        first_reset.append(window.min() if len(window) else pd.NaT)

    table = pd.DataFrame({"start": events["start"], "reset_day": first_reset})
    table["delay"] = (table["reset_day"] - table["start"]).dt.days

    return table


def summarize_point(
    chain: pd.DataFrame,
    events: pd.DataFrame,
    *,
    hit_days_before: int,
    hit_days_after: int,
) -> dict[str, float]:
    hits = event_hits(
        chain, events, hit_days_before=hit_days_before, hit_days_after=hit_days_after
    )
    resets = chain.loc[chain["reset"], "analyzed_day"]
    outside = resets.loc[
        _in_event_window(
            resets,
            events,
            hit_days_before=hit_days_before,
            hit_days_after=hit_days_after,
        ).eq(False)
    ]

    return {
        "hits": int(hits["reset_day"].notna().sum()),
        "events": len(events),
        "mean_delay": float(hits["delay"].mean()),
        "resets": len(resets),
        "false_resets": len(outside),
        "false_per_year": len(outside) * 365.25 / len(chain),
    }


@dataclass(frozen=True)
class GridSummary:
    selected: dict[str, float]
    ranked: pd.DataFrame


def summarize_grid(
    points: pd.DataFrame,
    max_false_per_year: float,
    current_thresholds: dict[str, float],
) -> GridSummary:
    threshold_columns = list(STREAK_THRESHOLD_COLUMNS.values())
    excess = (points["false_per_year"] - max_false_per_year).clip(lower=0)
    ranked = (
        points.assign(budget_excess=excess)
        .sort_values(
            ["budget_excess", "hits", "mean_delay", "false_per_year"]
            + threshold_columns,
            ascending=[True, False, True, True] + [True] * len(threshold_columns),
            na_position="last",
        )
        .reset_index(drop=True)
    )

    is_current = pd.Series(True, index=ranked.index)
    for scale, column in STREAK_THRESHOLD_COLUMNS.items():
        is_current &= ranked[column].eq(current_thresholds[scale])

    selected = ranked.iloc[0]

    return GridSummary(
        selected={
            scale: float(selected[column])
            for scale, column in STREAK_THRESHOLD_COLUMNS.items()
        },
        ranked=ranked.assign(
            selected=ranked.index == 0,
            current=is_current,
        ),
    )


def summarize_events(
    events: pd.DataFrame, chosen: pd.DataFrame, current: pd.DataFrame
) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "start": events["start"],
            "change_pct": events["change_pct"],
            "chosen_reset": chosen["reset_day"],
            "chosen_delay": chosen["delay"],
            "current_reset": current["reset_day"],
            "current_delay": current["delay"],
        }
    )


def diagnosis_case(
    chain: pd.DataFrame,
    cutover_date: str,
    kind: str,
    *,
    events: pd.DataFrame,
    positive_kinds: tuple[str, ...],
    negative_kinds: tuple[str, ...],
    hit_days_before: int,
    hit_days_after: int,
) -> dict[str, object]:
    day = (
        chain["analyzed_day"] + pd.Timedelta(days=1) - pd.Timestamp(cutover_date)
    ).dt.days
    if kind in positive_kinds:
        reacted = chain["reset"] & day.between(1, hit_days_after)
    elif kind in negative_kinds:
        outside = _in_event_window(
            chain["analyzed_day"],
            events,
            hit_days_before=hit_days_before,
            hit_days_after=hit_days_after,
        ).eq(False)
        reacted = chain["reset"] & day.ge(1) & outside
    else:
        reacted = chain["alarm"] & day.eq(1)

    first = chain.loc[reacted].head(1)
    scales = ""
    if len(first) and kind not in negative_kinds:
        scales = streak_scale_names(first).iloc[0]

    return {
        "kind": kind,
        "cutover_date": cutover_date,
        "hit_day": float(day[first.index[0]]) if len(first) else np.nan,
        "scales": scales,
    }


def summarize_diagnosis(cases: pd.DataFrame) -> pd.DataFrame:
    """Je Einstellung und Eingriff: erkannt bzw. gefeuert in hits von windows Fenstern, mittlerer Tag"""
    return cases.groupby(["config", "kind"], as_index=False, sort=False).agg(
        hits=("hit_day", "count"),
        windows=("hit_day", "size"),
        mean_day=("hit_day", "mean"),
    )


@dataclass(frozen=True)
class Headline:
    detection_met: bool
    false_met: bool
    slow_met: bool
    diagnosis_hits: int
    diagnosis_windows: int
    slow_fired: int
    slow_windows: int


def summarize_headline(
    selected: pd.Series,
    diagnosis: pd.DataFrame,
    *,
    positive_kinds: tuple[str, ...],
    negative_kinds: tuple[str, ...],
    target_detected_share: float,
    max_false_per_year: float,
    max_slow_fired_share: float,
) -> Headline:
    chosen = diagnosis.loc[diagnosis["config"].eq("chosen")]
    positive = chosen.loc[chosen["kind"].isin(positive_kinds)]
    negative = chosen.loc[chosen["kind"].isin(negative_kinds)]
    slow_fired = int(negative["hits"].sum())
    slow_windows = int(negative["windows"].sum())

    return Headline(
        detection_met=bool(
            selected["hits"] / selected["events"] >= target_detected_share
        ),
        false_met=bool(selected["false_per_year"] <= max_false_per_year),
        slow_met=slow_fired / slow_windows <= max_slow_fired_share,
        diagnosis_hits=int(positive["hits"].sum()),
        diagnosis_windows=int(positive["windows"].sum()),
        slow_fired=slow_fired,
        slow_windows=slow_windows,
    )
