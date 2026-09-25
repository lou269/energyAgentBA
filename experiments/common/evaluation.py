from __future__ import annotations

import numpy as np
import pandas as pd

from experiments.common.standard_config import LOCAL_TIMEZONE
from src.common.timestamps import local_day_index

# Phase über das ganze Fenster, zusätzlich zu vor/ab Cutover
ALL_DAYS = "all_days"


# Tag seit Ereignis = Tag der Entscheidung, decision_time ist dessen Mitternacht. An diesem Tag meldet das System
# und prognostiziert ihn, eingeordnet wird dabei der Vortag. Einordnung und Adaption zählen deshalb erst ab Tag 1 zum Ereignis
FIRST_ANALYZED_DAY = 1


def local_dates(times: pd.Series | pd.Index | list) -> pd.DatetimeIndex:
    # lokaler Kalendertag ohne Zeitzone, sonst zählt ein 23-Stunden-Tag über die Zeitumstellung als 0 Tage
    return local_day_index(
        pd.DatetimeIndex(pd.to_datetime(times, utc=True)), LOCAL_TIMEZONE
    ).tz_localize(None)


def add_overall_rows(frame: pd.DataFrame, column: str, overall: str) -> pd.DataFrame:
    # jede Zeile noch einmal mit overall in column, so fällt die Gesamtzahl im groupby gleich mit heraus
    overall_rows = frame.copy()
    overall_rows[column] = overall

    return pd.concat([frame, overall_rows], ignore_index=True)


def days_since_date(times: pd.Series, dates: pd.Series) -> pd.Index:
    # dates sind lokale Kalendertage als Text (Cutover, Starttermin), einer je Zeile
    return (local_dates(times) - pd.DatetimeIndex(pd.to_datetime(dates))).days


def days_since_event(comparison: pd.DataFrame, event_time: pd.Timestamp) -> pd.Index:
    return (
        local_dates(comparison["decision_time"]) - local_dates([event_time])[0]
    ).days


def summarize_classification_detection(
    comparison: pd.DataFrame,
    event_time: pd.Timestamp,
    target_classification: str,
) -> pd.DataFrame:
    """Ab welchem Tag seit event_time ordnet jede Config als target_classification ein, wie oft, wie oft wird adaptiert"""
    days = days_since_event(comparison, event_time)
    post_event = comparison.assign(day_since_event=days).loc[days >= FIRST_ANALYZED_DAY]

    rows: list[dict[str, object]] = []

    for config, group in post_event.groupby("config"):
        matches = group.loc[group["classification"] == target_classification]

        rows.append(
            {
                "config": config,
                "post_event_days": len(group),
                "target_classification": target_classification,
                "target_classification_days": len(matches),
                "first_detection_day": matches["day_since_event"].min(),
                "adaption_count": int((group["adaption_action"] != "none").sum()),
            }
        )

    return (
        pd.DataFrame(rows)
        .astype({"first_detection_day": "Int64"})
        .sort_values("config")
        .reset_index(drop=True)
    )


def count_days_by_period(
    comparison: pd.DataFrame, event_time: pd.Timestamp
) -> pd.DataFrame:
    """Tage je Klassifikation, dazu Adaptionen und Tage ohne gültiges Ergebnis, je config vor und ab dem Tag von event_time"""
    after_event = days_since_event(comparison, event_time) >= FIRST_ANALYZED_DAY
    labeled = comparison.assign(
        period=np.where(after_event, "after_event", "before_event"),
        adaption_days=comparison["adaption_action"].ne("none"),
        failed_days=comparison["error"].notna(),
    )

    totals = labeled.groupby(["config", "period"]).agg(
        days=("config", "size"),
        adaption_days=("adaption_days", "sum"),
        failed_days=("failed_days", "sum"),
    )
    classification_days = pd.crosstab(
        [labeled["config"], labeled["period"]], labeled["classification"]
    )

    return (
        totals.join(classification_days)
        .fillna(0)
        .astype(int)
        .rename_axis(columns=None)
        .reset_index()
    )


def list_decision_events(
    comparison: pd.DataFrame,
    event_time: pd.Timestamp,
    target_classification: str,
) -> pd.DataFrame:
    """Nur die Tage, an denen etwas passiert: target_classification, eine Adaption oder kein gültiges Ergebnis"""
    happened = (
        comparison["classification"].eq(target_classification)
        | comparison["adaption_action"].ne("none")
        | comparison["error"].notna()
    )
    events = comparison.assign(
        day_since_event=days_since_event(comparison, event_time)
    ).loc[happened]

    columns = [
        "day_since_event",
        "analyzed_day",
        "config",
        "classification",
        "adaption_action",
        "adaption_reason",
        "explanation",
        "error",
    ]
    return (
        events[columns]
        .sort_values(["day_since_event", "config"])
        .reset_index(drop=True)
    )


def summarize_mae_before_after(
    comparison: pd.DataFrame, event_time: pd.Timestamp
) -> pd.DataFrame:
    """Mittlerer/Median mae_w vor vs. nach event_time"""
    comparison = comparison.dropna(subset=["mae_w"]).copy()
    comparison["period"] = "before_event"
    # die Prognose startet bei decision_time, hier gehört decision_time == event_time also schon zu danach
    comparison.loc[comparison["decision_time"] >= event_time, "period"] = "after_event"

    return (
        comparison.groupby(["config", "period"])["mae_w"]
        .agg(mean_mae_w="mean", median_mae_w="median", day_count="count")
        .reset_index()
        .sort_values(["config", "period"])
        .reset_index(drop=True)
    )


