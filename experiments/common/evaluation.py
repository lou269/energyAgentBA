from __future__ import annotations

from collections.abc import Collection, Mapping

import numpy as np
import pandas as pd

from experiments.common.standard_config import (
    GOLDSTANDARD_EXPECTED,
    LOCAL_TIMEZONE,
    SINGLE_DAY_CLASSIFICATIONS,
    SUSTAINED_CLASSIFICATION,
    ANALYSIS_CONFIG,
)
from src.common.timestamps import local_day_index
from src.evaluation.consistency import missing_evidence_paths
from src.evaluation.text_check import (
    collect_state_values,
    find_violations,
)
from src.structured_state.structured_state_schema import SCALE_NAMES, StructuredState

# Phase über das ganze Fenster, zusätzlich zu vor/ab Cutover
ALL_DAYS = "all_days"

# Wert je Skala in der Reihenfolge von SCALE_NAMES, long_term kein Z-Score, nur Prozentabweichung
SCALE_VALUE_COLUMNS = [
    "long_term_deviation_pct" if scale == "long_term" else f"{scale}_score"
    for scale in SCALE_NAMES
]
SCALE_SUSTAINED_COLUMNS = [
    f"{scale}_sustained" for scale in ANALYSIS_CONFIG.level_shift_scales
]


# Tag seit Ereignis = Tag der Entscheidung, decision_time ist dessen Mitternacht. An diesem Tag meldet das System
# und prognostiziert ihn, eingeordnet wird dabei der Vortag. Einordnung und Adaption zählen deshalb erst ab Tag 1 zum Ereignis
FIRST_ANALYZED_DAY = 1

# eine Ergebniszeile je System, Cutover und Art in Studien auf Standard-Cutovern mit Kontrolllauf (E1, E2)
EVENT_KEYS = ["config", "cutover_date", "kind"]

# Zeile über alle Ereignisse in den Einordnungstabellen
ALL_EVENTS = "all"


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


def add_gate_flags(days: pd.DataFrame) -> pd.DataFrame:
    """Einzeltag-Alarm (Level über normal) und Gate offen wie in gate_classification, aus den Spalten von anomaly.csv"""
    alarm = days["anomaly_level"].notna() & days["anomaly_level"].ne("normal")
    any_sustained = days[SCALE_SUSTAINED_COLUMNS].eq(True).any(axis=1)
    gate_open = alarm | any_sustained | days["value_implausible"].eq(True)

    return days.assign(alarm=alarm, gate_open=gate_open)


def merge_cycle_days(summary: pd.DataFrame, anomaly: pd.DataFrame) -> pd.DataFrame:
    """Je Tag und Config Einordnung und Reset und Prognosefehler aus comparison_summary neben den Spalten aus anomaly.csv, dazu Gate-Flags und new_pattern"""
    # summary hat jeden Tag, anomaly.csv fehlt an Tagen ohne Analyse (z.B. direkt nach einem Reset)
    summary = summary[
        [
            "decision_time",
            "analyzed_day",
            "config",
            "classification",
            "reference_reset",
            "adaption_action",
            "error",
            "explanation",
            "mae_w",
            "mape_pct",
            "day_forecast_w",
            "day_bias_w",
            "day_error_w",
        ]
    ]
    days = summary.merge(
        anomaly, on=["decision_time", "analyzed_day", "config"], how="left"
    )

    return add_gate_flags(days).assign(
        new_pattern=days["classification"].eq("new_pattern")
    )


def join_scale_names(flags: pd.DataFrame, separator: str) -> list[str]:
    # je Zeile die Skalen, deren Flag gesetzt ist, die Spalten folgen level_shift_scales
    return [
        separator.join(
            scale
            for scale, flag in zip(ANALYSIS_CONFIG.level_shift_scales, row)
            if flag
        )
        for row in flags.itertuples(index=False)
    ]


def streak_scale_names(hits: pd.DataFrame) -> pd.Series:
    # Skalen mit anhaltender Abweichung je Zeile, etwa weekly+long_term
    sustained = hits[SCALE_SUSTAINED_COLUMNS].eq(True)

    return pd.Series(join_scale_names(sustained, "+"), index=hits.index)


def detection_scales(hits: pd.DataFrame, single_day: pd.Series) -> pd.Series:
    return hits["dominant_scale"].where(single_day, streak_scale_names(hits))


def add_days_since_cutover(results: pd.DataFrame) -> pd.DataFrame:
    # Entscheidungstag wie days_since_event, hier mit eigenem Cutover je Zeile
    return results.assign(
        days_since_cutover=days_since_date(
            results["decision_time"], results["cutover_date"]
        )
    )


