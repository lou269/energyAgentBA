from __future__ import annotations

import math
from typing import Protocol, TypedDict

from ollama import Client

from src.pipeline.schema_validation import is_real_number


class ModelMetadata(TypedDict):
    name: str
    digest: str | None


class LLMClient(Protocol):
    def generate_json(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        output_schema: dict[str, object],
        temperature: float,
        seed: int | None,
    ) -> str: ...

    def get_model_metadata(self, model: str) -> ModelMetadata: ...

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
        seed: int | None,
    ) -> str:
        options: dict[str, float | int] = {"temperature": temperature}

        if seed is not None:
            options["seed"] = seed

        response = self._client.chat(
            model=model,
            messages=messages,
            format=output_schema,
            options=options,
            think=False,
            stream=False,
        )

        return response.message.content or ""

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


    def close(self) -> None:
        self._client.close()
