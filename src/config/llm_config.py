from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LLMConfig:
    model: str
    prompt_version: str = "v1"
    temperature: float = 0.0
    seed: int | None = None
    timeout_seconds: float = 5.0
    max_attempts: int = 1