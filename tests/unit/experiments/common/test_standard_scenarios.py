# python -m pytest tests/unit/experiments/common/test_standard_scenarios.py -v

import pandas as pd
import pytest

from experiments.common import standard_scenarios
from experiments.common.standard_config import LOCAL_TIMEZONE, STANDARD_CONFIG
from src.common.timestamps import local_midnight_utc

CUTOVER = "2014-04-15"


@pytest.fixture(autouse=True)
def _constant_mains(monkeypatch: pytest.MonkeyPatch) -> None:
    index = pd.date_range("2013-12-01", "2014-07-31", freq="1h", tz="UTC")
    flags = pd.Series(False, index=index)
    monkeypatch.setattr(
        standard_scenarios,
        "load_target",
        lambda: (pd.Series(200.0, index=index), flags, flags),
    )


def test_all_kinds_share_decision_times_and_differ_only_from_the_cutover() -> None:
    scenarios = standard_scenarios.build_standard_scenarios(
        CUTOVER, ("control", "step", "scaled")
    )
    cutover_time = local_midnight_utc(CUTOVER, LOCAL_TIMEZONE)
    control = scenarios["control"].target_series
    step = scenarios["step"].target_series
    scaled = scenarios["scaled"].target_series

    assert list(scenarios) == ["control", "step", "scaled"]
    assert (
        scenarios["step"].decision_times
        == scenarios["control"].decision_times
        == scenarios["scaled"].decision_times
    )

    before = control.index < cutover_time
    assert (step[before] == control[before]).all()
    assert (
        step[control.index >= cutover_time] == 200.0 + STANDARD_CONFIG.step_injection_w
    ).all()
    assert scaled[control.index >= cutover_time].tolist() == pytest.approx(
        [200.0 * STANDARD_CONFIG.scale_factor]
        * int((control.index >= cutover_time).sum())
    )


def test_only_the_requested_kinds_are_built() -> None:
    assert list(
        standard_scenarios.build_standard_scenarios(CUTOVER, ("control", "step"))
    ) == ["control", "step"]


def test_strength_in_the_name_sets_the_step_and_the_ramp_length() -> None:
    scenarios = standard_scenarios.build_standard_scenarios(
        CUTOVER, ("step_30", "ramp_28")
    )
    cutover_time = local_midnight_utc(CUTOVER, LOCAL_TIMEZONE)
    step = scenarios["step_30"].target_series
    ramp = scenarios["ramp_28"].target_series

    assert (step[step.index >= cutover_time] == 230.0).all()
    assert (ramp[ramp.index < cutover_time] == 200.0).all()
    # nach 14 Tagen die Hälfte, ab 28 Tagen das volle Endniveau
    assert ramp[cutover_time + pd.Timedelta(days=14)] == pytest.approx(
        200.0 * (1 + (STANDARD_CONFIG.scale_factor - 1) / 2)
    )
    assert ramp[
        ramp.index >= cutover_time + pd.Timedelta(days=28)
    ].tolist() == pytest.approx(
        [200.0 * STANDARD_CONFIG.scale_factor]
        * int((ramp.index >= cutover_time + pd.Timedelta(days=28)).sum())
    )


def test_peak_adds_the_extra_power_on_the_cutover_day_only() -> None:
    scenarios = standard_scenarios.build_standard_scenarios(
        CUTOVER, ("control", "peak", "peak_6")
    )
    extra = scenarios["peak"].target_series - scenarios["control"].target_series
    longer = scenarios["peak_6"].target_series - scenarios["control"].target_series

    assert (extra > 0).sum() == STANDARD_CONFIG.peak_hours
    assert extra[extra > 0].eq(STANDARD_CONFIG.peak_extra_w).all()
    assert extra[extra > 0].index[0] == local_midnight_utc(
        CUTOVER, LOCAL_TIMEZONE
    ) + pd.Timedelta(hours=STANDARD_CONFIG.peak_start_hour)
    # gleiche Leistung, nur länger
    assert (longer > 0).sum() == 6
    assert longer.max() == STANDARD_CONFIG.peak_extra_w
