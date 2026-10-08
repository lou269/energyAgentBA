from dataclasses import replace

import pandas as pd

from experiments.common.evaluation import SCALE_SUSTAINED_COLUMNS
from src.adaption.adaption_policy import adaption_policy
from src.common.timestamps import local_midnight_utc, shift_local_days
from src.config.config_forecasting import NumericalAnalysisConfig
from src.context.calendar_context import build_calendar_context
from src.llm.gate import gate_classification
from src.llm.rule_based_classifier import rule_based_classify
from src.numerical_analysis.daily_analysis import (
    LEVEL_SHIFT_VALUE_COLUMNS,
    add_level_shift_streaks,
    compute_analysis_row,
)
from src.structured_state.builder import build_structured_state


def with_thresholds(
    config: NumericalAnalysisConfig, weekly: float, long_term: float
) -> NumericalAnalysisConfig:
    return replace(
        config,
        weekly_streak_threshold=weekly,
        long_term_streak_threshold_pct=long_term,
    )


def _score_row(
    series: pd.Series,
    history_start: pd.Timestamp,
    decision_time: pd.Timestamp,
    *,
    config: NumericalAnalysisConfig,
    cache: dict,
    local_timezone: str,
) -> pd.Series | None:
    # die Scores hängen nur von der Reihe und Beginn der Referenz ab, nicht von den Streak-Schwellen
    key = (history_start, decision_time)
    if key not in cache:
        history = series.loc[
            (series.index >= history_start) & (series.index < decision_time)
        ]
        cache[key] = compute_analysis_row(
            history,
            target_timestamp=decision_time - pd.Timedelta(hours=1),
            config=config,
            local_timezone=local_timezone,
        )

    return cache[key]


def level_shift_values(
    series: pd.Series,
    analysis_days: pd.DatetimeIndex,
    config: NumericalAnalysisConfig,
    *,
    cache: dict,
    local_timezone: str,
) -> pd.DataFrame:
    # Werte der Niveau-Skalen ohne Reset, die Referenz läuft ab Beginn der Reihe
    history_start = series.index[0]
    values = {}
    for day in analysis_days:
        row = _score_row(
            series,
            history_start,
            local_midnight_utc(day, local_timezone, days_offset=1),
            config=config,
            cache=cache,
            local_timezone=local_timezone,
        )
        if row is not None:
            values[day] = {
                scale: row[LEVEL_SHIFT_VALUE_COLUMNS[scale]]
                for scale in config.level_shift_scales
            }

    return pd.DataFrame.from_dict(values, orient="index")


def run_chain(
    series: pd.Series,
    analysis_days: pd.DatetimeIndex,
    config: NumericalAnalysisConfig,
    *,
    cache: dict,
    local_timezone: str,
    calendar_lookback_days: int,
    calendar_lookahead_days: int,
) -> pd.DataFrame:
    # Analyse, Streak, Einordnung nach Regel und Reset wie im Zyklus, ohne Prognose
    # -> cache darf über Läufe mit anderen Streak-Schwellen derselben Reihe geteilt werden
    history_start = series.index[0]
    score_history = pd.DataFrame()
    records = []

    for day in analysis_days:
        decision_time = local_midnight_utc(day, local_timezone, days_offset=1)
        row = _score_row(
            series,
            history_start,
            decision_time,
            config=config,
            cache=cache,
            local_timezone=local_timezone,
        )
        if row is None:
            continue

        row, score_history = add_level_shift_streaks(
            row.copy(), score_history, config=config, local_timezone=local_timezone
        )
        state = build_structured_state(
            decision_time=decision_time,
            analysis_row=row,
            calendar_context=build_calendar_context(
                [],
                source_available=False,
                source="none",
                retrieved_at=decision_time,
                decision_time=decision_time,
                window_start=shift_local_days(
                    decision_time, -calendar_lookback_days, local_timezone
                ),
                window_end=shift_local_days(
                    decision_time, calendar_lookahead_days, local_timezone
                ),
                local_timezone=local_timezone,
            ),
            local_timezone=local_timezone,
        )
        classification = (
            gate_classification(state)
            or rule_based_classify(
                state,
                local_timezone=local_timezone,
                min_sustained_scales=config.min_sustained_scales,
            ).classification
        )
        action = adaption_policy(
            classification,
            state,
            streak_tolerance_window_days=config.streak_tolerance_window_days,
            window_exclusion=False,
            local_timezone=local_timezone,
        )
        reset = action.kind == "advance_history_start"
        if reset:
            assert action.new_history_start is not None
            history_start = action.new_history_start
            score_history = pd.DataFrame()

        record = {
            "analyzed_day": day,
            "reset": reset,
            "alarm": row["anomaly_level"] != "normal",
            "anomaly_score": row["anomaly_score"],
        }
        for column in SCALE_SUSTAINED_COLUMNS:
            record[column] = bool(row.get(column, False))
        records.append(record)

    return pd.DataFrame(records)