def count_notifications(
    results: pd.DataFrame,
    keys: list[str],
    *,
    notification_classes: tuple[str, ...],
    period_days: int,
) -> pd.DataFrame:
    """Meldungen je Gruppe, unknown getrennt: dort reicht die Referenz nicht und das System kann nichts sagen"""
    flagged = results.assign(
        notification=results["classification"].isin(notification_classes),
        unknown=results["classification"].eq("unknown"),
    )
    counts = flagged.groupby(keys, as_index=False).agg(
        days=("classification", "size"),
        notification_days=("notification", "sum"),
        unknown_days=("unknown", "sum"),
    )
    counts["notifications_per_period"] = (
        counts["notification_days"] / counts["days"] * period_days
    )
    counts["unknown_per_period"] = counts["unknown_days"] / counts["days"] * period_days

    return counts


def summarize_paired_differences(values: pd.DataFrame, reference: str) -> pd.DataFrame:
    """values: eine Zeile je Paarung (Tag, Origin), eine Spalte je Variante. Differenz jeder Variante zu reference"""
    differences = values.drop(columns=reference).sub(values[reference], axis=0)

    summary = pd.DataFrame(
        {
            "paired_count": differences.count(),
            "mean_delta": differences.mean(),
            "delta_standard_error": differences.sem(),
            "better_share": differences.lt(0).sum() / differences.count(),
        }
    )
    # grobe Faustregel, aufeinanderfolgende Tage sind nicht unabhängig, der Standardfehler also eher zu klein
    summary["exceeds_noise"] = (
        summary["mean_delta"].abs() > 2 * summary["delta_standard_error"]
    )

    return summary.rename_axis("variant").reset_index()


def compare_mae_to_reference(
    comparison: pd.DataFrame, event_time: pd.Timestamp, reference_config: str
) -> pd.DataFrame:
    """Gepaart ab event_time: mae_w jeder config minus mae_w von reference_config am selben decision_time"""
    after_event = comparison.loc[comparison["decision_time"] >= event_time]
    mae = after_event.pivot(index="decision_time", columns="config", values="mae_w")

    return summarize_paired_differences(mae, reference_config).rename(
        columns={"variant": "config"}
    )


def compare_mae_to_reference_after_adaption(
    comparison: pd.DataFrame,
    event_time: pd.Timestamp,
    reference_config: str,
) -> pd.DataFrame:
    """Wie compare_mae_to_reference, aber je config erst ab ihrer ersten Adaption nach event_time"""
    after_event = comparison.loc[
        days_since_event(comparison, event_time) >= FIRST_ANALYZED_DAY
    ]
    adaptions = after_event.loc[after_event["adaption_action"].ne("none")].sort_values(
        "decision_time"
    )
    # der Adaptions-Zyklus baut seine Prognose schon mit dem angepassten Modell, zählt also mit
    first_adaptions = adaptions.groupby("config").head(1)
    first_adaptions = first_adaptions.assign(
        adaption_forecast_day=days_since_event(first_adaptions, event_time)
    )

    mae = comparison.pivot(index="decision_time", columns="config", values="mae_w")
    summaries = []

    for row in first_adaptions.itertuples(index=False):
        phase = mae.loc[mae.index >= row.decision_time, [reference_config, row.config]]
        summaries.append(
            summarize_paired_differences(phase, reference_config).assign(
                adaption_forecast_day=row.adaption_forecast_day,
                mean_mae_w=phase[row.config].mean(),
                reference_mean_mae_w=phase[reference_config].mean(),
            )
        )

    if not summaries:
        return pd.DataFrame(
            columns=[
                "config",
                "paired_count",
                "mean_delta",
                "delta_standard_error",
                "better_share",
                "exceeds_noise",
                "adaption_forecast_day",
                "mean_mae_w",
                "reference_mean_mae_w",
            ]
        )

    return pd.concat(summaries, ignore_index=True).rename(columns={"variant": "config"})


def spread_over_repeats(
    summary: pd.DataFrame,
    keys: list[str],
    value: str,
    *,
    repeat: str = "cutover_date",
    count_same_direction: bool = False,
) -> pd.DataFrame:
    """Eine Spalte je Wiederholung (Cutover, Starttermin) plus Mittel, bei Differenzen optional die Zahl der Wiederholungen mit demselben Vorzeichen wie das Mittel"""
    wide = summary.pivot(index=keys, columns=repeat, values=value).rename_axis(
        columns=None
    )
    repeats = list(wide.columns)
    wide["mean"] = wide[repeats].mean(axis=1)

    # bei wenigen, überlappenden Fenstern ist die gleiche Richtung überall das Einzige, was für einen echten Effekt spricht
    if count_same_direction:
        same_direction = wide[repeats].mul(wide["mean"], axis=0).gt(0).sum(axis=1)
        # ohne jede Differenz gibt es keine Richtung
        wide["same_direction"] = (
            same_direction.astype(str)
            + "/"
            + wide[repeats].notna().sum(axis=1).astype(str)
        ).where(wide["mean"].ne(0))

    return wide.reset_index()
