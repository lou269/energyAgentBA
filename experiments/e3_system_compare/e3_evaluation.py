from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np
import pandas as pd

from experiments.common.evaluation import (
    ALL_EVENTS,
    SCALE_VALUE_COLUMNS,
    SCALE_SUSTAINED_COLUMNS,
    add_days_since_cutover,
    add_weeks,
    add_judgement,
    add_overall_rows,
    assign_events,
    count_notifications,
    find_judged_days,
    list_event_series,
    merge_cycle_days,
    summarize_forecast_errors,
    summarize_latency,
)
from experiments.common.standard_config import (
    FLAG_CLASSIFICATION,
    NOTIFICATION_CLASSIFICATIONS,
    NOTIFICATION_PERIOD_DAYS,
    SINGLE_DAY_CLASSIFICATIONS,
    SUSTAINED_CLASSIFICATION,
)
from experiments.e3_system_compare.e3_config import SCENARIO_DIRECTORY


MEAN_LABEL = "alle Cutover"
# über mehrere Cutover zusammengefasste Tage werden je Cutover, Reihe und Zeitpunkt gepaart
POOL_PAIR_KEYS = ("cutover_date", "series", "decision_time")
SERIES_KEYS = ["cutover_date", "series"]
EVENT_KEYS = ["cutover_date", "config", "event"]

RESULT_COLUMNS = (
    [
        "scenario",
        "series",
        "cutover_date",
        "config",
        "decision_time",
        "analyzed_day",
        "days_since_cutover",
        "classification",
        "classifier_called",
        "adaption_action",
        "error",
        "day_error_w",
        "mae_w",
        "mape_pct",
        "anomaly_level",
        "dominant_scale",
        "alarm",
        "gate_open",
        "sustained_drift",
    ]
    + SCALE_VALUE_COLUMNS
    + SCALE_SUSTAINED_COLUMNS
)


def read_e3_results(
    summary: pd.DataFrame, anomaly: pd.DataFrame, *, series: str, cutover_date: str
) -> pd.DataFrame:
    days = merge_cycle_days(summary, anomaly).assign(
        series=series,
        cutover_date=cutover_date,
        scenario=SCENARIO_DIRECTORY.format(series=series, cutover_date=cutover_date),
    )
    # Regel bzw. LLM wurde gefragt, auch wenn das LLM keine gültige Antwort lieferte
    days["classifier_called"] = days["explanation"].notna() | days["error"].notna()

    return add_days_since_cutover(days)[RESULT_COLUMNS]


def _assign_series_events(results: pd.DataFrame, event_list: pd.DataFrame) -> pd.Series:
    numbers = pd.Series(pd.NA, index=results.index, dtype="Int64")
    for series, table in event_list.groupby("series"):
        rows = results["series"].eq(series)
        numbers.loc[rows] = assign_events(results.loc[rows], table) + (
            table["event"].min() - 1
        )

    return numbers


def _find_separation_days(results: pd.DataFrame) -> pd.DataFrame:
    # ab dem ersten Tag mit verschiedener Aktion haben die Systeme verschiedene Zustände, davor muss die Prognose bei allen gleich sein
    rows = []
    for (cutover_date, series), group in results.groupby(SERIES_KEYS):
        by_day = group.groupby("days_since_cutover")
        actions_differ = by_day["adaption_action"].nunique().gt(1)
        spread = by_day["mae_w"].max() - by_day["mae_w"].min()

        separation_day = actions_differ.idxmax() if actions_differ.any() else pd.NA
        before = (
            spread if pd.isna(separation_day) else spread[spread.index < separation_day]  # type: ignore
        )
        rows.append(
            {
                "cutover_date": cutover_date,
                "series": series,
                "separation_day": separation_day,
                "forecast_identical_before": bool(
                    np.isclose(before.fillna(0), 0).all()
                ),
            }
        )

    return pd.DataFrame(rows).astype({"separation_day": "Int64"})


def _count_lead_notifications(
    event_days: pd.DataFrame, judged_days: pd.DataFrame
) -> pd.DataFrame:
    # peak-Meldungen vor dem Bewertungstag einer dauerhaften Änderung zählen als Meldung, nicht als Fehler
    before_judged = event_days.merge(
        judged_days[EVENT_KEYS + ["judged_day"]], on=EVENT_KEYS, how="left"
    )
    before_judged = before_judged.loc[
        before_judged["expected"].eq(SUSTAINED_CLASSIFICATION)
        & ~before_judged["days_since_cutover"].ge(before_judged["judged_day"])
    ]

    return (
        before_judged.assign(
            notification=before_judged["classification"].isin(
                NOTIFICATION_CLASSIFICATIONS
            )
        )
        .groupby(EVENT_KEYS, as_index=False)
        .agg(lead_notification_days=("notification", "sum"))
    )


