from dataclasses import dataclass, replace

from src.config.config_forecasting import SYS_VARIANTS, CycleConfig, LLMConfig

RUN_PREFIX = "k3"
SEQUENCE_RUN_PREFIX = "k3_seq"
# vom Runner geschrieben, vom Report gelesen
RESULTS_FILE = "results"
SEQUENCE_RESULTS_FILE = "sequence_results"
# die Regel läuft in beiden Ebenen unter diesem Namen neben den Modellen mit
BASELINE_ID = "BASELINE"


@dataclass(frozen=True)
class LLMModelVariant:
    model_id: str
    model: str


@dataclass(frozen=True)
class K3Config:
    experiment_id: str = "K3_1_llm_model"
    config_version: str = "llm-model-0.6"

    base_llm_config: LLMConfig = LLMConfig(model="", keep_alive=-1)

    # bei temperature=0 praktisch deterministisch, eine zweite Wiederholung wäre fast eine Kopie
    repetitions: int = 1

    model_variants: tuple[LLMModelVariant, ...] = (
        # LLMModelVariant(model_id="MDL0", model="qwen3:4b"),
        LLMModelVariant(model_id="MDL1", model="qwen3:8b"),
        # LLMModelVariant(model_id="MDL2", model="qwen3.5:9b"),
        # LLMModelVariant(model_id="MDL3", model="gemma4:e4b"),
        # LLMModelVariant(model_id="MDL4", model="gemma4:e4b-mlx"),
        LLMModelVariant(model_id="MDL5", model="ministral-3:8b"),
    )

    include_rule_based_baseline: bool = True

    # Ebene 2: ein Cutover der Standard-Szenarien, nur für die Modellwahl.
    # Die erwartete Klasse je Art steht in GOLDSTANDARD_EXPECTED, ramp_56 aus E5 fehlt, sie öffnet hier kein Gate und das LLM wird nie gefragt
    sequence_cutover_date: str = "2014-04-15"
    sequence_kinds: tuple[str, ...] = ("control", "step", "peak_6")


def build_sequence_configs(
    model_variants: tuple[LLMModelVariant, ...], base_llm_config: LLMConfig
) -> dict[str, CycleConfig]:
    # SYS3 mit ausgetauschtem Modell
    return {
        variant.model_id: replace(
            SYS_VARIANTS["SYS3"],
            llm_config=replace(base_llm_config, model=variant.model),
        )
        for variant in model_variants
    }
