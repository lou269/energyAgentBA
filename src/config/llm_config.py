from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LLMConfig:
    model: str
    prompt_version: str = "v3"
    temperature: float = 0.0
    seed: int | None = 42
    max_attempts: int = 2
    request_timeout_seconds: float = 120.0
