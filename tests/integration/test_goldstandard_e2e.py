# python -m pytest tests/integration/test_goldstandard_e2e.py -v
#
# Goldstandard-Fälle durch den Zyklus (Gate, State, Regel, Adaption), SYS3 mit Fake-CLient

import json
from collections.abc import Mapping
from dataclasses import replace
from functools import partial

import numpy as np
import pandas as pd
import pytest

from experiments.common.standard_config import GOLDSTANDARD_EXPECTED
from experiments.common.standard_scenarios import add_stuck_flags, build_kind_series
from src.config.config_forecasting import CycleConfig, LLMConfig, SYS_VARIANTS
from src.context.calendar_context import build_calendar_context
from src.common.timestamps import shift_local_days
from src.adaption.adaption_policy import AdaptionAction
from src.llm.calendar_tool import CALENDAR_TOOL_NAME
from src.llm.client import ModelMetadata, ToolCall, ToolCallResponse
from src.llm.llm_schema import SCHEMA_VERSION
from src.pipeline.daily_cycle import CycleResult, CycleState, run_cycle

TIMEZONE = "Europe/London"
# Winter, lokale Zeit gleich UTC. Der Cutover ist Tag 60 der Reihe
CUTOVER = pd.Timestamp("2024-03-01", tz="UTC")
COLDSTART_DAYS = 60
FOLLOW_DAYS = 60
LLM_PROMPT = "Ordne den Tag ein."

SYS3_FAKE = replace(
    SYS_VARIANTS["SYS3"], llm_config=LLMConfig(model="test-model", max_attempts=1)
)
# CTX2: der Kalender kommt erst, wenn das Modell das Tool aufruft
SYS3_TOOL_FAKE = replace(
    SYS_VARIANTS["SYS3_TOOL"],
    llm_config=LLMConfig(model="test-model", max_attempts=1, calendar_tool=True),
)

# Aktion der Adaption je erwarteter Klasse
EXPECTED_ACTION = {
    "normal": "none",
    "peak": "none",
    "new_pattern": "advance_history_start",
    "measurement_error": "exclude_window",
}


def _calm_series(days: int, seed: int = 5) -> pd.Series:
    hours = days * 24
    index = pd.date_range("2024-01-01", periods=hours, freq="1h", tz="UTC")
    day_of_series = np.arange(hours) // 24
    jitter_by_day = np.random.default_rng(seed).normal(0.0, 5.0, size=days)
    values = (
        200.0
        + 2.0 * np.sin(2 * np.pi * index.hour.to_numpy() / 24)
        + jitter_by_day[day_of_series]
    )
    return pd.Series(values, index=index, name="target")


class _FixedAnswerClient:
    def __init__(
        self, answer: dict[str, object], asks_for_calendar: bool = False
    ) -> None:
        self.answer = answer
        self.asks_for_calendar = asks_for_calendar
        self.calls = 0

    def generate_json(self, **kwargs: object) -> str:
        self.calls += 1
        return json.dumps(self.answer)

    def request_tool_calls(self, **kwargs: object) -> ToolCallResponse:
        calls: list[ToolCall] = (
            [{"name": CALENDAR_TOOL_NAME, "arguments": {}}]
            if self.asks_for_calendar
            else []
        )
        return {"content": "", "tool_calls": calls}

    def get_model_metadata(self, model: str) -> ModelMetadata:
        return {"name": model, "digest": None}

    def unload_model(self, model: str) -> None:
        pass

    def close(self) -> None:
        pass


def _action(result: CycleResult) -> AdaptionAction:
    assert result.adaption_action is not None
    return result.adaption_action


def _answer(classification: str, evidence_path: str) -> dict[str, object]:
    return {
        "schema_version": SCHEMA_VERSION,
        "classification": classification,
        "explanation": "Test",
        "evidence_references": [{"path": evidence_path}],
        "user_recommendation": "Keine Aktion nötig.",
        "uncertainty": "Gering.",
    }


def _vacation_event() -> dict[str, str]:
    return {
        "event_id": "urlaub",
        "title": "Urlaub",
        "start": CUTOVER.isoformat(),
        "end": (CUTOVER + pd.Timedelta(days=FOLLOW_DAYS)).isoformat(),
        "known_at": (CUTOVER - pd.Timedelta(days=1)).isoformat(),
    }


def _calendar_context(decision_time: pd.Timestamp, events: list[Mapping[str, object]]):
    return build_calendar_context(
        events,
        source_available=bool(events),
        source="test" if events else "none",
        retrieved_at=decision_time,
        decision_time=decision_time,
        window_start=decision_time - pd.Timedelta(hours=24),
        window_end=decision_time + pd.Timedelta(hours=24),
        local_timezone=TIMEZONE,
    )


