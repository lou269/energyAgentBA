# conda activate forecasting-env
# python -m experiments.component_studies.k4_llm_classification.k4_1_llm_model.llm_model_runner

import logging
from dataclasses import asdict
from pathlib import Path
from time import perf_counter

import pandas as pd

from experiments.component_studies.k4_llm_classification.k4_1_llm_model.baseline_classifier import baseline_classify
from experiments.component_studies.k4_llm_classification.k4_1_llm_model.evaluation_cases import LLMEvaluationCase, build_evaluation_cases
from experiments.component_studies.k4_llm_classification.k4_1_llm_model.llm_model_config import K4_OUTPUT_ROOT, LLMModelExperimentConfig, LLMModelVariant
from src.llm.client import LLMClient, ModelMetadata, OllamaClient
from src.llm.inference import LLMAttemptRecord, LLMInferenceError, infer_llm_output
from src.llm.llm_run_artifacts import load_prompt
from src.llm.llm_runner import PROMPT_DIRECTORY
from src.pipeline.io import append_csv, append_jsonl, next_sequential_number, save_json

logger = logging.getLogger(__name__)


class LLMModelRunner:

    def __init__(self, experiment_config: LLMModelExperimentConfig | None = None) -> None:
        self.experiment_config = experiment_config or LLMModelExperimentConfig()

    def run(self) -> None:
        run_started = perf_counter()

        cases = build_evaluation_cases()
        prompt = load_prompt(PROMPT_DIRECTORY / f"prompt_{self.experiment_config.base_llm_config.prompt_version}.txt")

        run_number = next_sequential_number(K4_OUTPUT_ROOT, prefix="k4")
        run_dir = K4_OUTPUT_ROOT / f"k4_{run_number:03d}"
        results_file = run_dir / "results.csv"
        raw_dir = run_dir / "raw"

        logger.info(
            "Starting K4.1 model comparison: %d models x %d cases x %d repetitions.",
            len(self.experiment_config.model_variants),
            len(cases),
            self.experiment_config.repetitions,
        )

        for variant in self.experiment_config.model_variants:
            self._run_variant(variant, cases, prompt, results_file, raw_dir)

        if self.experiment_config.include_rule_based_baseline:
            self._run_baseline(cases, results_file)

        save_json(
            {
                "experiment_id": self.experiment_config.experiment_id,
                "config": asdict(self.experiment_config),
                "cases": {case.case_id: case.expected_classification for case in cases},
                "runtime_seconds": perf_counter() - run_started,
            },
            run_dir / "run_manifest.json",
        )

        logger.info("K4.1 model comparison completed: %s", run_dir)

    def _run_variant(
        self,
        variant: LLMModelVariant,
        cases: tuple[LLMEvaluationCase, ...],
        prompt: str,
        results_file: Path,
        raw_dir: Path,
    ) -> None:
        client: LLMClient = OllamaClient(timeout_seconds=self.experiment_config.base_llm_config.request_timeout_seconds)

        try:
            try:
                model_metadata = client.get_model_metadata(variant.model)
            except Exception as error:
                logger.error("Could not reach Ollama for %s (%s): %s", variant.model_id, variant.model, error)
                return

            for case in cases:
                for repetition in range(1, self.experiment_config.repetitions + 1):
                    row = self._run_attempt(client, variant, model_metadata, case, repetition, prompt, raw_dir)
                    append_csv(pd.DataFrame([row]), results_file)

                    # request_failed = Verbindungsfehler -> Rest der Variante wird übersprungen, invalid_output betrifft nur diesen Versuch
                    if row["error_kind"] == "request_failed":
                        logger.error("Aborting remaining cases for %s (%s) after a request failure.", variant.model_id, variant.model)
                        return
        finally:
            # Modell explizit entladen, bevor die naechste Variante drankommt
            try:
                client.unload_model(variant.model)
            except Exception as error:
                logger.warning("Could not unload %s (%s) from Ollama: %s", variant.model_id, variant.model, error)

            client.close()

    def _run_baseline(
        self,
        cases: tuple[LLMEvaluationCase, ...],
        results_file: Path,
    ) -> None:
        numerical_analysis_config = self.experiment_config.numerical_analysis_config
        local_timezone = self.experiment_config.project_config.timezone

        for case in cases:
            classification = baseline_classify(
                case.state,
                sustained_anomaly_streak_days=numerical_analysis_config.sustained_anomaly_streak_days,
                min_sustained_scales=numerical_analysis_config.min_sustained_scales,
                local_timezone=local_timezone,
            )

            row = {
                "model_id": "BASELINE",
                "model": "rule_based",
                "model_digest": None,
                "case_id": case.case_id,
                "expected_classification": case.expected_classification,
                "repetition": 1,
                "valid": True,
                "classification": classification,
                "correct": classification == case.expected_classification,
                "attempt_count": 1,
                "evidence_reference_count": None,
                "evidence_paths": None,
                "generation_seconds": 0.0,
                "error_kind": None,
                "error": None,
            }
            append_csv(pd.DataFrame([row]), results_file)

    def _run_attempt(
        self,
        client: LLMClient,
        variant: LLMModelVariant,
        model_metadata: ModelMetadata,
        case: LLMEvaluationCase,
        repetition: int,
        prompt: str,
        raw_dir: Path,
    ) -> dict[str, object]:
        base_row = {
            "model_id": variant.model_id,
            "model": variant.model,
            "model_digest": model_metadata["digest"],
            "case_id": case.case_id,
            "expected_classification": case.expected_classification,
            "repetition": repetition,
        }

        base_seed = self.experiment_config.base_llm_config.seed

        seed = base_seed if base_seed is None else base_seed + (repetition - 1)

        base_llm_config = self.experiment_config.base_llm_config

        try:
            result = infer_llm_output(
                case.state,
                client=client,
                prompt=prompt,
                model=variant.model,
                temperature=base_llm_config.temperature,
                presence_penalty=base_llm_config.presence_penalty,
                seed=seed,
                max_attempts=base_llm_config.max_attempts,
                num_predict=base_llm_config.num_predict,
                num_ctx=base_llm_config.num_ctx,
                think=base_llm_config.think,
                keep_alive=base_llm_config.keep_alive,
            )
        except LLMInferenceError as error:
            self._save_raw_attempt(raw_dir, variant, case, repetition, attempts=error.attempts, output=None, error=str(error))
            return {
                **base_row,
                "valid": False,
                "classification": None,
                "correct": False,
                "attempt_count": len(error.attempts),
                "evidence_reference_count": None,
                "evidence_paths": None,
                "generation_seconds": sum(attempt.generation_seconds for attempt in error.attempts),
                "error_kind": "invalid_output",
                "error": str(error),
            }
        except Exception as error:
            self._save_raw_attempt(raw_dir, variant, case, repetition, attempts=(), output=None, error=str(error))
            return {
                **base_row,
                "valid": False,
                "classification": None,
                "correct": False,
                "attempt_count": 0,
                "evidence_reference_count": None,
                "evidence_paths": None,
                "generation_seconds": 0.0,
                "error_kind": "request_failed",
                "error": str(error),
            }

        classification = result.output["classification"]
        evidence_paths = [reference["path"] for reference in result.output["evidence_references"]]

        self._save_raw_attempt(raw_dir, variant, case, repetition, attempts=result.attempts, output=dict(result.output), error=None)

        return {
            **base_row,
            "valid": True,
            "classification": classification,
            "correct": classification == case.expected_classification,
            "attempt_count": len(result.attempts),
            "evidence_reference_count": len(evidence_paths),
            "evidence_paths": ";".join(evidence_paths),
            "generation_seconds": sum(attempt.generation_seconds for attempt in result.attempts),
            "error_kind": None,
            "error": None,
        }

    def _save_raw_attempt(
        self,
        raw_dir: Path,
        variant: LLMModelVariant,
        case: LLMEvaluationCase,
        repetition: int,
        *,
        attempts: tuple[LLMAttemptRecord, ...],
        output: dict[str, object] | None,
        error: str | None,
    ) -> None:
        # nicht Teil von results.csv, für manuelle Durchsicht von explanation/evidence_references (Schema prüft keine inhaltliche Qualität)
        append_jsonl(
            {
                "model": variant.model,
                "case_id": case.case_id,
                "repetition": repetition,
                "expected_classification": case.expected_classification,
                "attempts": [asdict(attempt) for attempt in attempts],
                "output": output,
                "error": error,
            },
            raw_dir / f"{variant.model_id}.jsonl",
        )


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    LLMModelRunner().run()


if __name__ == "__main__":
    main()