def collect_scenario_results(
    summary: pd.DataFrame,
    anomaly: pd.DataFrame,
    *,
    kind: str,
    cutover_date: str,
    columns: list[str],
) -> pd.DataFrame:
    # Zyklustage eines Szenarios mit Art und Cutover, die Spalten wählt die Studie
    results = merge_cycle_days(summary, anomaly).assign(
        kind=kind, cutover_date=cutover_date
    )

    return results[columns]


def pair_with_control(
    results: pd.DataFrame,
    keys: list[str],
    flags: tuple[str, ...] = ("alarm", "gate_open", "new_pattern"),
) -> pd.DataFrame:
    """Jede Ereignis-Art tageweise neben control, keys enthält days_since_cutover. Im Kreislauf laufen die Reihen nach einem Reset auseinander, bis zur ersten Erkennung bleiben sie vergleichbar"""
    control = results.loc[results["kind"].eq("control"), keys + list(flags)]
    events = results.loc[results["kind"].ne("control")]

    paired = events.merge(control, on=keys, suffixes=("", "_control"))

    # event_<flag>: Flag, den es ohne Ereignis an diesem Tag nicht gegeben hätte
    for flag in flags:
        paired[f"event_{flag}"] = paired[flag] & ~paired[f"{flag}_control"]

    return paired


def summarize_event_response(
    paired: pd.DataFrame, keys: list[str], event_column: str
) -> pd.DataFrame:
    """Erster Tag ab Cutover je keys, an dem event_column gesetzt ist, NaN = nie"""
    after_cutover = paired.loc[paired["days_since_cutover"].ge(FIRST_ANALYZED_DAY)]
    event_days = after_cutover["days_since_cutover"].where(after_cutover[event_column])

    return (
        after_cutover.assign(event_day=event_days)
        .groupby(keys, as_index=False)
        .agg(first_event_day=("event_day", "min"))
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
    counts = flagged.groupby(keys, observed=True, as_index=False).agg(
        days=("classification", "size"),
        notification_days=("notification", "sum"),
        unknown_days=("unknown", "sum"),
    )
    counts["notifications_per_period"] = (
        counts["notification_days"] / counts["days"] * period_days
    )
    counts["unknown_per_period"] = counts["unknown_days"] / counts["days"] * period_days

    return counts


def summarize_latency(
    results: pd.DataFrame,
    runtimes: pd.DataFrame,
    *,
    rule_system: str,
    llm_system: str,
) -> pd.DataFrame:
    """Je Szenario Laufzeit je Tag mit der Regel, LLM-Aufrufe, Ausfalltage und Mehrlaufzeit des LLM-Systems je Aufruf"""
    llm_days = (
        results.loc[results["config"].eq(llm_system)]
        .groupby("scenario")
        .agg(
            days=("config", "size"),
            llm_calls=("classifier_called", "sum"),
            failed_days=("error", "count"),
        )
    )
    runtime = runtimes.pivot(
        index="scenario", columns="config", values="runtime_seconds"
    )
    latency = llm_days.assign(
        rule_seconds_per_day=runtime[rule_system] / llm_days["days"],
        extra_seconds=runtime[llm_system] - runtime[rule_system],
    )
    # ohne Aufruf keine Zeit je Aufruf
    latency["extra_seconds_per_call"] = latency["extra_seconds"] / latency[
        "llm_calls"
    ].replace(0, np.nan)

    return latency.reset_index()


def summarize_paired_differences(
    values: pd.DataFrame, reference: str | int
) -> pd.DataFrame:
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
        summary["mean_delta"].abs() > 2 * summary["delta_standard_error"]  # type: ignore
    )

    return summary.rename_axis("variant").reset_index()


