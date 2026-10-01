# python -m pytest tests/unit/llm/test_inference.py -v

import json
from typing import Any

import pytest

from src.config.config_forecasting import LLMConfig

from src.context.calendar_context import build_calendar_context
from src.llm.client import ModelMetadata, ToolCall, ToolCallResponse
from src.llm.inference import LLMInferenceError, LLMInferenceResult, infer_llm_output

from tests.unit.llm._state_fixture import valid_llm_output, valid_structured_state

LLM_CONFIG = LLMConfig(model="test-model")


class ScriptedClient:
    def __init__(
        self,
        responses: list[str | Exception],
        tool_calls: list[ToolCall] | None = None,
    ) -> None:
        self._responses = list(responses)
        self._tool_calls = tool_calls or []
        self.calls: list[dict[str, Any]] = []
        self.tool_requests: list[list[dict[str, str]]] = []

    def generate_json(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        output_schema: dict[str, object],
        temperature: float,
        presence_penalty: float,
        seed: int | None,
        num_predict: int,
        num_ctx: int,
        think: bool,
        keep_alive: int | str,
    ) -> str:
        self.calls.append(
            {
                "model": model,
                "messages": [dict(message) for message in messages],
                "temperature": temperature,
                "presence_penalty": presence_penalty,
                "seed": seed,
                "num_predict": num_predict,
                "num_ctx": num_ctx,
                "think": think,
                "keep_alive": keep_alive,
            }
        )

        response = self._responses.pop(0)

        if isinstance(response, Exception):
            raise response

        return response

    def request_tool_calls(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        tools: list[dict[str, object]],
        temperature: float,
        presence_penalty: float,
        seed: int | None,
        num_predict: int,
        num_ctx: int,
        think: bool,
        keep_alive: int | str,
    ) -> ToolCallResponse:
        self.tool_requests.append([dict(message) for message in messages])
        return {"content": "kein Aufruf", "tool_calls": self._tool_calls}

    def get_model_metadata(self, model: str) -> ModelMetadata:
        return {"name": model, "digest": None}

    def unload_model(self, model: str) -> None:
        pass

    def close(self) -> None:
        pass


def _run(
    client: ScriptedClient,
    *,
    state=None,
    max_attempts: int = 2,
    calendar_lookup=None,
) -> LLMInferenceResult:
    result = infer_llm_output(
        state if state is not None else valid_structured_state(),
        client=client,
        prompt="system prompt",
        model="qwen3.5:9b",
        temperature=0.0,
        presence_penalty=LLM_CONFIG.presence_penalty,
        seed=42,
        max_attempts=max_attempts,
        num_predict=LLM_CONFIG.num_predict,
        num_ctx=LLM_CONFIG.num_ctx,
        think=LLM_CONFIG.think,
        keep_alive=LLM_CONFIG.keep_alive,
        calendar_lookup=calendar_lookup,
    )
    return result


def test_valid_first_attempt_succeeds() -> None:
    client = ScriptedClient([json.dumps(valid_llm_output())])

    result = _run(client)

    assert result.output["classification"] == "peak"
    assert len(result.attempts) == 1
    assert result.attempts[0].valid is True
    assert len(client.calls) == 1
    assert client.calls[0]["presence_penalty"] == LLM_CONFIG.presence_penalty
    assert client.calls[0]["num_predict"] == LLM_CONFIG.num_predict
    assert client.calls[0]["num_ctx"] == LLM_CONFIG.num_ctx
    assert client.calls[0]["think"] == LLM_CONFIG.think
    assert client.calls[0]["keep_alive"] == LLM_CONFIG.keep_alive


def test_malformed_json_is_retried_and_recovers() -> None:
    client = ScriptedClient(["not valid json", json.dumps(valid_llm_output())])

    result = _run(client, max_attempts=2)

    assert len(result.attempts) == 2
    assert result.attempts[0].valid is False
    assert result.attempts[1].valid is True
    assert len(client.calls) == 2

    second_call_messages = client.calls[1]["messages"]
    assert second_call_messages[-2] == {
        "role": "assistant",
        "content": "not valid json",
    }
    assert second_call_messages[-1]["role"] == "user"
    assert "invalid" in second_call_messages[-1]["content"].lower()


def test_invalid_path_is_retried_and_recovers() -> None:
    state = valid_structured_state()
    invalid_output = valid_llm_output()
    invalid_output["evidence_references"][0]["path"] = "forecast.run_id"

    client = ScriptedClient(
        [json.dumps(invalid_output), json.dumps(valid_llm_output())]
    )

    result = _run(client, state=state, max_attempts=2)

    assert result.attempts[0].valid is False
    first_attempt_error = result.attempts[0].validation_error
    assert first_attempt_error is not None
    assert "not an existing scalar Structured-State path" in first_attempt_error
    assert result.attempts[1].valid is True


