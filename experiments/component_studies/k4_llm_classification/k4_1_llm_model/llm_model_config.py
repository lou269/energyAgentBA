from dataclasses import dataclass
from pathlib import Path

from src.config.config_forecasting import LLMConfig


@dataclass(frozen=True)
class LLMModelVariant:
    model_id: str
    model: str


LLM_MODEL_VARIANTS: tuple[LLMModelVariant, ...] = (
    #LLMModelVariant(model_id="MDL0", model="qwen3:4b"),
    #LLMModelVariant(model_id="MDL1", model="qwen3:8b"),
    LLMModelVariant(model_id="MDL2", model="qwen3.5:9b"),
    #LLMModelVariant(model_id="MDL3", model="llama3.1:8b"),
    #LLMModelVariant(model_id="MDL4", model="gemma3:12b"),
    #LLMModelVariant(model_id="MDL5", model="qwen3:14b"),
    #LLMModelVariant(model_id="MDL6", model="gpt-oss:20b"),
    LLMModelVariant(model_id="MDL7", model="gemma4:12b"),
)

# temperature>0, damit repetitions überhaupt Streuung erzeugen kann (seed variiert zusätzlich pro Wiederholung in llm_model_runner.py)
_BASE_LLM_CONFIG = LLMConfig(model="", temperature=0.3)


@dataclass(frozen=True)
class LLMModelExperimentConfig:
    experiment_id: str = "K4_1_llm_model"
    config_version: str = "llm-model-0.3"

    base_llm_config: LLMConfig = _BASE_LLM_CONFIG
    repetitions: int = 3

    model_variants: tuple[LLMModelVariant, ...] = LLM_MODEL_VARIANTS


K4_OUTPUT_ROOT: Path = Path(__file__).resolve().parent / "output"
