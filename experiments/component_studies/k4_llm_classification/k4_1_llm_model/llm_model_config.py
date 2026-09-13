from dataclasses import dataclass


@dataclass(frozen=True)
class LLMModelVariant:
    model_id: str
    model: str


LLM_MODEL_VARIANTS: tuple[LLMModelVariant, ...] = (
    LLMModelVariant(model_id="MDL0", model="qwen3:4b"),
    LLMModelVariant(model_id="MDL1", model="qwen3.5:9b"),
    LLMModelVariant(model_id="MDL2", model="llama3.1:8b"),
    LLMModelVariant(model_id="MDL3", model="gemma3:12b"),
)


@dataclass(frozen=True)
class LLMModelExperimentConfig:
    experiment_id: str = "K4_1_llm_model"
    config_version: str = "llm-model-0.1"

    prompt_version: str = "v1"
    temperature: float = 0.0
    seed: int = 42

    # Ein Versuch pro Aufruf, damit ungültige Erstausgaben sichtbar bleiben.
    max_attempts: int = 1
    repetitions: int = 3

    model_variants: tuple[LLMModelVariant, ...] = LLM_MODEL_VARIANTS
    output_subdir: str = "llm_model"
