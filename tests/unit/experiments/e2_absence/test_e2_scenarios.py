# python -m pytest tests/unit/experiments/e2_absence -v

import numpy as np
import pandas as pd

from experiments.e2_absence.e2_scenarios import build_ctx_scenarios


def _series(hours: int) -> pd.Series:
    index = pd.date_range("2024-01-01", periods=hours, freq="1h", tz="UTC")
    hour_of_day = index.hour.to_numpy()
    values = 200.0 + 50.0 * np.sin(2 * np.pi * hour_of_day / 24) + 10.0
    return pd.Series(values, index=index, name="target")


def test_ctx_scenarios() -> None:
    series = _series(240)
    decision_times = (series.index[100], series.index[150])
    events = (
        {
            "event_id": "e",
            "event_type": "absence",
            "start": "2024-01-01T00:00:00+00:00",
            "end": "2024-01-02T00:00:00+00:00",
            "known_at": "2023-12-01T00:00:00+00:00",
        },
    )

    scenarios = build_ctx_scenarios(series, decision_times, events)
    ctx0, ctx1 = scenarios["ctx0"], scenarios["ctx1"]

    assert ctx0.calendar_source_available is False
    assert ctx0.calendar_events == ()
    assert ctx1.calendar_source_available is True
    assert ctx1.calendar_events == events
    assert ctx0.target_series.equals(ctx1.target_series)
    assert ctx0.decision_times == ctx1.decision_times
    # ctx2 unterscheidet sich nur im Kalender-Tool
    assert scenarios["ctx2"] == ctx1
