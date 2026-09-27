from dataclasses import dataclass

import numpy as np
import pandas as pd

from experiments.common.evaluation import (
    ALL_DAYS,
    add_overall_rows,
    days_since_event,
    spread_over_repeats,
)
from experiments.common.standard_config import LOCAL_TIMEZONE
from src.common.timestamps import local_midnight_utc

KEYS = ["kind", "trigger_day", "strategy"]


def label_oracle_results(
    oracle_results: pd.DataFrame,
    *,
    kind: str,
    cutover_date: str,
    strategy: str,
    trigger_day: int | None,
) -> pd.DataFrame:
    # Entscheidungstag, an ihm wird auch prognostiziert
    cutover_time = local_midnight_utc(cutover_date, LOCAL_TIMEZONE)

    return oracle_results.assign(
        kind=kind,
        cutover_date=cutover_date,
        strategy=strategy,
        trigger_day=trigger_day,
        days_since_cutover=days_since_event(oracle_results, cutover_time),
    )


def pair_with_none(results: pd.DataFrame, evaluation_days: int) -> pd.DataFrame:
    """Jede Aktion tageweise neben none auf denselben Daten, nur die ersten evaluation_days Prognosetage ab dem Trigger"""
    keys = ["kind", "cutover_date", "days_since_cutover"]

    none = results.loc[results["strategy"].eq("none"), keys + ["mae_w"]].rename(
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
    control = summary.loc[summary["kind"].eq("control"), keys + ["mae_delta_w"]].rename(
        columns={"mae_delta_w": "control_delta_w"}
    )

    net = summary.loc[summary["kind"].ne("control")].merge(control, on=keys)
    net["net_delta_w"] = net["mae_delta_w"] - net["control_delta_w"]

    return net


def summarize_excess_without_action(results: pd.DataFrame) -> pd.DataFrame:
    """Mehrfehler von none gegenüber control, Zeilen = Ereignis, Spalten = Woche seit Cutover. Zeigt, wie schnell Rolling 30 eine Änderung von selbst lernt"""
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
        .pivot(index="kind", columns="week_since_cutover", values="excess_w")
    )


