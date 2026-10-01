# python -m pytest tests/unit/experiments/proactive_cycle -v

import pandas as pd
import pytest

from experiments.proactive_cycle.pc_outlook import OutlookState, build_outlook_state

TIMEZONE = "Europe/London"


def _state_for(
    day: str, usual_mean_w: float | None, factor: float | None = 1.0
) -> OutlookState:
    decision_time = pd.Timestamp(day, tz=TIMEZONE).tz_convert("UTC")
    hours = pd.date_range(decision_time, periods=48, freq="1h")
    return build_outlook_state(
        pd.DataFrame({"target_timestamp": hours, "y_pred": 300.0}),
        decision_time,
        usual_mean_w=usual_mean_w,
        retransformation_factor=factor,
        decimals=2,
        local_timezone=TIMEZONE,
    )


def test_state_sums_only_the_day_and_follows_its_length() -> None:
    normal = _state_for("2014-03-29", 270.0)
    short = _state_for("2014-03-30", 270.0)

    # 24 Stunden mit 300 W, übliches Tagesmittel 270 W
    assert normal["forecast_kwh"] == pytest.approx(7.2)
    assert normal["usual_kwh"] == pytest.approx(6.48)
    assert normal["deviation_pct"] == pytest.approx(11.11, abs=0.01)
    # Umstelltag mit 23 Stunden, Prognose und üblicher Wert zählen dieselben Stunden
    assert short["forecast_kwh"] == pytest.approx(6.9)
    assert short["usual_kwh"] == pytest.approx(6.21)


def test_state_without_usual_value() -> None:
    state = _state_for("2014-03-29", None)

    assert state["usual_kwh"] is None
    assert state["deviation_pct"] is None


def test_factor_scales_the_forecast_only() -> None:
    state = _state_for("2014-03-29", 270.0, factor=1.1)

    assert state["forecast_kwh"] == pytest.approx(7.92)
    assert state["usual_kwh"] == pytest.approx(6.48)
