# python -m pytest tests/unit/llm/test_inference.py -v

import json
from typing import Any

import pytest

from src.llm.client import ModelMetadata
from src.llm.inference import LLMInferenceError, LLMInferenceResult, infer_llm_output

from tests.unit.llm._state_fixture import valid_llm_output, valid_structured_state


class ScriptedClient:
    def __init__(
        self, 
        responses: list[str | Exception]
    ) -> None:
        self._responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    def generate_json(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        output_schema: dict[str, object],
        temperature: float,
        seed: int | None,
    ) -> str:
        self.calls.append(
            {
                "model": model,
                "messages": [dict(message) for message in messages],
                "temperature": temperature,
                "seed": seed,
            }
        )

        response = self._responses.pop(0)

        if isinstance(response, Exception):
            raise response

        return response

    def get_model_metadata(self, model: str) -> ModelMetadata:
        return {"name": model, "digest": None}

    def close(self) -> None:
        pass


def _run(
    client: ScriptedClient,
    *,
    state=None,
    max_attempts: int = 2,
) -> LLMInferenceResult:
    result = infer_llm_output(
        state if state is not None else valid_structured_state(),
        client=client,
        prompt="system prompt",
        model="qwen3.5:9b",
        temperature=0.0,
        seed=42,
        max_attempts=max_attempts,
    )
    return result


def test_valid_first_attempt_succeeds() -> None:
    client = ScriptedClient([json.dumps(valid_llm_output())])

    result = _run(client)

    assert result.output["classification"] == "peak"
    assert len(result.attempts) == 1
    assert result.attempts[0].valid is True
    assert len(client.calls) == 1


def test_malformed_json_is_retried_and_recovers() -> None:
    client = ScriptedClient(["not valid json", json.dumps(valid_llm_output())])

    result = _run(client, max_attempts=2)

    assert len(result.attempts) == 2
    assert result.attempts[0].valid is False
    assert result.attempts[1].valid is True
    assert len(client.calls) == 2

    second_call_messages = client.calls[1]["messages"]
    assert second_call_messages[-2] == {"role": "assistant", "content": "not valid json"}
    assert second_call_messages[-1]["role"] == "user"
    assert "invalid" in second_call_messages[-1]["content"].lower()


def test_invalid_path_is_retried_and_recovers() -> None:
    state = valid_structured_state()
    invalid_output = valid_llm_output()
    invalid_output["evidence_references"][0]["path"] = "forecast.run_id"

    client = ScriptedClient([json.dumps(invalid_output), json.dumps(valid_llm_output())])

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


def test_client_exception_is_wrapped_and_not_retried() -> None:
    client = ScriptedClient([ConnectionError("ollama unreachable")])

    with pytest.raises(RuntimeError, match="attempt 1"):
        _run(client, max_attempts=3)

    assert len(client.calls) == 1


@pytest.mark.parametrize(
    "kwargs",
    [
        {"prompt": ""},
        {"temperature": -1.0},
        {"seed": 1.5},
        {"max_attempts": 0},
    ],
)
def test_invalid_parameters_are_rejected_before_calling_client(
    kwargs: dict[str, object]
) -> None:
    client = ScriptedClient([json.dumps(valid_llm_output())])

    call_kwargs = {
        "prompt": "system prompt",
        "model": "qwen3.5:9b",
        "temperature": 0.0,
        "seed": 42,
        "max_attempts": 2,
    }
    call_kwargs.update(kwargs)

    with pytest.raises((ValueError, TypeError)):
        infer_llm_output(valid_structured_state(), client=client, **call_kwargs)

    assert client.calls == []