def summarize_error_curve(paired: pd.DataFrame) -> pd.DataFrame:
    """Fehlerverlauf je Woche nach dem Trigger, gemittelt über die Cutover, daran lässt sich die Erholungszeit ablesen"""
    weekly = paired.assign(week_since_trigger=paired["days_since_trigger"] // 7)

    return weekly.groupby(
        ["kind", "trigger_day", "strategy", "week_since_trigger"], as_index=False
    )[["mae_delta_w"]].mean()


def summarize_net_effect(net: pd.DataFrame) -> pd.DataFrame:
    table = spread_over_repeats(net, KEYS, "net_delta_w", count_same_direction=True)
    # relativ zum MAE ohne Aktion, damit sich die Größenordnung neben ~130 W einordnen lässt
    mae_none = net.groupby(KEYS, as_index=False)["mae_none_w"].mean()
    table = table.merge(mae_none, on=KEYS)
    table["mean_pct"] = table["mean"] / table["mae_none_w"] * 100

    return table.drop(columns="mae_none_w")


def summarize_false_alarm(summary: pd.DataFrame) -> pd.DataFrame:
    control = summary.loc[summary["kind"].eq("control")]

    return spread_over_repeats(control, KEYS, "mae_delta_w", count_same_direction=True)


# Teil 2: peak/low für Prophet ausblenden


def read_sys2_decisions(
    summary: pd.DataFrame, *, kind: str, cutover_date: str
) -> pd.DataFrame:
    summary = summary.assign(
        decision_time=pd.to_datetime(summary["decision_time"], utc=True)
    )

    return (
        summary[["decision_time", "classification", "adaption_action", "mae_w"]]
        .rename(columns={"mae_w": "mae_sys2_w"})
        .assign(kind=kind, cutover_date=cutover_date)
    )


def pair_masking(
    results: pd.DataFrame,
    decisions: pd.DataFrame,
    masked_classifications: tuple[str, ...],
) -> pd.DataFrame:
    """replay und mask tageweise nebeneinander, dazu die SYS2-Entscheidung desselben Tages"""
    keys = ["kind", "cutover_date", "decision_time"]

    paired = (
        results.pivot(
            index=keys + ["days_since_cutover"], columns="strategy", values="mae_w"
        )
        .rename(columns={"replay": "mae_replay_w", "mask": "mae_mask_w"})
        .reset_index()
        .merge(decisions[keys + ["classification", "mae_sys2_w"]], on=keys)
    )

    paired["mae_delta_w"] = paired["mae_mask_w"] - paired["mae_replay_w"]
    # replay muss SYS2 exakt nachbilden, sonst ist das Nachspielen falsch
    paired["replay_matches_sys2"] = np.isclose(
        paired["mae_replay_w"], paired["mae_sys2_w"], equal_nan=True
    )
    paired["masked_day"] = paired["classification"].isin(masked_classifications)

    return paired


def summarize_masking_by_cutover(paired: pd.DataFrame, early_days: int) -> pd.DataFrame:
    # control: Nutzen bei echten Ausreißern, step: Kosten, wenn der Beginn einer echten Änderung erst als peak ausgeblendet wird
    phase = pd.cut(
        paired["days_since_cutover"],
        [-np.inf, -1, early_days - 1, np.inf],
        labels=["before_cutover", "early", "late"],
    )
    phased = add_overall_rows(paired.assign(phase=phase.astype(str)), "phase", ALL_DAYS)

    return phased.groupby(
        ["kind", "cutover_date", "phase"], as_index=False, sort=False
    ).agg(
        days=("mae_delta_w", "count"),
        masked_days=("masked_day", "sum"),
        mae_replay_w=("mae_replay_w", "mean"),
        mae_mask_w=("mae_mask_w", "mean"),
        mae_delta_w=("mae_delta_w", "mean"),
        replay_matches_sys2=("replay_matches_sys2", "mean"),
    )


def summarize_masking(summary: pd.DataFrame) -> pd.DataFrame:
    keys = ["kind", "phase"]
    table = spread_over_repeats(summary, keys, "mae_delta_w", count_same_direction=True)
    counts = summary.groupby(keys, as_index=False, sort=False).agg(
        days=("days", "sum"), masked_days=("masked_days", "sum")
    )

    return counts.merge(table, on=keys).sort_values("kind", kind="stable")


@dataclass(frozen=True)
class StrategyKeyFigures:
    kind: str
    earliest: int
    latest: int
    # Netto-Effekt je Aktion beim frühesten Trigger
    earliest_rows: pd.DataFrame
    latest_best_w: float
    excess_first_week_w: float
    excess_late_week_w: float


def summarize_strategy_key_figures(
    net: pd.DataFrame, excess: pd.DataFrame, *, kind: str, late_week: int
) -> StrategyKeyFigures:
    """Netto-Effekt beim frühesten Trigger je Aktion, bester Effekt beim spätesten, Mehrfehler ohne Aktion"""
    event = net.loc[net["kind"].eq(kind)]
    earliest, latest = int(event["trigger_day"].min()), int(event["trigger_day"].max())

    return StrategyKeyFigures(
        kind=kind,
        earliest=earliest,
        latest=latest,
        earliest_rows=event.loc[event["trigger_day"].eq(earliest)],
        latest_best_w=event.loc[event["trigger_day"].eq(latest), "mean"].min(),
        # Spalten sind die Wochen seit Cutover, Zeilen die Ereignisse
        excess_first_week_w=excess[0][kind],
        excess_late_week_w=excess[late_week][kind],
    )


@dataclass(frozen=True)
class MaskingKeyFigures:
    # je Szenario über alle Tage, mit dem MAE ohne Ausblenden daneben
    overall: pd.DataFrame
    replay_match_pct: float


def summarize_masking_key_figures(
    summary: pd.DataFrame, table: pd.DataFrame, paired: pd.DataFrame
) -> MaskingKeyFigures:
    overall = table.loc[table["phase"].eq(ALL_DAYS)]
    mae_replay = (
        summary.loc[summary["phase"].eq(ALL_DAYS)]
        .groupby("kind")["mae_replay_w"]
        .mean()
    )

    return MaskingKeyFigures(
        overall=overall.assign(mae_replay_w=overall["kind"].map(mae_replay)),
        # replay muss SYS2 exakt nachbilden, sonst ist das Nachspielen falsch
        replay_match_pct=paired["replay_matches_sys2"].mean() * 100,
    )
