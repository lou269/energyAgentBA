# python -m pytest tests/unit/experiments/k4_adaptation/test_k4_masking.py -v

import pandas as pd

from experiments.k4_adaptation.k4_evaluation import pair_masking
from experiments.k4_adaptation.k4_oracle import replay_actions, replay_masked_days


def _decisions() -> pd.DataFrame:
    # lokale Mitternacht in BST, also 23:00 UTC am Vortag
    return pd.DataFrame(
        {
            "decision_time": pd.to_datetime(
                [
                    "2014-07-01T23:00:00+00:00",
                    "2014-07-02T23:00:00+00:00",
                    "2014-07-03T23:00:00+00:00",
                ],
                utc=True,
            ),
            "classification": ["peak", "normal", "new_pattern"],
            "adaption_action": ["none", "none", "advance_history_start"],
            "mae_sys2_w": [100.0, 110.0, 120.0],
            "kind": "control",
            "cutover_date": "2014-07-15",
        }
    )


def test_masked_day_is_the_day_evaluated_at_the_decision() -> None:
    masked = replay_masked_days(_decisions(), ("peak", "low"))
    assert masked is not None

    # Entscheidung um Mitternacht zum 2. Juli wertet den 1. Juli aus
    assert [day.date().isoformat() for day in masked] == ["2014-07-01"]
    assert replay_masked_days(_decisions(), ()) is None


def test_only_resets_are_replayed_as_cut() -> None:
    actions = replay_actions(_decisions())

    assert actions == {pd.Timestamp("2014-07-03T23:00:00+00:00"): "cut"}


def test_masking_is_paired_with_replay_on_the_same_day() -> None:
    decisions = _decisions()
    results = pd.concat(
        [
            decisions[["kind", "cutover_date", "decision_time"]].assign(
                strategy="replay",
                mae_w=[100.0, 110.0, 120.0],
                day_error_w=[10.0, float("nan"), 12.0],
            ),
            decisions[["kind", "cutover_date", "decision_time"]].assign(
                strategy="mask",
                mae_w=[100.0, 104.0, 120.0],
                day_error_w=[4.0, float("nan"), 12.0],
            ),
        ],
        ignore_index=True,
    ).assign(days_since_cutover=[-14, -13, -12] * 2)

    paired = pair_masking(results, decisions, ("peak", "low"), ("mae_w", "day_error_w"))

    assert paired["mae_w_delta"].tolist() == [0.0, -6.0, 0.0]
    # ein Tag ohne Tagesfehler bleibt NaN und wird erst in der Zusammenfassung ausgelassen
    assert paired["day_error_w_delta"].dropna().tolist() == [-6.0, 0.0]
    assert paired["replay_matches_sys2"].all()
    assert paired["masked_day"].tolist() == [True, False, False]