def _summarize_events(
    event_days: pd.DataFrame, event_list: pd.DataFrame, separations: pd.DataFrame
) -> pd.DataFrame:
    """Je Cutover, System und Ereignis die Einordnung am Bewertungstag, ohne Bewertungstag nicht erkannt, dazu Skala, Vorlauf-Meldungen und Reset"""
    judged_days = find_judged_days(event_days, EVENT_KEYS)
    table = add_judgement(
        event_days[["cutover_date", "config"]]
        .drop_duplicates()
        .merge(event_list, how="cross"),
        judged_days,
        EVENT_KEYS,
    )

    resets = (
        event_days.loc[event_days["adaption_action"].eq("advance_history_start")]
        .groupby(EVENT_KEYS, as_index=False)
        .agg(reset_day=("days_since_cutover", "min"))
    )
    table = (
        table.merge(
            _count_lead_notifications(event_days, table), on=EVENT_KEYS, how="left"
        )
        .merge(resets, on=EVENT_KEYS, how="left")
        .merge(
            separations[["cutover_date", "series", "separation_day"]],
            on=["cutover_date", "series"],
            how="left",
        )
    )
    table["correct_action"] = (
        table["reset_day"].notna().eq(table["expected"].eq(SUSTAINED_CLASSIFICATION))
    )
    # vor Beginn des Ereignisses hat schon ein System anders gehandelt, die Einordnung beruht nicht mehr auf demselben Zustand
    table["after_separation"] = (
        table["separation_day"].le(table["start_day"]).fillna(False)
    )
    day_columns = ["judged_day", "lead_notification_days", "reset_day"]
    table[day_columns] = table[day_columns].astype("Int64")

    return table.sort_values(["cutover_date", "event", "config"]).reset_index(drop=True)


def _summarize_criteria(events_table: pd.DataFrame) -> pd.DataFrame:
    """Je System und erwarteter Klasse sowie über alle Ereignisse: erkannt (TF1, ≥ 90 %), unter den erkannten richtig eingeordnet (TF2, ≥ 80 %). Der Festhänger öffnet das Gate über das Flag und zählt deshalb nur bei der Einordnung"""
    prefilter_event = events_table["expected"].ne(FLAG_CLASSIFICATION)
    criteria = (
        add_overall_rows(
            events_table.assign(
                prefilter_event=prefilter_event,
                prefilter_detected=prefilter_event & events_table["detected"],
            ),
            "expected",
            ALL_EVENTS,
        )
        .groupby(["config", "expected"], as_index=False)
        .agg(
            events=("event", "size"),
            detected=("detected", "sum"),
            correct=("correct", "sum"),
            prefilter_events=("prefilter_event", "sum"),
            prefilter_detected=("prefilter_detected", "sum"),
        )
    )

    return criteria.assign(
        detection_pct=criteria["prefilter_detected"]
        / criteria["prefilter_events"]
        * 100,
        correct_pct=criteria["correct"] / criteria["detected"] * 100,
    )


def _list_deviation_days(
    results: pd.DataFrame, *, rule_system: str, llm_system: str
) -> pd.DataFrame:
    decision_columns = ["classification", "adaption_action", "error"]
    joined = results.loc[
        results["config"].eq(rule_system),
        SERIES_KEYS
        + ["days_since_cutover", "analyzed_day", "event"]
        + decision_columns,
    ].merge(
        results.loc[
            results["config"].eq(llm_system),
            SERIES_KEYS + ["days_since_cutover"] + decision_columns,
        ],
        on=SERIES_KEYS + ["days_since_cutover"],
        suffixes=("_rule", "_llm"),
    )
    llm_failed = joined["error_llm"].notna()
    differs = (
        joined["classification_rule"]
        .fillna("")
        .ne(joined["classification_llm"].fillna(""))
        | llm_failed
    )

    return (
        joined.assign(llm_failed=llm_failed)
        .loc[differs]
        .drop(columns=["error_rule", "error_llm"])
        .reset_index(drop=True)
    )


