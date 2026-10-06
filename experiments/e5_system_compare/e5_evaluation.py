from dataclasses import dataclass

import numpy as np
import pandas as pd

from experiments.common.evaluation import (
    FIRST_ANALYZED_DAY,
    SCALE_VALUE_COLUMNS,
    SCALE_SUSTAINED_COLUMNS,
    add_days_since_cutover,
    add_overall_rows,
    count_notifications,
    detection_scales,
    merge_cycle_days,
    summarize_latency,
    summarize_paired_differences,
)
from experiments.common.standard_config import (
    GOLDSTANDARD_EXPECTED,
    NOTIFICATION_CLASSIFICATIONS,
    NOTIFICATION_PERIOD_DAYS,
)
from experiments.e5_system_compare.e5_config import SCENARIO_DIRECTORY

# Einzeltag-Ereignisse werden am Ereignistag bewertet, dauerhafte erst mit Drift oder new_pattern,
# vorher kann ein einzelner Tag noch nicht zeigen, dass die Änderung bleibt
FLAG_CLASSIFICATION = "measurement_error"
SINGLE_DAY_CLASSIFICATIONS = ("peak", FLAG_CLASSIFICATION)
DURABLE_CLASSIFICATION = "new_pattern"
# Zeile über alle Ereignisse in der TF2/TF3-Tabelle
ALL_EVENTS = "all"

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


def read_e5_results(
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


def _list_events(events: list | tuple) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "event": range(1, len(events) + 1),
            "kind": [kind for _, kind in events],
            "start_day": [day for day, _ in events],
            "first_day": [day + FIRST_ANALYZED_DAY for day, _ in events],
            "expected": [
                GOLDSTANDARD_EXPECTED[kind.partition("_")[0]] for _, kind in events
            ],
        }
    )


def _assign_events(results: pd.DataFrame, event_list: pd.DataFrame) -> pd.DataFrame:
    # jeder Tag der Ereignisreihe gehört zum Ereignis, das an ihm eingeordnet wird, bis zum ersten Einordnungstag des nächsten
    number = pd.Series(
        np.searchsorted(
            event_list["first_day"], results["days_since_cutover"], side="right"
        ),
        index=results.index,
    )

    return results.assign(
        event=number.astype("Int64").where(
            number.gt(0) & results["series"].eq("events")
        )
    )


