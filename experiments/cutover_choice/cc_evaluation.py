from dataclasses import dataclass

import pandas as pd

from src.common.timestamps import local_day


@dataclass(frozen=True)
class WindowSummary:
    cutover_date: str
    first_day: str
    last_day: str
    resets: int
    first_reset: str
    alarm_days: int
    clean: bool


def candidate_cutovers(
    series_start: pd.Timestamp,
    split_start: pd.Timestamp,
    split_end: pd.Timestamp,
    *,
    coldstart_days: int,
    before_days: int,
    after_days: int,
    step_days: int,
    local_timezone: str,
) -> list[str]:
    """Cutover im Raster, deren Entscheidungstage im Abschnitt und deren Kaltstart in der Reihe liegen"""
    series_first = local_day(series_start, local_timezone).tz_localize(None)
    first = local_day(split_start, local_timezone).tz_localize(None)
    last = local_day(split_end, local_timezone).tz_localize(None)
    # 1 Tag Reserve
    earliest = max(
        first + pd.Timedelta(days=before_days),
        series_first + pd.Timedelta(days=coldstart_days + before_days + 1),
    )
    starts = pd.date_range(
        earliest,
        last - pd.Timedelta(days=after_days),
        freq=pd.Timedelta(days=step_days),
    )

    return [start.strftime("%Y-%m-%d") for start in starts]


def summarize_window(chain: pd.DataFrame, cutover_date: str) -> WindowSummary:
    """Resets und Alarm-Tage der Kette im Control-Fenster, sauber = kein Reset im Fenster"""
    resets = chain.loc[chain["reset"], "analyzed_day"]

    return WindowSummary(
        cutover_date=cutover_date,
        first_day=str(chain["analyzed_day"].iloc[0].date()),
        last_day=str(chain["analyzed_day"].iloc[-1].date()),
        resets=len(resets),
        first_reset=str(resets.iloc[0].date()) if len(resets) else "",
        alarm_days=int(chain["alarm"].sum()),
        clean=len(resets) == 0,
    )