def _run(
    kind: str,
    days: int,
    config: CycleConfig = SYS_VARIANTS["SYS2"],
    llm_client: _FixedAnswerClient | None = None,
    events: list[Mapping[str, object]] | None = None,
) -> list[CycleResult]:
    series = build_kind_series(
        _calm_series(COLDSTART_DAYS + FOLLOW_DAYS), CUTOVER, kind
    )
    no_flags = pd.Series(False, index=series.index)
    implausible = (
        add_stuck_flags(series, no_flags, no_flags) if kind == "stuck" else no_flags
    )
    state = CycleState(
        history=series.loc[: CUTOVER - pd.Timedelta(hours=1)],
        prophet_model=None,
        model_history=None,
        model_fitted_at=None,
    )
    use_tool = config.llm_config is not None and config.llm_config.calendar_tool
    results = []
    decision_time = CUTOVER
    for _ in range(days):
        start = state.history.index[-1] + pd.Timedelta(hours=1)
        decision_time = shift_local_days(decision_time, 1, TIMEZONE)
        new_observations = series.loc[start : decision_time - pd.Timedelta(hours=1)]
        result, state = run_cycle(
            state,
            new_observations,
            decision_time,
            config,
            local_timezone=TIMEZONE,
            llm_client=llm_client,
            llm_prompt=LLM_PROMPT,
            calendar_context=_calendar_context(
                decision_time, [] if use_tool else events or []
            ),
            calendar_lookup=(
                partial(_calendar_context, decision_time, events or [])
                if use_tool
                else None
            ),
            calendar_tool_prompt=LLM_PROMPT if use_tool else None,
            new_value_implausible=implausible.loc[new_observations.index],
        )
        results.append(result)

    return results


def test_control_stays_normal_without_action() -> None:
    results = _run("control", days=20)

    assert {result.classification for result in results} == {
        GOLDSTANDARD_EXPECTED["control"]
    }
    assert {_action(result).kind for result in results} == {"none"}


@pytest.mark.parametrize("kind", ["peak", "stuck"])
def test_single_day_events_are_classified_on_their_day(kind: str) -> None:
    first = _run(kind, days=1)[0]
    expected = GOLDSTANDARD_EXPECTED[kind]

    assert first.classification == expected
    assert _action(first).kind == EXPECTED_ACTION[expected]


@pytest.mark.parametrize("kind", ["scaled", "scaled_down"])
def test_sustained_level_change_resets_once_in_both_directions(kind: str) -> None:
    results = _run(kind, days=FOLLOW_DAYS)
    expected = GOLDSTANDARD_EXPECTED[kind]
    classifications = [result.classification for result in results]

    assert expected in classifications
    first = classifications.index(expected)
    assert _action(results[first]).kind == EXPECTED_ACTION[expected]
    # vor der Erkennung kein Reset
    assert all(not result.reference_reset for result in results[:first])


def test_valid_llm_answer_new_pattern_resets_the_reference() -> None:
    client = _FixedAnswerClient(_answer("new_pattern", "anomaly.level"))
    results = _run("scaled", days=FOLLOW_DAYS, config=SYS3_FAKE, llm_client=client)
    answered = [index for index, r in enumerate(results) if r.llm_output is not None]

    assert answered
    first = results[answered[0]]
    assert first.classification == "new_pattern"
    assert _action(first).kind == "advance_history_start"
    assert first.reference_reset
    assert all(not result.reference_reset for result in results[: answered[0]])


def test_llm_answer_absence_excludes_the_calendar_window_once() -> None:
    client = _FixedAnswerClient(_answer("absence", "context.events.0.title"))
    event = _vacation_event()
    results = _run(
        "scaled_down",
        days=FOLLOW_DAYS,
        config=SYS3_FAKE,
        llm_client=client,
        events=[event],
    )
    answered = [r for r in results if r.llm_output is not None]

    assert len(answered) >= 2
    first, second = answered[0], answered[1]
    assert first.classification == "absence"
    assert _action(first).kind == "exclude_window"
    assert _action(first).excluded_window == (
        pd.Timestamp(event["start"]),
        pd.Timestamp(event["end"]),
    )
    # dasselbe Fenster wird am Folgetag nicht ein zweites Mal ausgeschlossen
    assert _action(second).kind == "none"
    assert not any(result.reference_reset for result in results)


def test_llm_answer_with_unknown_evidence_path_causes_no_adaption() -> None:
    client = _FixedAnswerClient(_answer("new_pattern", "anomaly.invented_path"))
    results = _run("scaled", days=FOLLOW_DAYS, config=SYS3_FAKE, llm_client=client)
    failed = [result for result in results if result.llm_error is not None]

    assert client.calls > 0
    assert len(failed) == client.calls
    assert all(result.classification is None for result in failed)
    assert all(result.adaption_action is None for result in failed)
    assert not any(result.reference_reset for result in results)


@pytest.mark.parametrize("asks_for_calendar", [True, False])
def test_calendar_tool_decides_whether_absence_can_be_grounded(
    asks_for_calendar: bool,
) -> None:
    client = _FixedAnswerClient(
        _answer("absence", "context.events.0.title"), asks_for_calendar
    )
    event = _vacation_event()
    results = _run(
        "scaled_down",
        days=FOLLOW_DAYS,
        config=SYS3_TOOL_FAKE,
        llm_client=client,
        events=[event],
    )
    answered = [r for r in results if r.llm_output is not None]
    failed = [r for r in results if r.llm_error is not None]

    if asks_for_calendar:
        assert answered
        assert answered[0].calendar_tool_response is not None
        assert _action(answered[0]).kind == "exclude_window"
        assert _action(answered[0]).excluded_window == (
            pd.Timestamp(event["start"]),
            pd.Timestamp(event["end"]),
        )
    else:
        # ohne Abruf gibt es keinen Eintrag, auf den der Pfad zeigen könnte
        assert not answered
        assert failed
        assert all(result.adaption_action is None for result in failed)
