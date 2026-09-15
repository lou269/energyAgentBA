# python -m pytest tests/unit/proposal_experiments/e1_new_device -v

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from experiments.proposal_experiments.e1_new_device.e1_scenarios import build_device_scenario
from src.config.project_config import ProjectConfig
from src.pipeline.comparison_harness import run_comparison
from src.pipeline.cycle_variants import SYS_VARIANTS


PROJECT_ROOT = ProjectConfig().project_root
DEVICE_METER_KEY = "H1_M5"


def _mains(hours: int) -> pd.Series:
    index = pd.date_range("2024-01-01", periods=hours, freq="1h", tz="UTC")
    hour_of_day = index.hour.to_numpy()
    values = 200.0 + 50.0 * np.sin(2 * np.pi * hour_of_day / 24) + 10.0
    return pd.Series(values, index=index, name="target")


def _device(hours: int, *, load_w: float = 30.0) -> pd.Series:
    # Gerät läuft real jeden Tag um Mitternacht, ist also schon im Mains-Rohsignal enthalten
    index = pd.date_range("2024-01-01", periods=hours, freq="1h", tz="UTC")
    values = np.where(index.hour == 0, load_w, 0.0)
    return pd.Series(values, index=index, name=DEVICE_METER_KEY)


def test_before_cutover_device_load_is_subtracted_from_mains() -> None:
    mains = _mains(240)
    device = _device(240)
    cutover_time = mains.index[100]

    scenario = build_device_scenario(
        mains, device, DEVICE_METER_KEY, cutover_time=cutover_time, coldstart_hours=24, decision_times=(mains.index[150],),
    )

    before = mains.index[96]  # aktive Gerätestunde (Tag 4, 00:00), liegt vor dem Cutover
    assert device.loc[before] > 0.0
    assert scenario.target_series.loc[before] == pytest.approx(mains.loc[before] - device.loc[before])


def test_at_and_after_cutover_mains_is_left_unchanged() -> None:
    mains = _mains(240)
    device = _device(240)
    cutover_time = mains.index[96]  # selbst eine aktive Gerätestunde -> prüft die Inklusiv-Grenze direkt

    scenario = build_device_scenario(
        mains, device, DEVICE_METER_KEY, cutover_time=cutover_time, coldstart_hours=24, decision_times=(mains.index[150],)
    )

    for timestamp in (cutover_time, mains.index[120]):
        assert device.loc[timestamp] > 0.0
        assert scenario.target_series.loc[timestamp] == pytest.approx(mains.loc[timestamp])


@pytest.mark.parametrize("bad_cutover_offset", [0, -1])
def test_cutover_time_must_lie_strictly_inside_the_series(bad_cutover_offset: int) -> None:
    mains = _mains(240)
    device = _device(240)

    with pytest.raises(ValueError, match="cutover_time"):
        build_device_scenario(
            mains, device, DEVICE_METER_KEY, cutover_time=mains.index[bad_cutover_offset],
            coldstart_hours=24, decision_times=(mains.index[150],),
        )


def test_run_comparison_completes_across_the_cutover(tmp_path: Path) -> None:
    mains = _mains(480)
    device = _device(480)
    coldstart_hours = 200
    decision_times = tuple(pd.date_range(start=mains.index[coldstart_hours] + pd.Timedelta(hours=1), periods=5, freq="24h", tz="UTC"))
    cutover_time = decision_times[2]  # liegt zwischen dem 2. und 3. Zyklus -> beide Seiten werden durchlaufen

    scenario = build_device_scenario(
        mains, device, DEVICE_METER_KEY,
        cutover_time=cutover_time, coldstart_hours=coldstart_hours, decision_times=decision_times,
    )

    config = {"SYS2": SYS_VARIANTS["SYS2"]}
    result = run_comparison(scenario, config, tmp_path / "run", PROJECT_ROOT)

    assert len(result) == len(decision_times)