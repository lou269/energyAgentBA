from __future__ import annotations

import pandas as pd


def summarize_prophet_forecast(
    forecast: pd.DataFrame,
) -> dict:
    required_columns = {
        "yhat",
        "yhat_lower",
        "yhat_upper",
    }

    missing = required_columns - set(forecast.columns)

    if missing:
        raise ValueError(
            "Forecast is missing required columns: "
            + ", ".join(sorted(missing))
        )

    if forecast.empty:
        raise ValueError(
            "Forecast must not be empty."
        )

    interval_width = (
        forecast["yhat_upper"]
        - forecast["yhat_lower"]
    )

    peak_timestamp = pd.Timestamp(
        forecast["yhat"].idxmax()
    )

    return {
        "horizon_hours": int(len(forecast)),
        "mean_forecast_w": float(
            forecast["yhat"].mean()
        ),
        "peak_forecast_w": float(
            forecast["yhat"].max()
        ),
        "peak_timestamp": peak_timestamp.isoformat(),
        "min_forecast_w": float(
            forecast["yhat"].min()
        ),
        "mean_interval_width_w": float(
            interval_width.mean()
        ),
    }


def build_structured_state(
    data: pd.DataFrame,
    history: pd.Series,
    cutoff: pd.Timestamp,
    prophet_summary: dict,
    calendar_context: dict,
) -> dict:
    cutoff = pd.Timestamp(cutoff)

    current = data.loc[[cutoff]].iloc[0]

    recent_24h = history.tail(24)
    recent_7d = history.tail(168)

    return {
        "timestamp": cutoff.isoformat(),

        "observation": {
            "current_power_w": _float_or_none(
                current["current_power"]
            ),
            "last_24h_mean_w": float(
                recent_24h.mean()
            ),
            "last_7d_mean_w": float(
                recent_7d.mean()
            ),
        },

        "analysis": {
            "short_term_mean_w": _float_or_none(
                current["short_term_mean"]
            ),
            "daily_expected_w": _float_or_none(
                current["daily_expected"]
            ),
            "weekly_expected_w": _float_or_none(
                current["weekly_expected"]
            ),
            "long_term_mean_w": _float_or_none(
                current["long_term_mean"]
            ),
            "trend": _value_or_none(
                current["trend"]
            ),
            "trend_change": _float_or_none(
                current["trend_change"]
            ),
        },

        "anomaly": {
            "score": _float_or_none(
                current["anomaly_score"]
            ),
            "level": _value_or_none(
                current["anomaly_level"]
            ),
            "direction": _value_or_none(
                current["anomaly_direction"]
            ),
            "dominant_scale": _value_or_none(
                current["dominant_scale"]
            ),
        },

        "forecast": {
            "model": "prophet",
            "summary": prophet_summary,
        },

        "context": calendar_context,
    }


def _float_or_none(
    value,
):
    if pd.isna(value):
        return None

    return float(value)


def _value_or_none(
    value,
):
    if pd.isna(value):
        return None

    return value