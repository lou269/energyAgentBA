# python -m src.llm.llm_runner --model qwen3:4b
# python -m src.llm.llm_runner --model qwen3.5:9b

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from time import perf_counter


from src.config.llm_config import LLMConfig
from src.config.project_config import ProjectConfig, ensure_project_directories
from src.llm.inference import LLMInferenceError, LLMInferenceResult, infer_llm_output
from src.llm.client import LLMClient, ModelMetadata, OllamaClient

from src.llm.llm_run_artifacts import (
    create_llm_run_id,
    load_prompt,
    load_structured_state,
    save_failed_llm_run,
    save_request_failed_llm_run,
    save_successful_llm_run,
)


logger = logging.getLogger(__name__)

PROMPT_DIRECTORY = Path(__file__).parent / "prompts"


class LLMRunner:

    def __init__(
        self,
        llm_config: LLMConfig,
        project_config: ProjectConfig | None = None,
        client: LLMClient | None = None,
    ) -> None:
        self.llm_config = llm_config
        self.project_config = project_config or ProjectConfig()
        self.client = (
            client
            if client is not None
            else OllamaClient(timeout_seconds=(llm_config.request_timeout_seconds))
        )

    def run(self) -> LLMInferenceResult:
        ensure_project_directories(self.project_config)

        run_id = create_llm_run_id()
        run_directory = self.project_config.llm_output_dir / run_id
        state_file = self.project_config.structured_state_output_dir / "structured_state.json"
    
        prompt_file = PROMPT_DIRECTORY / f"prompt_{self.llm_config.prompt_version}.txt"

        state = load_structured_state(state_file)
        prompt = load_prompt(prompt_file)

        logger.info(
            "Starting LLM inference: run_id=%s, model=%s, prompt_version=%s.",
            run_id,
            self.llm_config.model,
            self.llm_config.prompt_version,
        )

        model_metadata: ModelMetadata = {"name": self.llm_config.model, "digest": None}

        inference_started = perf_counter()

        try:
            model_metadata = self.client.get_model_metadata(self.llm_config.model)

            result = infer_llm_output(
                state,
                client=self.client,
                prompt=prompt,
                model=self.llm_config.model,
                temperature=self.llm_config.temperature,
                seed=self.llm_config.seed,
                max_attempts=self.llm_config.max_attempts,
            )

        except LLMInferenceError as error:
            runtime_seconds = perf_counter() - inference_started

            save_failed_llm_run(
                run_id=run_id,
                run_directory=run_directory,
                state=state,
                state_file=state_file,
                prompt=prompt,
                prompt_file=prompt_file,
                llm_config=self.llm_config,
                model_metadata=model_metadata,
                error=error,
                runtime_seconds=runtime_seconds,
                project_root=self.project_config.project_root,
            )
            raise

        except Exception as error:
            runtime_seconds = perf_counter() - inference_started

            save_request_failed_llm_run(
                run_id=run_id,
                run_directory=run_directory,
                state=state,
                state_file=state_file,
                prompt=prompt,
                prompt_file=prompt_file,
                llm_config=self.llm_config,
                model_metadata=model_metadata,
                error=error,
                runtime_seconds=runtime_seconds,
                project_root=self.project_config.project_root,
            )
            raise

        runtime_seconds = perf_counter() - inference_started

        save_successful_llm_run(
            run_id=run_id,
            run_directory=run_directory,
            state=state,
            state_file=state_file,
            prompt=prompt,
            prompt_file=prompt_file,
            llm_config=self.llm_config,
            model_metadata=model_metadata,
            result=result,
            runtime_seconds=runtime_seconds,
            project_root=self.project_config.project_root,
        )

        logger.info("LLM inference completed: run_id=%s, output=%s.", run_id, run_directory)

        return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run evidence-grounded LLM inference for the current Structured State.",
        argument_default=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--model", required=True, help="Ollama model, for example qwen3:4b."
    )
    parser.add_argument("--prompt-version")
    parser.add_argument("--temperature", type=float)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--max-attempts", type=int)
    parser.add_argument("--request-timeout-seconds", type=float)

    arguments = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    llm_config = LLMConfig(**vars(arguments))
    LLMRunner(llm_config=llm_config).run()


if __name__ == "__main__":
    main()



