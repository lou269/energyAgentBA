from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import cast

from src.config.llm_config import LLMConfig
from src.llm.inference import LLMAttemptRecord, LLMInferenceError, LLMInferenceResult
from src.llm.llm_run_manifest import LLMRunStatus, build_llm_run_manifest
from src.pipeline.io import find_run_directory, save_json
from src.structured_state.structured_state_schema import StructuredState

from src.llm.client import ModelMetadata


def create_llm_run_id(llm_output_dir: Path, structured_state_run_number: int) -> str:
    latest_run = find_run_directory(llm_output_dir, prefix="llm")
    number = (latest_run[0] if latest_run is not None else 0) + 1
    return f"llm_{number:03d}_ss_{structured_state_run_number:03d}"


def load_structured_state(state_file: Path) -> StructuredState:
    if not state_file.is_file():
        raise FileNotFoundError(f"Structured State does not exist: {state_file}")

    with state_file.open("r", encoding="utf-8") as file:
        loaded_state = json.load(file)

    if not isinstance(loaded_state, dict):
        raise TypeError("Structured State file must contain a JSON object.")

    return cast(StructuredState, loaded_state)


def load_prompt(prompt_file: Path) -> str:
    if not prompt_file.is_file():
        raise FileNotFoundError(f"Prompt file does not exist: {prompt_file}")

    prompt = prompt_file.read_text(encoding="utf-8")

    if not prompt.strip():
        raise ValueError(f"Prompt file must not be empty: {prompt_file}")

    return prompt


def save_successful_llm_run(
    *,
    run_id: str,
    run_directory: Path,
    state: StructuredState,
    state_file: Path,
    prompt: str,
    prompt_file: Path,
    llm_config: LLMConfig,
    model_metadata: ModelMetadata,
    result: LLMInferenceResult,
    runtime_seconds: float,
    project_root: Path,
) -> None:
    output_paths = _save_common_artifacts(
        run_id=run_id,
        run_directory=run_directory,
        state=state,
        prompt=prompt,
        attempts=result.attempts,
    )

    llm_output_file = run_directory / "llm_output.json"
    save_json(dict(result.output), llm_output_file)
    output_paths["llm_output"] = llm_output_file

    _save_manifest(
        run_id=run_id,
        run_directory=run_directory,
        status="valid",
        state=state,
        state_file=state_file,
        prompt_file=prompt_file,
        llm_config=llm_config,
        model_metadata=model_metadata,
        attempts=result.attempts,
        output_paths=output_paths,
        runtime_seconds=runtime_seconds,
        error=None,
        project_root=project_root,
    )


def save_failed_llm_run(
    *,
    run_id: str,
    run_directory: Path,
    state: StructuredState,
    state_file: Path,
    prompt: str,
    prompt_file: Path,
    llm_config: LLMConfig,
    model_metadata: ModelMetadata,
    error: LLMInferenceError,
    runtime_seconds: float,
    project_root: Path,
) -> None:
    output_paths = _save_common_artifacts(
        run_id=run_id,
        run_directory=run_directory,
        state=state,
        prompt=prompt,
        attempts=error.attempts,
    )

    _save_manifest(
        run_id=run_id,
        run_directory=run_directory,
        status="invalid_output",
        state=state,
        state_file=state_file,
        prompt_file=prompt_file,
        llm_config=llm_config,
        model_metadata=model_metadata,
        attempts=error.attempts,
        output_paths=output_paths,
        runtime_seconds=runtime_seconds,
        error=error,
        project_root=project_root,
    )


def save_request_failed_llm_run(
    *,
    run_id: str,
    run_directory: Path,
    state: StructuredState,
    state_file: Path,
    prompt: str,
    prompt_file: Path,
    llm_config: LLMConfig,
    model_metadata: ModelMetadata,
    error: Exception,
    runtime_seconds: float,
    project_root: Path,
    attempts: tuple[LLMAttemptRecord, ...] = (),
) -> None:
    output_paths = _save_common_artifacts(
        run_id=run_id,
        run_directory=run_directory,
        state=state,
        prompt=prompt,
        attempts=attempts,
    )

    _save_manifest(
        run_id=run_id,
        run_directory=run_directory,
        status="request_failed",
        state=state,
        state_file=state_file,
        prompt_file=prompt_file,
        llm_config=llm_config,
        model_metadata=model_metadata,
        attempts=attempts,
        output_paths=output_paths,
        runtime_seconds=runtime_seconds,
        error=error,
        project_root=project_root,
    )


def _save_common_artifacts(
    *,
    run_id: str,
    run_directory: Path,
    state: StructuredState,
    prompt: str,
    attempts: tuple[LLMAttemptRecord, ...],
) -> dict[str, Path]:
    if run_directory.exists():
        raise FileExistsError(f"LLM run directory already exists: {run_directory}")

    run_directory.mkdir(parents=True, exist_ok=False)

    state_output_file = run_directory / "structured_state.json"
    prompt_output_file = run_directory / "prompt.txt"
    attempts_output_file = run_directory / "attempts.json"

    save_json(dict(state), state_output_file)
    _save_text_atomically(prompt, prompt_output_file)
    save_json(
        {"run_id": run_id, "attempts": [asdict(attempt) for attempt in attempts]},
        attempts_output_file,
    )

    return {
        "structured_state": state_output_file,
        "prompt": prompt_output_file,
        "attempts": attempts_output_file,
    }


def _save_manifest(
    *,
    run_id: str,
    run_directory: Path,
    status: LLMRunStatus,
    state: StructuredState,
    state_file: Path,
    prompt_file: Path,
    llm_config: LLMConfig,
    model_metadata: ModelMetadata,
    attempts: tuple[LLMAttemptRecord, ...],
    output_paths: dict[str, Path],
    runtime_seconds: float,
    error: Exception | None,
    project_root: Path,
) -> None:
    manifest = build_llm_run_manifest(
        project_root=project_root,
        run_id=run_id,
        status=status,
        decision_time=state["decision_time"],
        forecast_run_id=state["forecast"]["run_id"],
        config_values=asdict(llm_config),
        model_metadata=dict(model_metadata),
        input_paths={"structured_state": state_file, "prompt": prompt_file},
        output_paths=output_paths,
        attempt_records=tuple(asdict(attempt) for attempt in attempts),
        runtime_seconds=runtime_seconds,
        error=error,
    )

    save_json(manifest, run_directory / "run_manifest.json")


def _save_text_atomically(content: str, output_file: Path) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)

    temporary_file = output_file.with_suffix(output_file.suffix + ".tmp")

    try:
        temporary_file.write_text(content, encoding="utf-8")
        temporary_file.replace(output_file)
    finally:
        temporary_file.unlink(missing_ok=True)