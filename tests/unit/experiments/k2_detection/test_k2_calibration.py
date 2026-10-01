import pandas as pd

from experiments.k2_detection.k2_calibration import summarize_streak_point


def _gated(kind: str, new_pattern_days: list[int]) -> pd.DataFrame:
    days = list(range(-2, 25))
    return pd.DataFrame(
        {
            "mode": "isolated",
            "variant": "DETECTOR",
            "cutover_date": "2014-02-12",
            "kind": kind,
            "days_since_cutover": days,
            "alarm": False,
            "gate_open": False,
            "new_pattern": [day in new_pattern_days for day in days],
        }
    )


def test_streak_point_counts_onsets() -> None:
    gated = pd.concat(
        [
            # eine Drift über fünf Tage ist ein falsches new_pattern, nicht fünf
            _gated("control", list(range(10, 15))),
            # Beginn an Tag 5 liegt in der Toleranz um den der Kontrolle, erst Tag 18 ist die eigene Erkennung
            _gated("step", list(range(5, 15)) + [18, 19]),
        ],
        ignore_index=True,
    )

    point = summarize_streak_point(gated, control_reset_tolerance_days=7).iloc[0]

    assert point["false_new_pattern"] == 1
    assert point["first_event_new_pattern_day"] == 18
