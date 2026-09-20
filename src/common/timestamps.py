from __future__ import annotations

import pandas as pd


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
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string timestamp.")

    timestamp = parse_utc_timestamp(value, field_name)

    normalized_value = value[:-1] + "+00:00" if value.endswith("Z") else value
    if normalized_value != timestamp.isoformat():
        raise ValueError(f"{field_name} must be an ISO-8601 UTC timestamp.")

    return timestamp


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


def local_day_index(index: pd.Index, local_timezone: str) -> pd.DatetimeIndex:
    return pd.DatetimeIndex(index).tz_convert(local_timezone).normalize()


def local_calendar_range(
    start: pd.Timestamp,
    step_hours: int,
    end: pd.Timestamp,
    local_timezone: str,
) -> pd.DatetimeIndex:
    if step_hours % 24 == 0:
        local_index = pd.date_range(
            start=start.tz_convert(local_timezone),
            end=end.tz_convert(local_timezone),
            freq=f"{step_hours // 24}D",
        )
        return local_index.tz_convert("UTC")

    return pd.date_range(start=start, end=end, freq=f"{step_hours}h")