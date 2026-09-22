from dataclasses import dataclass, replace
from pathlib import Path

from src.config.config_forecasting import SYS_VARIANTS, CycleConfig, LLMConfig, NumericalAnalysisConfig
from src.config.project_config import ProjectConfig


@dataclass(frozen=True)
class LLMModelVariant:
    model_id: str
    model: str


LLM_MODEL_VARIANTS: tuple[LLMModelVariant, ...] = (
    LLMModelVariant(model_id="MDL0", model="qwen3:4b"),
    LLMModelVariant(model_id="MDL1", model="qwen3:8b"),
    LLMModelVariant(model_id="MDL2", model="qwen3.5:9b"),
    LLMModelVariant(model_id="MDL3", model="llama3.1:8b"),
    LLMModelVariant(model_id="MDL4", model="gemma3:4b"),
    LLMModelVariant(model_id="MDL5", model="gemma4:e4b"),
    LLMModelVariant(model_id="MDL6", model="gemma4:e4b-mlx"),
    LLMModelVariant(model_id="MDL7", model="ministral-3:8b")
)

_BASE_LLM_CONFIG = LLMConfig(model="", keep_alive=-1)


@dataclass(frozen=True)
class LLMModelExperimentConfig:
    experiment_id: str = "K4_1_llm_model"
    config_version: str = "llm-model-0.4"

    base_llm_config: LLMConfig = _BASE_LLM_CONFIG
  
    repetitions: int = 2

    model_variants: tuple[LLMModelVariant, ...] = LLM_MODEL_VARIANTS

    include_rule_based_baseline: bool = True
    numerical_analysis_config: NumericalAnalysisConfig = NumericalAnalysisConfig()
    project_config: ProjectConfig = ProjectConfig()


K4_OUTPUT_ROOT: Path = Path(__file__).resolve().parent / "output"
K4_SEQUENCE_OUTPUT_ROOT: Path = Path(__file__).resolve().parent / "output_sequence"


def build_sequence_configs(
    model_variants: tuple[LLMModelVariant, ...] = LLM_MODEL_VARIANTS,
    base_llm_config: LLMConfig = _BASE_LLM_CONFIG,
) -> dict[str, CycleConfig]:

    sys3_config = SYS_VARIANTS["SYS3"]

    return {
        variant.model_id: CycleConfig(
            forecasting_config=sys3_config.forecasting_config,
            numerical_analysis_config=sys3_config.numerical_analysis_config,
            event_adaptation=sys3_config.event_adaptation,
            llm_mode=sys3_config.llm_mode,
            llm_config=replace(base_llm_config, model=variant.model),
        )
        for variant in model_variants
    }