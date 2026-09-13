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