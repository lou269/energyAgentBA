# python -m pytest tests/unit/experiments/common/test_standard_scenarios.py -v

import pandas as pd
import pytest

from experiments.common import standard_scenarios
from experiments.common.standard_config import LOCAL_TIMEZONE, STANDARD_CONFIG
from experiments.common.standard_scenarios import add_stuck_flags, add_stuck_value
from src.common.timestamps import local_midnight_utc

CUTOVER = "2014-04-15"


@pytest.fixture(autouse=True)
def _constant_mains(monkeypatch: pytest.MonkeyPatch) -> None:
    index = pd.date_range("2013-12-01", "2014-07-31", freq="1h", tz="UTC")
    flags = pd.Series(False, index=index)
    monkeypatch.setattr(
        standard_scenarios,
        "load_target",
        lambda split: (pd.Series(200.0, index=index), flags, flags),
    )
    # der ganze Testzeitraum gilt als Abschnitt
    monkeypatch.setattr(
        standard_scenarios,
        "load_split_bounds",
        lambda split: (index[0], index[-1]),
    )


def _build(kinds: tuple[str, ...], margin_after_days: int = 30) -> dict:
    return standard_scenarios.build_standard_scenarios(
        CUTOVER,
        kinds,
        split="validation",
        margin_before_days=14,
        margin_after_days=margin_after_days,
    )


def test_all_kinds_share_decision_times_and_differ_only_from_the_cutover() -> None:
    scenarios = _build(("control", "scaled"))
    cutover_time = local_midnight_utc(CUTOVER, LOCAL_TIMEZONE)
    control = scenarios["control"].target_series
    scaled = scenarios["scaled"].target_series

    assert list(scenarios) == ["control", "scaled"]
    assert scenarios["scaled"].decision_times == scenarios["control"].decision_times
    decision_times = scenarios["control"].decision_times
    assert decision_times[0] == cutover_time - pd.Timedelta(days=14)
    assert decision_times[-1] == cutover_time + pd.Timedelta(days=30)

    before = control.index < cutover_time
    assert (scaled[before] == control[before]).all()
    assert scaled[~before].tolist() == pytest.approx(
        [200.0 * STANDARD_CONFIG.scale_factor] * int((~before).sum())
    )


def test_ramps_reach_their_factor_after_their_days() -> None:
    scenarios = _build(("ramp_28", "ramp_56_down"), margin_after_days=60)
    cutover_time = local_midnight_utc(CUTOVER, LOCAL_TIMEZONE)
    fast = scenarios["ramp_28"].target_series
    slow = scenarios["ramp_56_down"].target_series

    assert (fast[fast.index < cutover_time] == 200.0).all()
    # nach der halben Dauer die Hälfte, danach das volle Endniveau
    assert fast[cutover_time + pd.Timedelta(days=14)] == pytest.approx(
        200.0 * (1 + (STANDARD_CONFIG.scale_factor - 1) / 2)
    )
    assert fast[cutover_time + pd.Timedelta(days=40)] == pytest.approx(
        200.0 * STANDARD_CONFIG.scale_factor
    )
    assert slow[cutover_time + pd.Timedelta(days=28)] == pytest.approx(
        200.0 * (1 + (STANDARD_CONFIG.scale_factor_down - 1) / 2)
    )


def test_peak_and_level_change_only_the_cutover_day() -> None:
    scenarios = _build(("control", "peak", "level"))
    control = scenarios["control"].target_series
    peak = scenarios["peak"].target_series - control
    level = scenarios["level"].target_series - control

    assert (peak > 0).sum() == STANDARD_CONFIG.peak_hours
    assert peak[peak > 0].eq(STANDARD_CONFIG.peak_extra_w).all()
    assert peak[peak > 0].index[0] == local_midnight_utc(
        CUTOVER, LOCAL_TIMEZONE
    ) + pd.Timedelta(hours=STANDARD_CONFIG.peak_start_hour)
    assert (level > 0).sum() == 24
    assert level[level > 0].eq(STANDARD_CONFIG.level_extra_w).all()


def test_stuck_value() -> None:
    index = pd.date_range("2020-01-01", periods=24, freq="1h", tz="UTC")
    series = pd.Series(range(24), index=index, dtype=float)

    stuck = add_stuck_value(series, index[10], hours=8)

    assert stuck.iloc[10:18].eq(9.0).all()
    assert stuck.iloc[:10].equals(series.iloc[:10])
    assert stuck.iloc[18:].equals(series.iloc[18:])


def test_stuck_flags() -> None:
    index = pd.date_range("2020-01-01", periods=48, freq="1h", tz="UTC")
    series = pd.Series(range(48), index=index, dtype=float)
    never = pd.Series(False, index=index)

    flags = add_stuck_flags(add_stuck_value(series, index[10], hours=12), never, never)

    # ab der sechsten Stunde gleich dem Vorgänger, wie bei den echten Daten
    assert flags[flags].index.tolist() == index[15:22].tolist()


def test_stuck_flags_imputed() -> None:
    index = pd.date_range("2020-01-01", periods=12, freq="1h", tz="UTC")
    constant = pd.Series(100.0, index=index)
    never = pd.Series(False, index=index)
    always = pd.Series(True, index=index)

    assert add_stuck_flags(constant, never, never).any()
    assert not add_stuck_flags(constant, always, never).any()
