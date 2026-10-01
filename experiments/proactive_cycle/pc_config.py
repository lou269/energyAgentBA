from dataclasses import dataclass

from src.config.config_forecasting import LLMConfig

RUN_PREFIX = "proactive_cycle"
# vom Runner geschrieben, vom Report gelesen
OUTLOOK_FILE = "outlook.jsonl"
# Vorlage für die Erklärungsbewertung
RATING_TEMPLATE_FILE = "outlook_ratings_template"


@dataclass(frozen=True)
class ProactiveCycleConfig:
    experiment_id: str = "pc_outlook"
    config_version: str = "outlook-0.1"

    # Prognose ohne Adaption und ohne Aufruf 1, der Ausblick hängt nur an der Prognose
    cycle_system: str = "SYS1"

    llm_config: LLMConfig = LLMConfig(prompt_version="outlook_v1", keep_alive=-1)

    # Train-Cutover aus den Standard-Szenarien, vom Cutover an so viele Tage mit Ausblick, ohne Kalender
    cutover_date: str = "2014-02-12"
    outlook_days: int = 12

    # Nachkommastellen von kWh und Prozent im State
    state_decimals: int = 1

    # Startwert für das Mischen der Texte im verblindeten Export
    rating_seed: int = 42
