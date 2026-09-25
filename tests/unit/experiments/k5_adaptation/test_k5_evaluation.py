# python -m pytest tests/unit/experiments/k5_adaptation/test_k5_evaluation.py -v

import pandas as pd

from experiments.k5_adaptation.k5_evaluation import (
    summarize_excess_without_action,
    net_of_control,
    pair_with_none,
)


def _results(
    strategy: str, trigger_day: float, mae: list[float], kind: str = "step"
) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "kind": kind,
            "cutover_date": "2014-04-15",
            "strategy": strategy,
            "trigger_day": trigger_day,
            "days_since_cutover": list(range(len(mae))),
            "mae_w": mae,
        }
    )


def test_actions_are_paired_with_none_on_the_same_scenario_and_day() -> None:
    results = pd.concat(
        [
            _results("none", float("nan"), [100.0, 100.0, 150.0, 140.0, 130.0]),
            # control darf nicht in die Paarung von step rutschen
            _results("none", float("nan"), [90.0] * 5, kind="control"),
            _results("cut", 2.0, [100.0, 100.0, 120.0, 110.0, 105.0]),
        ],
        ignore_index=True,
    )

    paired = pair_with_none(results, evaluation_days=2)

    assert paired["days_since_trigger"].tolist() == [0, 1]
    assert paired["mae_none_w"].tolist() == [150.0, 140.0]
    assert paired["mae_delta_w"].tolist() == [-30.0, -30.0]


def test_net_effect_subtracts_what_the_same_action_does_without_a_change() -> None:
    summary = pd.DataFrame(
        {
            "kind": ["step", "control", "step"],
            "trigger_day": [6.0, 6.0, 12.0],
            "strategy": "cut",
            "cutover_date": "2014-04-15",
            "mae_delta_w": [-5.0, -1.0, -2.0],
        }
    )

    net = net_of_control(summary)

    # ohne control-Zeile zum selben Trigger gibt es keinen Nettowert
    assert net["trigger_day"].tolist() == [6.0]
    assert net["net_delta_w"].tolist() == [-4.0]


def test_summarize_excess_without_action_is_none_minus_control_per_week() -> None:
    days = list(range(-1, 8))
    results = pd.concat(
        [
            _results("none", float("nan"), [100.0] * 9, kind="control").assign(
                days_since_cutover=days
            ),
            _results(
                "none", float("nan"), [100.0] + [130.0] * 7 + [110.0], kind="step"
            ).assign(days_since_cutover=days),
        ],
        ignore_index=True,
    )

    excess = summarize_excess_without_action(results).to_dict("index")

    # Tag -1 liegt vor dem Cutover und zählt nicht
    assert excess["step"] == {0: 30.0, 1: 10.0}