def _find_separation_days(results: pd.DataFrame) -> pd.DataFrame:
    # ab dem ersten Tag mit verschiedener Aktion haben die Systeme verschiedene Zustände, davor muss die Prognose bei allen gleich sein
    rows = []
    for (cutover_date, series), group in results.groupby(SERIES_KEYS):
        by_day = group.groupby("days_since_cutover")
        actions_differ = by_day["adaption_action"].nunique().gt(1)
        spread = by_day["mae_w"].max() - by_day["mae_w"].min()

        separation_day = actions_differ.idxmax() if actions_differ.any() else pd.NA
        before = (
            spread if pd.isna(separation_day) else spread[spread.index < separation_day]
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


def _find_judged_days(event_days: pd.DataFrame) -> pd.DataFrame:
    single_day = event_days["expected"].isin(SINGLE_DAY_CLASSIFICATIONS)
    judged = (
        single_day
        & event_days["days_since_cutover"].eq(event_days["first_day"])
        & event_days["gate_open"].eq(True)
    ) | (
        ~single_day
        & (
            event_days["sustained_drift"].eq(True)
            | event_days["classification"].eq(DURABLE_CLASSIFICATION)
        )
    )
    judged_days = (
        event_days.loc[judged]
        .sort_values("days_since_cutover")
        .groupby(EVENT_KEYS)
        .head(1)
    )
    judged_days = judged_days.assign(
        trigger_scale=detection_scales(
            judged_days, judged_days["expected"].isin(SINGLE_DAY_CLASSIFICATIONS)
        )
    ).rename(columns={"days_since_cutover": "judged_day"})

    return judged_days[EVENT_KEYS + ["judged_day", "classification", "trigger_scale"]]


def _count_lead_notifications(
    event_days: pd.DataFrame, judged_days: pd.DataFrame
) -> pd.DataFrame:
    # peak-Meldungen vor dem Bewertungstag einer dauerhaften Änderung zählen als Meldung, nicht als Fehler
    before_judged = event_days.merge(
        judged_days[EVENT_KEYS + ["judged_day"]], on=EVENT_KEYS, how="left"
    )
    before_judged = before_judged.loc[
        before_judged["expected"].eq(DURABLE_CLASSIFICATION)
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
    """Je Cutover, System und Ereignis die Einordnung am Bewertungstag (TF3), ohne Bewertungstag nicht erkannt (TF2), dazu Skala, Vorlauf-Meldungen und Reset"""
    judged_days = _find_judged_days(event_days)
    table = (
        event_days[["cutover_date", "config"]]
        .drop_duplicates()
        .merge(event_list, how="cross")
        .merge(judged_days, on=EVENT_KEYS, how="left")
    )
    table["detected"] = table["judged_day"].notna()
    table["correct"] = (
        table["classification"]
        .eq(table["expected"])
        .astype("boolean")
        .mask(~table["detected"])
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
            separations.loc[
                separations["series"].eq("events"), ["cutover_date", "separation_day"]
            ],
            on="cutover_date",
            how="left",
        )
    )
    table["correct_action"] = (
        table["reset_day"].notna().eq(table["expected"].eq(DURABLE_CLASSIFICATION))
    )
    # vor Beginn des Ereignisses hat schon ein System anders gehandelt, die Einordnung beruht nicht mehr auf demselben Zustand
    table["after_separation"] = (
        table["separation_day"].le(table["start_day"]).fillna(False)
    )
    day_columns = ["judged_day", "lead_notification_days", "reset_day"]
    table[day_columns] = table[day_columns].astype("Int64")

    return table.sort_values(["cutover_date", "event", "config"]).reset_index(drop=True)


def _summarize_criteria(events_table: pd.DataFrame) -> pd.DataFrame:
    """Je System und erwarteter Klasse sowie über alle Ereignisse: erkannt (TF2, ≥ 90 %), unter den erkannten richtig eingeordnet (TF3, ≥ 80 %). Der Festhänger öffnet das Gate über das Flag und zählt deshalb nur in TF3"""
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


def _pair_with_reference(
    window: pd.DataFrame, column: str, reference_system: str
) -> pd.DataFrame:
    return summarize_paired_differences(
        window.pivot(index="days_since_cutover", columns="config", values=column),
        reference_system,
    ).rename(columns={"variant": "config"})


def _compare_forecasts(
    results: pd.DataFrame, durable_start_day: int, reference_system: str
) -> pd.DataFrame:
    """MAE und MAPE ab Beginn der dauerhaften Änderung und im Kontrolllauf ab Cutover, gepaart gegen reference_system"""
    in_window = results["days_since_cutover"].ge(0) & (
        results["series"].eq("control")
        | results["days_since_cutover"].ge(durable_start_day)
    )
    windowed = results.loc[in_window]

    rows = []
    for (cutover_date, series), window in windowed.groupby(SERIES_KEYS):
        mape = _pair_with_reference(window, "mape_pct", reference_system)[
            ["config", "mean_delta"]
        ].rename(columns={"mean_delta": "mape_delta_pct"})
        means = window.groupby("config", as_index=False).agg(
            mean_mae_w=("mae_w", "mean"), mean_mape_pct=("mape_pct", "mean")
        )
        rows.append(
            means.merge(
                _pair_with_reference(window, "mae_w", reference_system),
                on="config",
                how="left",
            )
            .merge(mape, on="config", how="left")
            .assign(
                cutover_date=str(cutover_date),
                series=str(series),
                from_day=window["days_since_cutover"].min(),
            )
        )

    return pd.concat(rows, ignore_index=True)


def _count_notifications_after_detection(
    event_days: pd.DataFrame, events_table: pd.DataFrame, single_day_scales: list[str]
) -> pd.DataFrame:
    detected = events_table.loc[
        events_table["expected"].eq(DURABLE_CLASSIFICATION) & events_table["detected"]
    ]
    after = event_days.merge(detected[EVENT_KEYS + ["judged_day"]], on=EVENT_KEYS)
    after = after.loc[after["days_since_cutover"].gt(after["judged_day"])]

    return count_notifications(
        after.assign(
            sighted=after[[f"{scale}_score" for scale in single_day_scales]]
            .notna()
            .all(axis=1)
        ),
        EVENT_KEYS + ["sighted"],
        notification_classes=NOTIFICATION_CLASSIFICATIONS,
        period_days=NOTIFICATION_PERIOD_DAYS,
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
    *,
    rule_system: str,
    llm_system: str,
) -> pd.DataFrame:
    """Die vorab festgelegten Aussagen aus Kap. 23 je Cutover: Regel besser als Referenz, LLM gleichwertig bzw. besser als Regel"""
    correct = (
        events_table.pivot(
            index=["cutover_date", "event"], columns="config", values="correct"
        )
        .fillna(False)
        .astype(bool)
    )
    rule_events = events_table.loc[events_table["config"].eq(rule_system)]
    control_resets = control.pivot(
        index="cutover_date", columns="config", values="resets"
    )
    rule_forecast = forecast.loc[
        forecast["series"].eq("events") & forecast["config"].eq(rule_system)
    ].set_index("cutover_date")

    decisions = pd.DataFrame(
        {
            "rule_mae_delta_w": rule_forecast["mean_delta"],
            "rule_single_day_resets": rule_events.loc[
                rule_events["expected"].isin(SINGLE_DAY_CLASSIFICATIONS)
            ]
            .groupby("cutover_date")["reset_day"]
            .count(),
            "rule_control_resets": control_resets[rule_system],
            "llm_only_correct": (correct[llm_system] & ~correct[rule_system])
            .groupby(level="cutover_date")
            .sum(),
            "rule_only_correct": (correct[rule_system] & ~correct[llm_system])
            .groupby(level="cutover_date")
            .sum(),
            "llm_extra_control_resets": control_resets[llm_system]
            - control_resets[rule_system],
        }
    )
    decisions["rule_better"] = (
        decisions["rule_mae_delta_w"].lt(0)
        & decisions["rule_single_day_resets"].eq(0)
        & decisions["rule_control_resets"].eq(0)
    )
    decisions["llm_equivalent"] = decisions["rule_only_correct"].eq(0) & decisions[
        "llm_extra_control_resets"
    ].le(0)
    decisions["llm_better"] = decisions["llm_only_correct"].gt(0) & decisions[
        "rule_only_correct"
    ].eq(0)

    return decisions.rename_axis("cutover_date").reset_index()


@dataclass(frozen=True)
class E5Summary:
    events: pd.DataFrame
    criteria: pd.DataFrame
    decisions: pd.DataFrame
    separations: pd.DataFrame
    deviations: pd.DataFrame
    control: pd.DataFrame
    forecast: pd.DataFrame
    notifications: pd.DataFrame
    latency: pd.DataFrame
    answers: pd.DataFrame
    interrupted: bool


def summarize_e5(
    results: pd.DataFrame,
    runtimes: pd.DataFrame,
    llm_outputs: pd.DataFrame,
    *,
    events: list | tuple,
    reference_system: str,
    rule_system: str,
    llm_system: str,
    single_day_scales: list[str],
) -> E5Summary:
    """Alles, was der E5-Report zeigt"""
    event_list = _list_events(events)
    results = _assign_events(results, event_list)
    event_days = results.loc[results["event"].notna()].merge(event_list, on="event")

    separations = _find_separation_days(results)
    events_table = _summarize_events(event_days, event_list, separations)
    control = _summarize_control(results)
    # die Dauerlast kommt als letztes Ereignis
    forecast = _compare_forecasts(
        results,
        int(
            event_list.loc[
                event_list["expected"].eq(DURABLE_CLASSIFICATION), "start_day"
            ].max()
        ),
        reference_system,
    )

    return E5Summary(
        events=events_table,
        criteria=_summarize_criteria(events_table),
        decisions=_evaluate_decision_rules(
            events_table,
            forecast,
            control,
            rule_system=rule_system,
            llm_system=llm_system,
        ),
        separations=separations,
        deviations=_list_deviation_days(
            results, rule_system=rule_system, llm_system=llm_system
        ),
        control=control,
        forecast=forecast,
        notifications=_count_notifications_after_detection(
            event_days, events_table, single_day_scales
        ),
        latency=summarize_latency(
            results, runtimes, rule_system=rule_system, llm_system=llm_system
        ).merge(results[["scenario"] + SERIES_KEYS].drop_duplicates(), on="scenario"),
        answers=_list_llm_answers(results, llm_outputs, rule_system=rule_system),
        interrupted=bool(runtimes["interrupted"].any()),
    )
