import logging
import math
from typing import Protocol, TypedDict

from ollama import Client

from src.pipeline.schema_validation import is_real_number

logger = logging.getLogger(__name__)


class ModelMetadata(TypedDict):
    name: str
    digest: str | None


class ToolCall(TypedDict):
    name: str
    arguments: dict[str, object]


class LLMClient(Protocol):
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
    ) -> str: ...

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
    ) -> list[ToolCall]: ...

    def get_model_metadata(self, model: str) -> ModelMetadata: ...

    def unload_model(self, model: str) -> None: ...

    def close(self) -> None: ...


class OllamaClient:
    def __init__(self, *, timeout_seconds: float) -> None:
        if (
            not is_real_number(timeout_seconds)
            or not math.isfinite(float(timeout_seconds))
            or timeout_seconds <= 0
        ):
            raise ValueError("timeout_seconds must be a finite positive number.")

        self._client = Client(timeout=float(timeout_seconds))

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
        response = self._client.chat(
            model=model,
            messages=messages,
            format=output_schema,
            options=_options(temperature, presence_penalty, seed, num_predict, num_ctx),
            think=think,
            stream=False,
            keep_alive=keep_alive,
        )

        if response.done_reason == "length":
            logger.warning(
                "Ollama response for model %s was cut off at the num_predict limit.",
                model,
            )

        return response.message.content or ""

    # ohne format: mit JSON-Schema gibt Ollama keine Tool-Aufrufe zurück
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
    ) -> list[ToolCall]:
        response = self._client.chat(
            model=model,
            messages=messages,
            tools=tools,
            options=_options(temperature, presence_penalty, seed, num_predict, num_ctx),
            think=think,
            stream=False,
            keep_alive=keep_alive,
        )

        return [
            {"name": call.function.name, "arguments": dict(call.function.arguments)}
            for call in response.message.tool_calls or []
        ]

    def get_model_metadata(self, model: str) -> ModelMetadata:
        if not isinstance(model, str) or not model.strip():
            raise ValueError("model must be a non-empty string.")

        available_models = self._client.list()

        for available_model in available_models.models:
            if available_model.model != model:
                continue

            return {
                "name": available_model.model or model,
                "digest": available_model.digest,
            }

        return {"name": model, "digest": None}

    def unload_model(self, model: str) -> None:
        if not isinstance(model, str) or not model.strip():
            raise ValueError("model must be a non-empty string.")

        # leerer Prompt + keep_alive=0 ist der von Ollama dokumentierte Weg, ein Modell sofort aus dem Speicher zu entladen
        self._client.generate(model=model, prompt="", keep_alive=0)

    def close(self) -> None:
        self._client.close()


def _options(
    temperature: float,
    presence_penalty: float,
    seed: int | None,
    num_predict: int,
    num_ctx: int,
) -> dict[str, float | int]:
    options: dict[str, float | int] = {
        "temperature": temperature,
        "presence_penalty": presence_penalty,
        "num_predict": num_predict,
        "num_ctx": num_ctx,
    }

    if seed is not None:
        options["seed"] = seed

    return options