def add_weeks(
    days: pd.DataFrame, week_days: int, day_column: str = "day_since_start"
) -> pd.DataFrame:
    """Woche 1 ab Tag 0 der Spalte day_column, je week_days Tage"""
    return days.assign(week=days[day_column] // week_days + 1)


def summarize_forecast_errors(
    days: pd.DataFrame,
    keys: list[str],
    reference_config: str,
    pair_keys: tuple[str, ...] = ("decision_time",),
) -> pd.DataFrame:
    """Je config und keys Mittel von Tagesfehler (Hauptmaß), MAE und MAPE aus dem Harness, dazu Tagesfehler und MAE gepaart gegen reference_config je Paarung (pair_keys, sonst decision_time). Fasst keys mehrere Läufe zusammen, muss pair_keys den Lauf mit enthalten"""
    rows = []

    for group_values, group in days.groupby(keys):
        means = group.groupby("config").agg(
            mean_day_error_w=("day_error_w", "mean"),
            mean_mae_w=("mae_w", "mean"),
            mean_mape_pct=("mape_pct", "mean"),
        )
        day_error = summarize_paired_differences(
            group.pivot(index=list(pair_keys), columns="config", values="day_error_w"),
            reference_config,
        ).set_index("variant")
        mae = summarize_paired_differences(
            group.pivot(index=list(pair_keys), columns="config", values="mae_w"),
            reference_config,
        ).set_index("variant")["mean_delta"]

        summary = (
            means.join(day_error)
            .assign(mae_delta_w=mae)
            .rename_axis("config")
            .reset_index()
        )
        for key, value in zip(keys, group_values):
            summary[key] = value  # type: ignore
        rows.append(summary)

    return pd.concat(rows, ignore_index=True)


def list_events(events: list | tuple) -> pd.DataFrame:
    """Eine Zeile je Ereignis einer Reihe (Tag ab Cutover, Art): Nummer, Art, Starttag, erster Einordnungstag und erwartete Klasse"""
    return pd.DataFrame(
        {
            "event": range(1, len(events) + 1),
            "kind": [kind for _, kind in events],
            "start_day": [day for day, _ in events],
            "first_day": [day + FIRST_ANALYZED_DAY for day, _ in events],
            "expected": [GOLDSTANDARD_EXPECTED[kind] for _, kind in events],
        }
    )


def list_event_series(
    event_series: Mapping[str, tuple[tuple[int, str], ...]],
) -> pd.DataFrame:
    """Wie list_events für mehrere Reihen, die Nummern laufen über alle Reihen durch und die Spalte series nennt die Reihe"""
    tables = []
    offset = 0
    for series, events in event_series.items():
        table = list_events(events)
        table["event"] += offset
        tables.append(table.assign(series=series))
        offset += len(events)

    return pd.concat(tables, ignore_index=True)


def assign_events(days: pd.DataFrame, event_list: pd.DataFrame) -> pd.Series:
    """Nummer des Ereignisses, das an diesem Tag eingeordnet wird, bis zum ersten Einordnungstag des nächsten. Vor dem ersten Ereignis leer"""
    number = pd.Series(
        np.searchsorted(
            event_list["first_day"], days["days_since_cutover"], side="right"
        ),
        index=days.index,
    )

    return number.astype("Int64").where(number.gt(0))


def find_judged_days(event_days: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    """Je keys der erste Tag, an dem die Einordnung bewertet wird: bei Einzeltag-Ereignissen der Tag first_day mit offenem Gate, bei dauerhaften der erste Tag mit anhaltender Abweichung oder new_pattern, dazu die Klasse an diesem Tag und die Skala, die ihn ausgelöst hat. Ohne Zeile = nicht erkannt"""
    single_day = event_days["expected"].isin(SINGLE_DAY_CLASSIFICATIONS)
    judged = (
        single_day
        & event_days["days_since_cutover"].eq(event_days["first_day"])
        & event_days["gate_open"].eq(True)
    ) | (
        ~single_day
        & (
            event_days["sustained_drift"].eq(True)
            | event_days["classification"].eq(SUSTAINED_CLASSIFICATION)
        )
    )
    judged_days = (
        event_days.loc[judged].sort_values("days_since_cutover").groupby(keys).head(1)
    )
    judged_days = judged_days.assign(
        trigger_scale=detection_scales(
            judged_days, judged_days["expected"].isin(SINGLE_DAY_CLASSIFICATIONS)
        )
    ).rename(columns={"days_since_cutover": "judged_day"})

    return judged_days[keys + ["judged_day", "classification", "trigger_scale"]]


def add_judgement(
    events: pd.DataFrame, judged_days: pd.DataFrame, keys: list[str]
) -> pd.DataFrame:
    """events (keys und expected) neben den Bewertungstagen: erkannt = es gibt einen Bewertungstag, richtig = die Klasse dort ist die erwartete (leer, wenn nicht erkannt)"""
    table = events.merge(judged_days, on=keys, how="left")
    table["detected"] = table["judged_day"].notna()
    table["correct"] = (
        table["classification"]
        .eq(table["expected"])
        .astype("boolean")
        .mask(~table["detected"])
    )

    return table


def spread_over_repeats(
    summary: pd.DataFrame,
    keys: list[str],
    value: str,
    *,
    repeat: str = "cutover_date",
    count_same_direction: bool = False,
    count_improved: bool = False,
    count_detected: bool = False,
) -> pd.DataFrame:
    """Eine Spalte je Wiederholung (Cutover, Starttermin) plus Mittel, bei Differenzen optional die Zahl der Wiederholungen mit demselben Vorzeichen wie das Mittel,
    bei Differenzen mit negativ = besser optional die Zahl der Wiederholungen mit einem Wert unter null,
    bei Erkennungstagen optional die Zahl der Wiederholungen mit einem Tag (NaN = nicht erkannt)
    """
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

    if count_improved:
        wide["improved"] = (
            wide[repeats].lt(0).sum(axis=1).astype(str)
            + "/"
            + wide[repeats].notna().sum(axis=1).astype(str)
        )

    if count_detected:
        wide["detected"] = (
            wide[repeats].notna().sum(axis=1).astype(str) + f"/{len(repeats)}"
        )

    return wide.reset_index()


def check_answer_text(
    text: str,
    state: Mapping[str, object],
    *,
    control_words: Collection[str],
    number_tolerance: float,
    rounding_step: float,
    prompt_numbers: Collection[float] = (),
) -> str:
    quantities, date_parts = collect_state_values(state)
    violations = find_violations(
        text,
        quantities=quantities,
        date_parts=date_parts,
        control_words=control_words,
        number_tolerance=number_tolerance,
        rounding_step=rounding_step,
        prompt_numbers=prompt_numbers,
    )

    return "; ".join(f"{item.kind}: {item.found}" for item in violations)


def check_answer(
    answer: pd.Series,
    state: StructuredState,
    *,
    control_words: Collection[str],
    number_tolerance: float,
    rounding_step: float,
    prompt_numbers: Collection[float],
) -> tuple[str, str]:
    """Textprüfung und Belegprüfung einer Antwort: Verstöße im Text und die Pfade, die zur Klasse fehlen, je als Text, leer = nichts gefunden"""
    text = " ".join(
        answer[column]
        for column in ["explanation", "user_recommendation", "uncertainty"]
    )
    violations = check_answer_text(
        text,
        state,
        control_words=control_words,
        number_tolerance=number_tolerance,
        rounding_step=rounding_step,
        prompt_numbers=prompt_numbers,
    )
    missing = missing_evidence_paths(
        answer["classification"], answer["evidence_paths"].split(";"), state
    )

    return violations, "; ".join(missing)


def attach_states(outputs: pd.DataFrame, states: pd.DataFrame) -> pd.DataFrame:
    """LLM-Antworten neben dem State des Tages, verbunden über Szenario, System und Zeitpunkt in UTC. Die Ausgabe schreibt UTC, der State die lokale Zeit mit Offset"""
    return outputs.assign(
        time=pd.to_datetime(outputs["decision_time"], utc=True)
    ).merge(
        states.assign(time=pd.to_datetime(states["decision_time"], utc=True))[
            ["scenario", "config", "time", "state"]
        ],
        on=["scenario", "config", "time"],
    )


def list_deviation_days(
    results: pd.DataFrame,
    keys: list[str],
    extra_columns: list[str],
    *,
    rule_system: str,
    llm_system: str,
) -> pd.DataFrame:
    """Die Tage, an denen das LLM-System eine andere Klasse hat als die Regel oder ausgefallen ist, je Zeile Klasse und Adaption beider. keys nennt die Läufe, in denen gepaart wird (mit days_since_cutover), extra_columns kommen von der Regel dazu"""
    decision_columns = ["classification", "adaption_action", "error"]
    joined = results.loc[
        results["config"].eq(rule_system),
        keys + ["days_since_cutover"] + extra_columns + decision_columns,
    ].merge(
        results.loc[
            results["config"].eq(llm_system),
            keys + ["days_since_cutover"] + decision_columns,
        ],
        on=keys + ["days_since_cutover"],
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


def summarize_scenario_real_data(
    series: pd.Series,
    *,
    reference_days: int,
    peak_hours: int,
    quantile: float,
    autumn_months: tuple[str, str],
) -> pd.Series:
    """Woran die Stärken von level und peak gemessen sind, dazu der Herbstanstieg
    level = Tagesmittel minus Median der reference_days Tage davor, quantile über die Tage
    peak = mittlere Mehrleistung im stärksten Block aus peak_hours Stunden, je Stunde gegen den Median
    derselben Stunde an den reference_days Tagen davor, quantile über die Tage
    Herbstanstieg = Monatsmittel bis gegen von in Prozent
    """
    days = local_dates(series.index)
    daily = series.groupby(days).mean()
    level = (daily - daily.rolling(reference_days).median().shift(1)).dropna()

    hourly = series.groupby(
        [days, pd.DatetimeIndex(series.index).tz_convert(LOCAL_TIMEZONE).hour]
    ).mean()
    hourly = hourly.unstack()
    excess = hourly - hourly.rolling(reference_days).median().shift(1)
    strongest_block = excess.T.rolling(peak_hours).mean().T.max(axis=1).dropna()

    month_from, month_to = (daily.loc[month].mean() for month in autumn_months)

    return pd.Series(
        {
            "level_w": level.quantile(quantile),
            "peak_w": strongest_block.quantile(quantile),
            "evaluable_days": len(level),
            "autumn_rise_pct": 100 * (month_to / month_from - 1),
        }
    )
