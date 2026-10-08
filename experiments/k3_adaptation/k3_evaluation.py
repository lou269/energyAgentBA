from dataclasses import dataclass

import pandas as pd

from experiments.common.evaluation import (
    ALL_DAYS,
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


def pair_with_none(
    results: pd.DataFrame, evaluation_days: int, metric: str
) -> pd.DataFrame:
    """Jede Aktion tageweise neben none auf denselben Daten, nur die ersten evaluation_days Prognosetage ab dem Trigger. metric ist eine Fehlerspalte der Ergebnisse (mae_w, day_error_w), daneben entstehen <metric>_none und <metric>_delta"""
    keys = ["kind", "cutover_date", "days_since_cutover"]

    none = results.loc[results["strategy"].eq("none"), keys + [metric]].rename(
        columns={metric: f"{metric}_none"}
    )
    paired = results.loc[results["strategy"].ne("none")].merge(none, on=keys)

    # Tag 0 ist der erste Prognosetag nach der Aktion
    paired["days_since_trigger"] = paired["days_since_cutover"] - paired["trigger_day"]
    paired[f"{metric}_delta"] = paired[metric] - paired[f"{metric}_none"]

    return paired.loc[paired["days_since_trigger"].between(0, evaluation_days - 1)]


def summarize_after_trigger(paired: pd.DataFrame, metric: str) -> pd.DataFrame:
    grouped = paired.groupby(["kind", "trigger_day", "strategy", "cutover_date"])
    summary = grouped[[metric, f"{metric}_none", f"{metric}_delta"]].mean()
    summary["days"] = grouped[metric].count()

    return summary.reset_index()


def summarize_bias_after_cutover(
    results: pd.DataFrame, first_day: int, last_day: int
) -> pd.DataFrame:
    """Prognose minus Messung beim Tagesmittel ohne Aktion, Mittel über die Cutover, Zeilen = Ereignis, Spalten = Tag seit Cutover. Zeigt, ob und wie schnell das Modell eine Änderung von selbst aufnimmt"""
    none = results.loc[
        results["strategy"].eq("none")
        & results["days_since_cutover"].between(first_day, last_day)
    ]

    return none.pivot_table(
        index="kind", columns="days_since_cutover", values="day_bias_w", aggfunc="mean"
    )


def summarize_error_curve(paired: pd.DataFrame, metric: str) -> pd.DataFrame:
    """Fehlerverlauf je Woche nach der Aktion, gemittelt über die Cutover, daran lässt sich die Erholungszeit ablesen"""
    weekly = paired.assign(week_since_trigger=paired["days_since_trigger"] // 7)

    return weekly.groupby(
        ["kind", "trigger_day", "strategy", "week_since_trigger"], as_index=False
    )[[f"{metric}_delta"]].mean()


def summarize_effect(summary: pd.DataFrame, metric: str) -> pd.DataFrame:
    table = spread_over_repeats(summary, KEYS, f"{metric}_delta", count_improved=True)
    # relativ zum Fehler ohne Aktion, damit sich die Größenordnung einordnen lässt
    none = summary.groupby(KEYS, as_index=False)[f"{metric}_none"].mean()
    table = table.merge(none, on=KEYS)
    table["mean_pct"] = table["mean"] / table[f"{metric}_none"] * 100

    return table.drop(columns=f"{metric}_none")


# Teil 2: Ereignistag für Prophet ausblenden


def pair_masking(results: pd.DataFrame, metrics: tuple[str, ...]) -> pd.DataFrame:
    """none und mask tageweise nebeneinander auf derselben Reihe. Je Fehlerspalte entstehen <metric>_none, <metric>_mask und <metric>_delta"""
    keys = ["kind", "cutover_date", "decision_time", "days_since_cutover"]

    wide = results.pivot(index=keys, columns="strategy", values=list(metrics))
    wide.columns = [f"{metric}_{strategy}" for metric, strategy in wide.columns]
    paired = wide.reset_index()

    for metric in metrics:
        paired[f"{metric}_delta"] = paired[f"{metric}_mask"] - paired[f"{metric}_none"]

    return paired


def summarize_masking_by_cutover(
    paired: pd.DataFrame, first_day: int, last_day: int, window_days: int, metric: str
) -> pd.DataFrame:
    # nur Tage, an denen eine Spitze im Trainingsfenster steckt: ab dem Tag nach der ersten bis window_days nach der letzten.
    # Davor und danach trainieren beide Läufe auf denselben Tagen und die Differenz ist null
    in_window = paired["days_since_cutover"].between(
        first_day + 1, last_day + window_days
    )
    # Tage ohne Wert (beim Tagesfehler unvollständige Tage) zählen nirgends mit
    valid = paired.loc[in_window].dropna(subset=[f"{metric}_delta"])

    grouped = valid.groupby(["kind", "cutover_date"], sort=False)
    summary = grouped[[f"{metric}_none", f"{metric}_mask", f"{metric}_delta"]].mean()
    summary["days"] = grouped[f"{metric}_delta"].count()

    return summary.reset_index()


def summarize_masking(summary: pd.DataFrame, metric: str) -> pd.DataFrame:
    """Je Szenario: Differenz je Cutover und im Mittel, dazu der Fehler ohne Ausblenden (none) und die Zahl der Tage"""
    table = spread_over_repeats(
        summary, ["kind"], f"{metric}_delta", count_improved=True
    )
    counts = summary.groupby("kind", as_index=False, sort=False).agg(
        days=("days", "sum"), none=(f"{metric}_none", "mean")
    )

    return counts.merge(table, on="kind")


@dataclass(frozen=True)
class StrategyKeyFigures:
    kind: str
    earliest: int
    latest: int
    # Differenz zu keiner Aktion je Aktion beim frühesten Trigger
    earliest_rows: pd.DataFrame
    latest_best_w: float


def summarize_strategy_key_figures(
    effect: pd.DataFrame, *, kind: str
) -> StrategyKeyFigures:
    """Differenz zu keiner Aktion beim frühesten Trigger je Aktion, beste Differenz beim spätesten"""
    event = effect.loc[effect["kind"].eq(kind)]
    earliest, latest = int(event["trigger_day"].min()), int(event["trigger_day"].max())

    return StrategyKeyFigures(
        kind=kind,
        earliest=earliest,
        latest=latest,
        earliest_rows=event.loc[event["trigger_day"].eq(earliest)],
        latest_best_w=event.loc[event["trigger_day"].eq(latest), "mean"].min(),
    )


def summarize_masking_key_figures(
    summary: pd.DataFrame, table: pd.DataFrame, metric: str
) -> pd.DataFrame:
    """Je Szenario über alle Tage, mit dem Fehler ohne Ausblenden (none) daneben"""
    overall = table.loc[table["phase"].eq(ALL_DAYS)]
    none = (
        summary.loc[summary["phase"].eq(ALL_DAYS)]
        .groupby("kind")[f"{metric}_none"]
        .mean()
    )

    return overall.assign(none=overall["kind"].map(none))
