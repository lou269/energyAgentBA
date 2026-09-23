# python -m pytest tests/unit/component_studies/k5_adaptation_strategies/test_k5_evaluation.py -v

import pandas as pd

from experiments.component_studies.k5_adaptation_strategies.k5_evaluation import pair_with_none


def _results(strategy: str, trigger_day: float, mae: list[float], kind: str = "step") -> pd.DataFrame:
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
