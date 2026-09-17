import json
import math
from dataclasses import dataclass
from time import perf_counter
from typing import cast

from src.llm.client import LLMClient
from src.llm.llm_schema import LLMOutput, RawLLMOutput, build_llm_output_json_schema
from src.llm.validation import collect_scalar_evidence_paths, validate_llm_output_against_state
from src.pipeline.schema_validation import is_real_number
from src.structured_state.structured_state_schema import StructuredState


@dataclass(frozen=True)
class LLMAttemptRecord:
    attempt_number: int
    raw_content: str
    valid: bool
    validation_error: str | None
    generation_seconds: float


@dataclass(frozen=True)
class LLMInferenceResult:
    output: LLMOutput
    attempts: tuple[LLMAttemptRecord, ...]


class LLMInferenceError(ValueError):
    def __init__(
        self, 
        message: str, 
        *, 
        attempts: tuple[LLMAttemptRecord, ...]
    ) -> None:
        super().__init__(message)
        self.attempts = attempts


def infer_llm_output(
    state: StructuredState,
    *,
    client: LLMClient,
    prompt: str,
    model: str,
    temperature: float,
    seed: int | None,
    max_attempts: int,
    num_predict: int,
    num_ctx: int,
    think: bool,
    keep_alive: int | str,
) -> LLMInferenceResult:
    _validate_inference_parameters(
        prompt=prompt,
        model=model,
        temperature=temperature,
        seed=seed,
        max_attempts=max_attempts,
    )

    allowed_evidence_paths = collect_scalar_evidence_paths(state)
    output_schema = build_llm_output_json_schema(allowed_evidence_paths)

    state_json = json.dumps(state, ensure_ascii=False, allow_nan=False, separators=(",", ":"))

    messages: list[dict[str, str]] = [
        {"role": "system", "content": prompt.strip()},
        {"role": "user", "content": state_json},
    ]

    attempts: list[LLMAttemptRecord] = []
    last_error: TypeError | ValueError | None = None

    for attempt_number in range(1, max_attempts + 1):
        generation_started = perf_counter()

        try:
            content = client.generate_json(
                model=model.strip(),
                messages=messages,
                output_schema=output_schema,
                temperature=float(temperature),
                seed=seed,
                num_predict=num_predict,
                num_ctx=num_ctx,
                think=think,
                keep_alive=keep_alive,
            )
        except Exception as error:
            raise RuntimeError(f"LLM client request failed during attempt {attempt_number}.") from error

        generation_seconds = perf_counter() - generation_started

        try:
            if not isinstance(content, str):
                raise TypeError("LLM client response must be a string.")

            if not content.strip():
                raise ValueError("LLM returned an empty response.")

            parsed_output = json.loads(content)
            raw_output = cast(RawLLMOutput, parsed_output)

            output = validate_llm_output_against_state(raw_output, state, allowed_paths=allowed_evidence_paths)

        except (TypeError, ValueError) as error:
            last_error = error

            attempts.append(
                LLMAttemptRecord(
                    attempt_number=attempt_number,
                    raw_content=content if isinstance(content, str) else repr(content),
                    valid=False,
                    validation_error=(f"{type(error).__name__}: {error}"),
                    generation_seconds=generation_seconds,
                )
            )

            if attempt_number < max_attempts:
                _append_correction_messages(
                    messages=messages,
                    invalid_content=(content if isinstance(content, str) else ""),
                    error=error,
                )

            continue

        attempts.append(
            LLMAttemptRecord(
                attempt_number=attempt_number,
                raw_content=content,
                valid=True,
                validation_error=None,
                generation_seconds=generation_seconds,
            )
        )

        return LLMInferenceResult(output=output, attempts=tuple(attempts))

    raise LLMInferenceError(f"LLM returned no valid output after {max_attempts} attempt(s).", attempts=tuple(attempts)) from last_error



def _append_correction_messages(
    *,
    messages: list[dict[str, str]],
    invalid_content: str,
    error: TypeError | ValueError,
) -> None:
    if invalid_content.strip():
        messages.append({"role": "assistant", "content": invalid_content})

    messages.append(
        {
            "role": "user",
            "content": (
                "The previous response was invalid: "
                f"{type(error).__name__}: {error} "
                "Return one corrected JSON object only. "
                "Use only evidence paths allowed by the provided "
                "JSON schema. The user JSON is the root object. "
                "Do not add `data`, `state`, `json`, `input`, or a "
                "filename before an evidence path. Each evidence "
                "reference contains only a `path`, never a `value`."
            ),
        }
    )


def _validate_inference_parameters(
    *, 
    prompt: str, 
    model: str, 
    temperature: float, 
    seed: int | None, 
    max_attempts: int
) -> None:
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("prompt must be a non-empty string.")

    if not isinstance(model, str) or not model.strip():
        raise ValueError("model must be a non-empty string.")

    if model != model.strip():
        raise ValueError("model must not contain surrounding whitespace.")


    if (
        not is_real_number(temperature)
        or not math.isfinite(float(temperature))
        or temperature < 0
    ):
        raise ValueError("temperature must be a finite non-negative number.")

    if seed is not None and (isinstance(seed, bool) or not isinstance(seed, int)):
        raise TypeError("seed must be an integer or None.")

    if (
        isinstance(max_attempts, bool)
        or not isinstance(max_attempts, int)
        or max_attempts < 1
    ):
        raise ValueError("max_attempts must be an integer of at least 1.")