def _summarize_control(results: pd.DataFrame) -> pd.DataFrame:
    control = results.loc[results["series"].eq("control")]
    keys = ["cutover_date", "config"]
    resets = (
        control.assign(reset=control["adaption_action"].eq("advance_history_start"))
        .groupby(keys, as_index=False)
        .agg(resets=("reset", "sum"))
    )

    return count_notifications(
        control,
        keys,
        notification_classes=NOTIFICATION_CLASSIFICATIONS,
        period_days=NOTIFICATION_PERIOD_DAYS,
    ).merge(resets, on=keys)


def _window_forecast_days(
    results: pd.DataFrame, durable_start_days: pd.Series
) -> pd.DataFrame:
    """Tage mit dauerhafter Änderung ab deren Beginn (Reihe -> Starttag) und im Kontrolllauf ab Cutover"""
    in_window = results["days_since_cutover"].ge(0) & (
        results["series"].eq("control")
        | results["days_since_cutover"].ge(results["series"].map(durable_start_days))
    )

    return results.loc[in_window]


def _compare_forecasts(windowed: pd.DataFrame, reference_system: str) -> pd.DataFrame:
    """Prognosefehler gegen reference_system je Reihe, in den Reihen mit dauerhafter Änderung ab deren Beginn"""
    from_day = windowed.groupby(SERIES_KEYS, as_index=False).agg(
        from_day=("days_since_cutover", "min")
    )

    return summarize_forecast_errors(windowed, SERIES_KEYS, reference_system).merge(
        from_day, on=SERIES_KEYS
    )


def _pool_forecasts(windowed: pd.DataFrame, reference_system: str) -> pd.DataFrame:
    """Prognosefehler gegen reference_system über alle Cutover der Reihen mit dauerhafter Änderung, alle Tage zusammen"""
    durable = windowed.loc[windowed["series"].ne("control")]

    return summarize_forecast_errors(
        durable, ["series"], reference_system, POOL_PAIR_KEYS
    )


def _compare_forecasts_by_week(
    windowed: pd.DataFrame, reference_system: str, week_days: int
) -> pd.DataFrame:
    """Je Cutover und Woche ab der Dauerlast Tagesfehler und Differenz gegen reference_system, eine Spalte je System, dazu je Woche alle Cutover zusammen"""
    durable = windowed.loc[windowed["series"].ne("control")]
    start = durable.groupby(SERIES_KEYS)["days_since_cutover"].transform("min")
    weeks = add_weeks(
        durable.assign(day_since_start=durable["days_since_cutover"] - start),
        week_days,
    )
    errors = summarize_forecast_errors(weeks, SERIES_KEYS + ["week"], reference_system)
    pooled = summarize_forecast_errors(
        weeks, ["week"], reference_system, POOL_PAIR_KEYS
    ).assign(cutover_date=MEAN_LABEL)
    values = ["mean_day_error_w", "mean_delta"]
    table = pd.concat(
        [
            errors[["cutover_date", "week", "config"] + values],
            pooled[["cutover_date", "week", "config"] + values],
        ]
    ).pivot(index=["cutover_date", "week"], columns="config", values=values)
    table.columns = [f"{value}_{config}" for value, config in table.columns]

    return (
        table.reset_index().sort_values(["week", "cutover_date"]).reset_index(drop=True)
    )


def _count_notifications_after_detection(
    event_days: pd.DataFrame, events_table: pd.DataFrame
) -> pd.DataFrame:
    """Je Cutover und System die Meldungstage nach dem Bewertungstag der Dauerlast, getrennt nach Einzeltag-Klassen und allen Meldungen"""
    detected = events_table.loc[
        events_table["expected"].eq(SUSTAINED_CLASSIFICATION) & events_table["detected"]
    ]
    after = event_days.merge(detected[EVENT_KEYS + ["judged_day"]], on=EVENT_KEYS)
    after = after.loc[after["days_since_cutover"].gt(after["judged_day"])]

    def count(classes: tuple[str, ...]) -> pd.DataFrame:
        return count_notifications(
            after,
            EVENT_KEYS,
            notification_classes=classes,
            period_days=NOTIFICATION_PERIOD_DAYS,
        )[EVENT_KEYS + ["days", "notification_days", "notifications_per_period"]]

    return (
        count(NOTIFICATION_CLASSIFICATIONS)
        .merge(
            count(SINGLE_DAY_CLASSIFICATIONS),
            on=EVENT_KEYS + ["days"],
            suffixes=("", "_single_day"),
        )
        .drop(columns="notifications_per_period_single_day")
    )


