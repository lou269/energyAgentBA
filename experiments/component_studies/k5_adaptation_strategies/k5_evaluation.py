import pandas as pd

from experiments.proposal_experiments.shared_analysis import forecast_days_since_event
from src.common.timestamps import local_midnight_utc


def label_oracle_results(
    oracle_results: pd.DataFrame,
    *,
    kind: str,
    cutover_date: str,
    strategy: str,
    trigger_day: int | None,
    local_timezone: str,
) -> pd.DataFrame:
    # anders als in K3 zählt hier der prognostizierte Tag, nicht der zuletzt analysierte
    cutover_time = local_midnight_utc(cutover_date, local_timezone)

    return oracle_results.assign(
        kind=kind,
        cutover_date=cutover_date,
        strategy=strategy,
        trigger_day=trigger_day,
        days_since_cutover=forecast_days_since_event(oracle_results, cutover_time, local_timezone),
    )


def pair_with_none(results: pd.DataFrame, evaluation_days: int) -> pd.DataFrame:
    """Jede Aktion tageweise neben none auf denselben Daten, nur die ersten evaluation_days Prognosetage ab dem Trigger"""
    keys = ["kind", "cutover_date", "days_since_cutover"]

    none = results.loc[results["strategy"].eq("none"), [*keys, "mae_w"]].rename(columns={"mae_w": "mae_none_w"})
    paired = results.loc[results["strategy"].ne("none")].merge(none, on=keys)

    # Tag 0 ist der erste Prognosetag nach der Aktion
    paired["days_since_trigger"] = paired["days_since_cutover"] - paired["trigger_day"]
    paired["mae_delta_w"] = paired["mae_w"] - paired["mae_none_w"]

    return paired.loc[paired["days_since_trigger"].between(0, evaluation_days - 1)]


def summarize_after_trigger(paired: pd.DataFrame) -> pd.DataFrame:
    # step: Nutzen bei echter Änderung, control: Kosten eines Fehlalarms
    return paired.groupby(["kind", "trigger_day", "strategy", "cutover_date"], as_index=False).agg(
        days=("mae_w", "count"),
        mae_w=("mae_w", "mean"),
        mae_none_w=("mae_none_w", "mean"),
        mae_delta_w=("mae_delta_w", "mean"),
    )


def error_curve(paired: pd.DataFrame) -> pd.DataFrame:
    """Fehlerverlauf je Tag nach dem Trigger, gemittelt über die Cutover, daran lässt sich die Erholungszeit ablesen"""
    return paired.groupby(["kind", "trigger_day", "strategy", "days_since_trigger"], as_index=False)[
        ["mae_w", "mae_none_w", "mae_delta_w"]
    ].mean()
