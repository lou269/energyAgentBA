# python -m pytest tests/unit/experiments/k3_adaptation/test_k3_masking.py -v

import pandas as pd

from experiments.k3_adaptation.k3_evaluation import (
    pair_masking,
    summarize_masking_by_cutover,
)


def _results() -> pd.DataFrame:
    # lokale Mitternacht in BST, also 23:00 UTC am Vortag
    keys = pd.DataFrame(
        {
            "decision_time": pd.to_datetime(
                [
                    "2014-07-14T23:00:00+00:00",
                    "2014-07-15T23:00:00+00:00",
                    "2014-07-16T23:00:00+00:00",
                    "2014-08-25T23:00:00+00:00",
                ],
                utc=True,
            ),
            "kind": "peak",
            "cutover_date": "2014-07-15",
            "days_since_cutover": [-1, 0, 1, 41],
        }
    )

    return pd.concat(
        [
            keys.assign(
                strategy="none",
                mae_w=[100.0, 110.0, 120.0, 130.0],
                day_error_w=[10.0, float("nan"), 12.0, 14.0],
            ),
            keys.assign(
                strategy="mask",
                mae_w=[100.0, 104.0, 118.0, 130.0],
                day_error_w=[10.0, float("nan"), 9.0, 14.0],
            ),
        ],
        ignore_index=True,
    )


def test_masking_is_paired_with_none_on_the_same_day() -> None:
    paired = pair_masking(_results(), ("mae_w", "day_error_w"))

    assert paired["mae_w_delta"].tolist() == [0.0, -6.0, -2.0, 0.0]
    # ein Tag ohne Tagesfehler bleibt NaN und wird erst in der Zusammenfassung ausgelassen
    assert paired["day_error_w_delta"].dropna().tolist() == [0.0, -3.0, 0.0]


def test_peaks_count_in_window_until_the_window_after_the_last_one() -> None:
    paired = pair_masking(_results(), ("mae_w", "day_error_w"))

    # Spitzen an Tag 0 und 10, Fenster 30 Tage: Tag 1 bis 40 im Fenster, Tag 41 danach
    summary = summarize_masking_by_cutover(paired, 0, 10, 30, "day_error_w")
    by_phase = summary.set_index("phase")

    assert by_phase.loc["in_window", "day_error_w_delta"] == -3.0
    assert by_phase.loc["before_peak", "days"] == 1
    assert by_phase.loc["after_window", "days"] == 1
