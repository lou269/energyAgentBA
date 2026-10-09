from dataclasses import dataclass

import numpy as np
import pandas as pd

from experiments.common.evaluation import FIRST_ANALYZED_DAY
from experiments.common.standard_config import (
    EXPECTED_DETECTION,
    GOLDSTANDARD_EXPECTED,
)


def sustained_values(
    values: pd.DataFrame, *, window_days: int, min_days: int
) -> pd.DataFrame:
    """Je Tag und Skala der min_days-größte Betrag im Fenster der letzten window_days Tage"""

    def kth_largest(window: np.ndarray) -> float:
        valid = np.sort(np.abs(window[~np.isnan(window)]))
        return valid[-min_days] if len(valid) >= min_days else np.nan

    return values.rolling(window_days, min_periods=min_days).apply(
        kth_largest, raw=True
    )


def thresholds_for_share(sustained: pd.DataFrame, share: float) -> dict[str, float]:
    """Schwelle je Skala, mit der sie an share der Tage anhält. Tage ohne Wert zählen als nicht anhaltend"""
    return {
        scale: float(sustained[scale].fillna(0.0).quantile(1 - share))
        for scale in sustained.columns
    }


def summarize_grid(
    grid: pd.DataFrame, resets: pd.DataFrame, *, days: int, max_resets: int
) -> pd.DataFrame:
    """Je Anteil die Schwellen, die Resets im durchgehenden Lauf und je Jahr.
    Gewählt ist der größte Anteil (empfindlichste Schwellen) mit höchstens max_resets Resets
    """
    counts = resets.groupby("share").size()
    summary = grid.assign(
        resets=grid["share"].map(counts).fillna(0).astype(int),
    )
    summary["resets_per_year"] = summary["resets"] * 365.25 / days
    chosen = summary.loc[summary["resets"].le(max_resets), "share"].max()

    return summary.assign(selected=summary["share"].eq(chosen))


def single_day_shares(
    scores: pd.Series, directions: pd.Series, thresholds: tuple[float, ...]
) -> pd.DataFrame:
    """Anteil der Tage mit Score ab der Schwelle und Richtung high, Tage ohne Score zählen nicht"""
    valid = scores.notna()
    peak_scores = scores.where(directions.eq("high"), 0.0)[valid]
    return pd.DataFrame(
        {
            "threshold": list(thresholds),
            "alarm_share": [
                float(peak_scores.ge(value).mean()) for value in thresholds
            ],
        }
    )


def summarize_single_day(shares: pd.DataFrame, *, target_share: float) -> pd.DataFrame:
    """Gewählt ist die Schwelle, deren Anteil am nächsten am Ziel liegt, bei Gleichstand die niedrigere"""
    closest = (shares["alarm_share"] - target_share).abs().idxmin()

    return shares.assign(selected=shares.index == closest)


def spaced_cutovers(
    first_day: pd.Timestamp,
    last_day: pd.Timestamp,
    *,
    before_days: int,
    after_days: int,
) -> list[str]:
    starts = pd.date_range(
        first_day + pd.Timedelta(days=before_days),
        last_day - pd.Timedelta(days=after_days),
        freq=pd.Timedelta(days=after_days),
    )

    return [start.strftime("%Y-%m-%d") for start in starts]


def diagnosis_case(
    chain: pd.DataFrame, cutover_date: str, kind: str
) -> dict[str, object]:
    """Erster Reset ab dem Ereignistag (Tage seit Cutover) und Alarm am Ereignistag"""
    day = (
        chain["analyzed_day"] + pd.Timedelta(days=1) - pd.Timestamp(cutover_date)
    ).dt.days
    resets = day[chain["reset"] & day.ge(FIRST_ANALYZED_DAY)]

    return {
        "kind": kind,
        "cutover_date": cutover_date,
        "reset_day": float(resets.min()) if len(resets) else np.nan,
        "event_alarm": bool(chain.loc[day.eq(FIRST_ANALYZED_DAY), "alarm"].any()),
    }


def summarize_diagnosis(cases: pd.DataFrame) -> pd.DataFrame:
    """Je Einstellung und Art: eigene Resets, Resets insgesamt, Median des eigenen Reset-Tages, Alarme am Ereignistag"""
    control = cases.loc[
        cases["kind"].eq("control"), ["config", "cutover_date", "reset_day"]
    ].rename(columns={"reset_day": "control_reset_day"})
    cases = cases.merge(control, on=["config", "cutover_date"])
    own = cases["reset_day"].notna() & ~cases["control_reset_day"].le(
        cases["reset_day"]
    )

    return (
        cases.assign(
            own_reset=own,
            own_reset_day=cases["reset_day"].where(own),
            expected=cases["kind"].map(GOLDSTANDARD_EXPECTED).map(EXPECTED_DETECTION),
        )
        .groupby(["config", "kind", "expected"], as_index=False, sort=False)
        .agg(
            windows=("kind", "size"),
            own_resets=("own_reset", "sum"),
            any_resets=("reset_day", "count"),
            median_reset_day=("own_reset_day", "median"),
            event_alarms=("event_alarm", "sum"),
        )
    )


@dataclass(frozen=True)
class K1Summary:
    grid: pd.DataFrame
    selected: pd.Series
    single_day: pd.DataFrame
    single_day_selected: pd.Series
    diagnosis: pd.DataFrame


def summarize_k1(
    grid: pd.DataFrame,
    resets: pd.DataFrame,
    single_day: pd.DataFrame,
    cases: pd.DataFrame,
    *,
    days: int,
    max_resets: int,
    single_day_target_share: float,
) -> K1Summary:
    """Raster mit gewähltem Punkt und Diagnose je Einstellung und Art"""
    summary = summarize_grid(grid, resets, days=days, max_resets=max_resets)
    single_day_summary = summarize_single_day(
        single_day, target_share=single_day_target_share
    )

    return K1Summary(
        grid=summary,
        selected=summary.loc[summary["selected"]].iloc[0],
        single_day=single_day_summary,
        single_day_selected=single_day_summary.loc[single_day_summary["selected"]].iloc[
            0
        ],
        diagnosis=summarize_diagnosis(cases),
    )
