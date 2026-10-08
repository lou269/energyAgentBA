# python -m pytest tests/unit/experiments/k3_adaptation/test_k3_evaluation.py -v

import pandas as pd

from experiments.k3_adaptation.k3_evaluation import (
    pair_with_none,
    summarize_bias_after_cutover,
)


def _results(
    strategy: str, trigger_day: float, mae: list[float], kind: str = "scaled"
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
            # control darf nicht in die Paarung von scaled rutschen
            _results("none", float("nan"), [90.0] * 5, kind="control"),
            _results("cut", 2.0, [100.0, 100.0, 120.0, 110.0, 105.0]),
        ],
        ignore_index=True,
    )

    paired = pair_with_none(results, evaluation_days=2, metric="mae_w")

    assert paired["days_since_trigger"].tolist() == [0, 1]
    assert paired["mae_w_none"].tolist() == [150.0, 140.0]
    assert paired["mae_w_delta"].tolist() == [-30.0, -30.0]


def test_bias_after_cutover_averages_the_cutovers_without_action() -> None:
    rows = []
    for cutover, bias in [
        ("2014-04-15", [-100.0, -40.0]),
        ("2014-07-15", [-80.0, -20.0]),
    ]:
        for day, value in zip([0, 1], bias):
            rows.append(
                {
                    "kind": "scaled",
                    "cutover_date": cutover,
                    "strategy": "none",
                    "days_since_cutover": day,
                    "day_bias_w": value,
                }
            )
    # Aktionen und Tage außerhalb des Fensters zählen nicht
    rows.append({**rows[0], "strategy": "cut", "day_bias_w": 999.0})
    rows.append({**rows[0], "days_since_cutover": 5, "day_bias_w": 999.0})

    bias = summarize_bias_after_cutover(pd.DataFrame(rows), 0, 1)

    assert bias.loc["scaled"].tolist() == [-90.0, -30.0]  # type: ignore