def _list_llm_answers(
    results: pd.DataFrame, outputs: pd.DataFrame, *, rule_system: str
) -> pd.DataFrame:
    rule_classes = results.loc[
        results["config"].eq(rule_system),
        ["scenario", "analyzed_day", "classification"],
    ].rename(columns={"classification": "rule_classification"})
    answer_keys = ["scenario", "config", "analyzed_day"]
    days = results[
        answer_keys
        + ["series", "cutover_date", "days_since_cutover", "event", "adaption_action"]
    ]

    return (
        outputs.drop(columns=["decision_time", "evidence_paths"])
        .merge(days, on=answer_keys)
        .merge(rule_classes, on=["scenario", "analyzed_day"])
        .sort_values(SERIES_KEYS + ["days_since_cutover"])
        .reset_index(drop=True)
    )


def _evaluate_decision_rules(
    events_table: pd.DataFrame,
    forecast: pd.DataFrame,
    control: pd.DataFrame,
    notifications: pd.DataFrame,
    *,
    reference_system: str,
    rule_system: str,
    llm_system: str,
) -> pd.DataFrame:
    """Die vorab festgelegten Aussagen aus Kap. 23 je Cutover: Regel und LLM besser als Referenz (belastbar bessere Prognose oder weniger Meldungen, ohne falsche Resets), LLM gleichwertig zur Regel"""
    correct = (
        events_table.pivot(
            index=["cutover_date", "event"], columns="config", values="correct"
        )
        .fillna(False)
        .astype(bool)
    )
    control_resets = control.pivot(
        index="cutover_date", columns="config", values="resets"
    )
    notification_rates = notifications.pivot(
        index="cutover_date", columns="config", values="notifications_per_period"
    ).reindex(columns=[reference_system, rule_system, llm_system])
    columns = {
        "rule_only_correct": (correct[rule_system] & ~correct[llm_system])
        .groupby(level="cutover_date")
        .sum(),
        "llm_extra_control_resets": control_resets[llm_system]
        - control_resets[rule_system],
    }
    for name, system in (("rule", rule_system), ("llm", llm_system)):
        system_events = events_table.loc[events_table["config"].eq(system)]
        system_forecast = forecast.loc[
            forecast["series"].ne("control") & forecast["config"].eq(system)
        ].set_index("cutover_date")
        columns[f"{name}_day_error_delta_w"] = system_forecast["mean_delta"]
        columns[f"{name}_day_error_reliable"] = system_forecast["exceeds_noise"]
        columns[f"{name}_single_day_resets"] = (
            system_events.loc[
                system_events["expected"].isin(SINGLE_DAY_CLASSIFICATIONS)
            ]
            .groupby("cutover_date")["reset_day"]
            .count()
        )
        columns[f"{name}_control_resets"] = control_resets[system]
        columns[f"{name}_notification_delta"] = (
            notification_rates[system] - notification_rates[reference_system]
        )

    decisions = pd.DataFrame(columns)
    for name in ("rule", "llm"):
        decisions[f"{name}_better"] = (
            (
                (
                    decisions[f"{name}_day_error_delta_w"].lt(0)
                    & decisions[f"{name}_day_error_reliable"].eq(True)
                )
                | decisions[f"{name}_notification_delta"].lt(0)
            )
            & decisions[f"{name}_single_day_resets"].eq(0)
            & decisions[f"{name}_control_resets"].eq(0)
        )
    decisions["llm_equivalent"] = decisions["rule_only_correct"].eq(0) & decisions[
        "llm_extra_control_resets"
    ].le(0)

    return decisions.rename_axis("cutover_date").reset_index()


