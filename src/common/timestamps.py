from __future__ import annotations

from typing import TypeVar, cast

import pandas as pd

SeriesOrFrame = TypeVar("SeriesOrFrame", pd.Series, pd.DataFrame)


def parse_utc_timestamp(value: object, field_name: str) -> pd.Timestamp:
    if isinstance(value, pd.Timestamp):
        timestamp = value
    elif isinstance(value, str):
        try:
            timestamp = pd.Timestamp(value)
        except (TypeError, ValueError, OverflowError) as error:
            raise ValueError(f"{field_name} must be a valid timestamp.") from error
    else:
        raise TypeError(f"{field_name} must be a string or pandas Timestamp.")

    if pd.isna(timestamp):
        raise ValueError(f"{field_name} must not be missing.")

    if timestamp.tzinfo is None:
        raise ValueError(f"{field_name} must contain timezone information.")

    return timestamp.tz_convert("UTC")


def parse_utc_timestamp_field(value: object, field_name: str) -> pd.Timestamp:
    # JSON-Felder stehen in Ortszeit mit Offset (lesbar fürs LLM), intern wird mit UTC weitergerechnet
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string timestamp.")

    timestamp = parse_utc_timestamp(value, field_name)

    normalized_value = value[:-1] + "+00:00" if value.endswith("Z") else value
    if normalized_value != pd.Timestamp(normalized_value).isoformat():
        raise ValueError(f"{field_name} must be an ISO-8601 timestamp with offset.")

    return timestamp


def local_isoformat(timestamp: pd.Timestamp, local_timezone: str) -> str:
    return timestamp.tz_convert(local_timezone).isoformat()


def snap_to_local_midnight_range(
    start: pd.Timestamp,
    end: pd.Timestamp,
    local_timezone: str,
) -> tuple[pd.Timestamp, pd.Timestamp]:
    """start (inklusiv) und end (exklusiv) auf volle lokale Kalendertage einschränken.
    Aufrufer, die end inklusiv weiterreichen (z.B. .loc-Slicing), ziehen selbst die passende
    sample_period ab, siehe auxiliary_appliance_selection.py"""
    local_start = start.tz_convert(local_timezone)
    local_end = end.tz_convert(local_timezone)

    snapped_start = local_start.normalize()
    if snapped_start < local_start:
        snapped_start = snapped_start + pd.DateOffset(days=1)

    snapped_end = local_end.normalize()

    if snapped_start >= snapped_end:
        raise ValueError("start and end do not span a full local day.")

    return snapped_start.tz_convert("UTC"), snapped_end.tz_convert("UTC")


def shift_local_days(
    timestamp: pd.Timestamp, days: int, local_timezone: str
) -> pd.Timestamp:
    # Versatz in Kalendertagen, über eine Zeitumstellung hat ein Tag also 23 oder 25 Stunden
    return (timestamp.tz_convert(local_timezone) + pd.DateOffset(days=days)).tz_convert(
        "UTC"
    )


def local_midnight_utc(
    date: str | pd.Timestamp, local_timezone: str, days_offset: int = 0
) -> pd.Timestamp:
    return shift_local_days(
        pd.Timestamp(date, tz=local_timezone), days_offset, local_timezone
    )


def local_day_index(index: pd.Index, local_timezone: str) -> pd.DatetimeIndex:
    return pd.DatetimeIndex(index).tz_convert(local_timezone).normalize()


def local_daily_mean(values: SeriesOrFrame, local_timezone: str) -> SeriesOrFrame:
    return cast(SeriesOrFrame, values.tz_convert(local_timezone).resample("D").mean())


def local_day(timestamp: pd.Timestamp, local_timezone: str) -> pd.Timestamp:
    return local_day_index(pd.DatetimeIndex([timestamp]), local_timezone)[0]


def reindex_at_local_lag(
    series: pd.Series,
    target_index: pd.DatetimeIndex,
    lag_days: int,
    local_timezone: str,
) -> pd.Series:
    # Vergleich über die Wanduhrzeit, damit 08:00 auch nach der Zeitumstellung auf 08:00 vom Vortag zeigt
    wall_clock = pd.Series(
        series.to_numpy(),
        index=pd.DatetimeIndex(series.index)
        .tz_convert(local_timezone)
        .tz_localize(None),
    )
    # im Oktober gibt es 01:00 zweimal, der erste Wert zählt
    wall_clock = wall_clock[~wall_clock.index.duplicated()]

    reference = target_index.tz_convert(local_timezone).tz_localize(
        None
    ) - pd.Timedelta(days=lag_days)
    # die im März übersprungene Stunde nimmt den Wert davor, die Uhr springt genau eine Stunde
    values = wall_clock.reindex(
        reference, method="ffill", tolerance=pd.Timedelta(hours=1)
    )

    return pd.Series(values.to_numpy(), index=target_index)


def analyzed_day_index(
    decision_times: pd.Index, local_timezone: str
) -> pd.DatetimeIndex:
    # decision_time ist die Mitternacht nach dem analysierten Tag, die Prognose startet dagegen genau dort
    return local_day_index(
        pd.DatetimeIndex(decision_times) - pd.Timedelta(hours=1), local_timezone
    )


def analyzed_day(decision_time: pd.Timestamp, local_timezone: str) -> pd.Timestamp:
    return analyzed_day_index(pd.DatetimeIndex([decision_time]), local_timezone)[0]


def analyzed_day_text(decision_time: pd.Timestamp, local_timezone: str) -> str:
    return analyzed_day(decision_time, local_timezone).date().isoformat()


def local_date_text(timestamp: pd.Timestamp, local_timezone: str) -> str:
    return local_day(timestamp, local_timezone).date().isoformat()


def local_days_between(
    later: pd.Timestamp, earlier: pd.Timestamp, local_timezone: str
) -> int:
    return (
        local_day(later, local_timezone).tz_localize(None)
        - local_day(earlier, local_timezone).tz_localize(None)
    ).days


def local_day_hours(
    day_start: pd.Timestamp, days: int, frequency: str, local_timezone: str
) -> pd.DatetimeIndex:
    day_end = shift_local_days(day_start, days, local_timezone)
    return pd.date_range(start=day_start, end=day_end, freq=frequency, inclusive="left")


def local_calendar_range(
    start: pd.Timestamp,
    step_days: int,
    end: pd.Timestamp,
    local_timezone: str,
) -> pd.DatetimeIndex:
    local_start = start.tz_convert(local_timezone)

    # sonst läuft jeder Tag der Reihe mit demselben Versatz, z.B. 01:00-01:00 bei UTC-Mitternacht im Sommer
    if local_start != local_start.normalize():
        raise ValueError(f"start must lie on local midnight, got {local_start}.")

    local_index = pd.date_range(
        start=local_start, end=end.tz_convert(local_timezone), freq=f"{step_days}D"
    )
    return local_index.tz_convert("UTC")
