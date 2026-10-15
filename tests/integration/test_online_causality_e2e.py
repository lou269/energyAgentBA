# python -m pytest tests/integration/test_online_causality_e2e.py -v
#
# Aufbereitung und Tageszyklus dürfen am Entscheidungstag nichts aus der Zukunft kennen

from collections.abc import Hashable, Mapping

import numpy as np
import pandas as pd
import pytest

from src.common.column_naming import (
    channel_data_column,
    plausibility_column,
    quality_column,
    treated_column,
)
from src.common.timestamps import shift_local_days
from src.config.config_forecasting import SYS_VARIANTS, PreprocessingConfig
from src.context.calendar_context import build_calendar_context
from src.pipeline.daily_cycle import CycleResult, CycleState, run_cycle
from src.preprocessing.preprocessing_runner import run_preprocessing

TIMEZONE = "Europe/London"
# Winter, lokale Zeit gleich UTC
START = pd.Timestamp("2024-01-01", tz="UTC")
COLDSTART_DAYS = 60
CYCLE_DAYS = 3
DAYS_AFTER = 2
METER = "m1"
HOUR = pd.Timedelta(hours=1)

PREPROCESSING = PreprocessingConfig()
CONFIG = SYS_VARIANTS["SYS2"]
DECISION_TIME = START + pd.Timedelta(days=COLDSTART_DAYS + CYCLE_DAYS)

PAST_EVENT = {
    "event_id": "besuch",
    "title": "Besuch",
    "start": (DECISION_TIME - 30 * HOUR).isoformat(),
    "end": (DECISION_TIME - 20 * HOUR).isoformat(),
    "known_at": (DECISION_TIME - pd.Timedelta(days=10)).isoformat(),
}
# liegt im Kalenderfenster, ist aber erst eine Stunde nach der Entscheidung bekannt
LATE_EVENT = {
    "event_id": "urlaub",
    "title": "Urlaub",
    "start": (DECISION_TIME + 2 * HOUR).isoformat(),
    "end": (DECISION_TIME + 10 * HOUR).isoformat(),
    "known_at": (DECISION_TIME + HOUR).isoformat(),
}


def _raw_series() -> pd.Series:
    hours = (COLDSTART_DAYS + CYCLE_DAYS + DAYS_AFTER) * 24
    index = pd.date_range(START, periods=hours, freq="1h")
    jitter_by_day = np.random.default_rng(5).normal(0.0, 5.0, size=hours // 24)
    values = (
        200.0
        + 2.0 * np.sin(2 * np.pi * index.hour.to_numpy() / 24)
        + jitter_by_day[np.arange(hours) // 24]
    )
    return pd.Series(values, index=index)


def _series_with_defects(gap_across_decision: bool) -> pd.Series:
    values = _raw_series()
    # kurze Lücke und festhängender Wert, beides lange vor der Entscheidung
    values.loc[DECISION_TIME - 60 * HOUR : DECISION_TIME - 58 * HOUR] = np.nan
    stuck_start = DECISION_TIME - 50 * HOUR
    stuck_end = DECISION_TIME - 43 * HOUR
    values.loc[stuck_start:stuck_end] = values.loc[stuck_start]
    if gap_across_decision:
        # vor der Entscheidung genau so lang wie die Auffüllgrenze, insgesamt länger
        limit = PREPROCESSING.max_imputation_gap_hourly
        values.loc[DECISION_TIME - limit * HOUR : DECISION_TIME + 2 * HOUR] = np.nan
    return values


def _calendar_context(decision_time: pd.Timestamp, events: list[Mapping[str, object]]):
    return build_calendar_context(
        events,
        source_available=bool(events),
        source="test" if events else "none",
        retrieved_at=decision_time,
        decision_time=decision_time,
        window_start=decision_time - 24 * HOUR,
        window_end=decision_time + 24 * HOUR,
        local_timezone=TIMEZONE,
    )


def _last_cycle(values: pd.Series, events: list[Mapping[str, object]]) -> CycleResult:
    data = pd.DataFrame({channel_data_column(METER, "hourly"): values})
    quality = pd.DataFrame({quality_column(METER, "coverage_mask"): values.notna()})
    prepared = run_preprocessing(
        data,
        quality,
        PREPROCESSING,
        TIMEZONE,
        sample_period_hours_hourly=1.0,
    )
    target = prepared.treated_hourly[treated_column(METER)].rename("target")
    implausible = prepared.plausibility_hourly[plausibility_column(METER)]

    cutover = START + pd.Timedelta(days=COLDSTART_DAYS)
    state = CycleState(
        history=target.loc[: cutover - HOUR],
        prophet_model=None,
        model_history=None,
        model_fitted_at=None,
    )
    decision_time = cutover
    for _ in range(CYCLE_DAYS):
        decision_time = shift_local_days(decision_time, 1, TIMEZONE)
        new_observations = target.loc[
            state.history.index[-1] + HOUR : decision_time - HOUR
        ]
        result, state = run_cycle(
            state,
            new_observations,
            decision_time,
            CONFIG,
            local_timezone=TIMEZONE,
            calendar_context=_calendar_context(decision_time, events),
            new_value_implausible=implausible.loc[new_observations.index],
        )

    assert result.decision_time == DECISION_TIME  # type: ignore
    return result  # type: ignore


def _row_values(row: pd.Series | None) -> dict[Hashable, object] | None:
    # fehlende Werte als None, sonst ist NA nicht vergleichbar
    if row is None:
        return None
    return {key: None if pd.isna(value) else value for key, value in row.items()}


def _assert_same_result(left: CycleResult, right: CycleResult) -> None:
    assert left.classification == right.classification
    assert _row_values(left.analysis_row) == _row_values(right.analysis_row)
    assert left.structured_state == right.structured_state
    assert left.adaption_action == right.adaption_action
    np.testing.assert_allclose(left.forecast["y_pred"], right.forecast["y_pred"])


def test_result_does_not_depend_on_data_after_the_decision() -> None:
    full = _series_with_defects(gap_across_decision=False)
    seen = full.loc[: DECISION_TIME - HOUR]

    _assert_same_result(
        _last_cycle(seen, [PAST_EVENT]), _last_cycle(full, [PAST_EVENT])
    )


# bekannte Grenze: die Länge einer Lücke wird über die ganze Reihe gezählt, online wäre
# der Tag davor nicht ausgeschlossen. In S2 und S4 gibt es keine Lücke über Mitternacht
@pytest.mark.xfail(
    strict=True, reason="Lückenlänge hängt von Daten nach der Entscheidung ab"
)
def test_gap_reaching_past_the_decision_is_treated_the_same() -> None:
    full = _series_with_defects(gap_across_decision=True)
    seen = full.loc[: DECISION_TIME - HOUR]

    _assert_same_result(
        _last_cycle(seen, [PAST_EVENT]), _last_cycle(full, [PAST_EVENT])
    )


def test_calendar_entry_known_after_the_decision_changes_nothing() -> None:
    seen = _series_with_defects(gap_across_decision=False).loc[: DECISION_TIME - HOUR]

    _assert_same_result(
        _last_cycle(seen, [PAST_EVENT]),
        _last_cycle(seen, [PAST_EVENT, LATE_EVENT]),
    )