def test_all_attempts_invalid_raises_llm_inference_error() -> None:
    client = ScriptedClient(["not valid json", "still not valid json"])

    with pytest.raises(LLMInferenceError) as excinfo:
        _run(client, max_attempts=2)

    assert len(excinfo.value.attempts) == 2
    assert all(not attempt.valid for attempt in excinfo.value.attempts)
    assert excinfo.value.__cause__ is not None
    assert len(client.calls) == 2


def test_empty_response_is_treated_as_invalid_attempt() -> None:
    client = ScriptedClient(["   ", json.dumps(valid_llm_output())])

    result = _run(client, max_attempts=2)

    assert result.attempts[0].valid is False
    first_attempt_error = result.attempts[0].validation_error
    assert first_attempt_error is not None
    assert "empty" in first_attempt_error.lower()
    assert result.attempts[1].valid is True


def test_client_exception_is_retried_then_raised_as_inference_error() -> None:
    client = ScriptedClient([ConnectionError("ollama unreachable")] * 3)

    with pytest.raises(LLMInferenceError) as excinfo:
        _run(client, max_attempts=3)

    assert len(client.calls) == 3
    assert isinstance(excinfo.value.__cause__, ConnectionError)
    assert all(not attempt.valid for attempt in excinfo.value.attempts)


def test_client_exception_recovers_on_later_attempt() -> None:
    client = ScriptedClient(
        [ConnectionError("ollama unreachable"), json.dumps(valid_llm_output())]
    )

    result = _run(client, max_attempts=3)

    assert len(client.calls) == 2
    assert result.attempts[0].valid is False
    assert result.attempts[-1].valid is True


@pytest.mark.parametrize(
    "kwargs",
    [
        {"prompt": ""},
        {"temperature": -1.0},
        {"presence_penalty": float("nan")},
        {"seed": 1.5},
        {"max_attempts": 0},
    ],
)
def test_invalid_parameters_are_rejected_before_calling_client(
    kwargs: dict[str, object],
) -> None:
    client = ScriptedClient([json.dumps(valid_llm_output())])

    call_kwargs = {
        "prompt": "system prompt",
        "model": "qwen3.5:9b",
        "temperature": 0.0,
        "presence_penalty": LLM_CONFIG.presence_penalty,
        "seed": 42,
        "max_attempts": 2,
        "num_predict": LLM_CONFIG.num_predict,
        "num_ctx": LLM_CONFIG.num_ctx,
        "think": LLM_CONFIG.think,
        "keep_alive": LLM_CONFIG.keep_alive,
    }
    call_kwargs.update(kwargs)

    with pytest.raises((ValueError, TypeError)):
        infer_llm_output(valid_structured_state(), client=client, **call_kwargs)

    assert client.calls == []


VACATION = {
    "event_id": "vacation",
    "event_type": "absence",
    "start": "2015-12-10T00:00:00+00:00",
    "end": "2015-12-20T00:00:00+00:00",
    "known_at": "2015-11-01T00:00:00+00:00",
}


def _calendar():
    return build_calendar_context(
        [VACATION],
        source_available=True,
        source="calendar_tool",
        retrieved_at="2015-12-16T00:00:00+00:00",
        decision_time="2015-12-16T00:00:00+00:00",
        window_start="2015-12-15T00:00:00+00:00",
        window_end="2015-12-17T00:00:00+00:00",
        local_timezone="UTC",
    )


def test_fetched_calendar_replaces_the_context_and_can_ground_absence() -> None:
    output = valid_llm_output()
    output["classification"] = "absence"
    output["evidence_references"] = [
        {"path": "anomaly.direction"},
        {"path": "context.events.0.event_type"},
    ]
    client = ScriptedClient(
        [json.dumps(output)],
        tool_calls=[
            {"name": "get_calendar_events", "arguments": {}},
        ],
    )

    result = _run(client, calendar_lookup=_calendar)

    context = result.state["context"]
    assert context["source"] == "calendar_tool"
    assert [event["event_id"] for event in context["events"]] == ["vacation"]
    assert result.output["classification"] == "absence"
    assert json.loads(client.calls[0]["messages"][1]["content"])["context"] == context


def test_without_a_tool_call_the_state_stays_as_it_was() -> None:
    state = valid_structured_state()
    client = ScriptedClient([json.dumps(valid_llm_output())])

    result = _run(client, state=state, calendar_lookup=_calendar)

    assert len(client.tool_requests) == 1
    assert result.state == state
    assert result.calendar_tool_response == {"content": "kein Aufruf", "tool_calls": []}
