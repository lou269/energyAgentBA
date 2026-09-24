import pandas as pd

from experiments.shared_analysis import forecast_days_since_event
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
        days_since_cutover=forecast_days_since_event(
            oracle_results, cutover_time, local_timezone
        ),
    )


def pair_with_none(results: pd.DataFrame, evaluation_days: int) -> pd.DataFrame:
    """Jede Aktion tageweise neben none auf denselben Daten, nur die ersten evaluation_days Prognosetage ab dem Trigger"""
    keys = ["kind", "cutover_date", "days_since_cutover"]

    none = results.loc[results["strategy"].eq("none"), [*keys, "mae_w"]].rename(
        columns={"mae_w": "mae_none_w"}
    )
    paired = results.loc[results["strategy"].ne("none")].merge(none, on=keys)

    # Tag 0 ist der erste Prognosetag nach der Aktion
    paired["days_since_trigger"] = paired["days_since_cutover"] - paired["trigger_day"]
    paired["mae_delta_w"] = paired["mae_w"] - paired["mae_none_w"]

    return paired.loc[paired["days_since_trigger"].between(0, evaluation_days - 1)]


def summarize_after_trigger(paired: pd.DataFrame) -> pd.DataFrame:
    # step: Nutzen bei echter Änderung, control: Kosten eines Fehlalarms
    return paired.groupby(
        ["kind", "trigger_day", "strategy", "cutover_date"], as_index=False
    ).agg(
        days=("mae_w", "count"),
        mae_w=("mae_w", "mean"),
        mae_none_w=("mae_none_w", "mean"),
        mae_delta_w=("mae_delta_w", "mean"),
    )


def net_of_control(summary: pd.DataFrame) -> pd.DataFrame:
    """Effekt bei echter Änderung abzüglich dessen, was dieselbe Aktion ohne Änderung bewirkt"""
    keys = ["trigger_day", "strategy", "cutover_date"]
    control = summary.loc[summary["kind"].eq("control"), [*keys, "mae_delta_w"]].rename(
        columns={"mae_delta_w": "control_delta_w"}
    )

    net = summary.loc[summary["kind"].ne("control")].merge(control, on=keys)
    net["net_delta_w"] = net["mae_delta_w"] - net["control_delta_w"]

    return net


def excess_without_reaction(results: pd.DataFrame) -> pd.DataFrame:
    """Mehrfehler von none gegenüber control je Woche seit Cutover, zeigt, wie schnell Rolling 30 eine Änderung von selbst lernt"""
    none = results.loc[
        results["strategy"].eq("none") & results["days_since_cutover"].ge(0)
    ]
    mae = none.pivot(
        index=["cutover_date", "days_since_cutover"], columns="kind", values="mae_w"
    )

    excess = mae.drop(columns="control").sub(mae["control"], axis=0).reset_index()
    excess["week_since_cutover"] = excess["days_since_cutover"] // 7

    return (
        excess.melt(
            id_vars=["cutover_date", "week_since_cutover"],
            value_vars=[kind for kind in mae.columns if kind != "control"],
            var_name="kind",
            value_name="excess_w",
        )
        .groupby(["kind", "week_since_cutover"], as_index=False)[["excess_w"]]
        .mean()
    )


def error_curve(paired: pd.DataFrame) -> pd.DataFrame:
    """Fehlerverlauf je Woche nach dem Trigger, gemittelt über die Cutover, daran lässt sich die Erholungszeit ablesen"""
    weekly = paired.assign(week_since_trigger=paired["days_since_trigger"] // 7)

    return weekly.groupby(
        ["kind", "trigger_day", "strategy", "week_since_trigger"], as_index=False
    )[["mae_delta_w"]].mean()