def _summarize_overall(
    decisions: pd.DataFrame,
    events_table: pd.DataFrame,
    pooled_forecast: pd.DataFrame,
    control: pd.DataFrame,
    notifications: pd.DataFrame,
    *,
    reference_system: str,
    rule_system: str,
    llm_system: str,
) -> pd.DataFrame:
    """Je System die Hauptkennzahlen über alle Cutover: Tagesfehler ab Dauerlast über alle Tage der Cutover, Meldungen je Zeitraum nach der Erkennung, Resets sowie die Entscheidungsregeln als Anzahl Cutover. Teilfrage 2 nur in den Zeilen von Regel und LLM"""
    errors = (
        pooled_forecast.set_index("config")
        .assign(
            day_error_delta_two_se_w=lambda frame: 2 * frame["delta_standard_error"]
        )[
            [
                "mean_day_error_w",
                "mean_delta",
                "day_error_delta_two_se_w",
                "exceeds_noise",
            ]
        ]
        .rename(
            columns={
                "mean_day_error_w": "day_error_w",
                "mean_delta": "day_error_delta_w",
                "exceeds_noise": "day_error_reliable",
            }
        )
    )
    counts = notifications.groupby("config")[
        ["days", "notification_days", "notification_days_single_day"]
    ].sum()
    rates = (
        counts[["notification_days", "notification_days_single_day"]].div(
            counts["days"], axis=0
        )
        * NOTIFICATION_PERIOD_DAYS
    )
    rates.columns = ["notifications_per_period", "single_day_notifications_per_period"]
    single_day_events = events_table.loc[
        events_table["expected"].isin(SINGLE_DAY_CLASSIFICATIONS)
    ]
    resets = pd.DataFrame(
        {
            "single_day_resets": single_day_events.groupby("config")[
                "reset_day"
            ].count(),
            "control_resets": control.groupby("config")["resets"].sum(),
        }
    )
    verdicts = pd.DataFrame(
        {
            "better_cutovers": {
                rule_system: decisions["rule_better"].sum(),
                llm_system: decisions["llm_better"].sum(),
            },
            "extra_control_resets": {
                llm_system: decisions["llm_extra_control_resets"].sum()
            },
            "equivalent_cutovers": {llm_system: decisions["llm_equivalent"].sum()},
        }
    )

    return (
        errors.join(rates)
        .join(resets)
        .join(verdicts)
        .assign(cutovers=len(decisions))
        .reindex([reference_system, rule_system, llm_system])
        .rename_axis("config")
        .reset_index()
    )


@dataclass(frozen=True)
class E3Summary:
    events: pd.DataFrame
    criteria: pd.DataFrame
    decisions: pd.DataFrame
    overall: pd.DataFrame
    separations: pd.DataFrame
    deviations: pd.DataFrame
    control: pd.DataFrame
    forecast: pd.DataFrame
    forecast_weeks: pd.DataFrame
    notifications: pd.DataFrame
    latency: pd.DataFrame
    answers: pd.DataFrame
    interrupted: bool


def summarize_e3(
    results: pd.DataFrame,
    runtimes: pd.DataFrame,
    llm_outputs: pd.DataFrame,
    *,
    event_series: Mapping[str, tuple[tuple[int, str], ...]],
    reference_system: str,
    rule_system: str,
    llm_system: str,
    week_days: int,
) -> E3Summary:
    """Alles, was der E3-Report zeigt"""
    event_list = list_event_series(event_series)
    results = results.assign(event=_assign_series_events(results, event_list))
    event_days = results.loc[results["event"].notna()].merge(
        event_list, on=["series", "event"]
    )

    separations = _find_separation_days(results)
    events_table = _summarize_events(event_days, event_list, separations)
    control = _summarize_control(results)
    notifications = _count_notifications_after_detection(event_days, events_table)
    windowed = _window_forecast_days(
        results,
        event_list.loc[event_list["expected"].eq(SUSTAINED_CLASSIFICATION)]
        .groupby("series")["start_day"]
        .min(),
    )
    forecast = _compare_forecasts(windowed, reference_system)

    decisions = _evaluate_decision_rules(
        events_table,
        forecast,
        control,
        notifications,
        reference_system=reference_system,
        rule_system=rule_system,
        llm_system=llm_system,
    )

    return E3Summary(
        events=events_table,
        criteria=_summarize_criteria(events_table),
        decisions=decisions,
        separations=separations,
        deviations=_list_deviation_days(
            results, rule_system=rule_system, llm_system=llm_system
        ),
        overall=_summarize_overall(
            decisions,
            events_table,
            _pool_forecasts(windowed, reference_system),
            control,
            notifications,
            reference_system=reference_system,
            rule_system=rule_system,
            llm_system=llm_system,
        ),
        control=control,
        forecast=forecast,
        forecast_weeks=_compare_forecasts_by_week(
            windowed, reference_system, week_days
        ),
        notifications=notifications,
        latency=summarize_latency(
            results, runtimes, rule_system=rule_system, llm_system=llm_system
        ).merge(results[["scenario"] + SERIES_KEYS].drop_duplicates(), on="scenario"),
        answers=_list_llm_answers(results, llm_outputs, rule_system=rule_system),
        interrupted=bool(runtimes["interrupted"].any()),
    )
