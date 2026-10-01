from dataclasses import dataclass

from src.config.config_forecasting import (
    CycleConfig,
    ForecastingConfig,
    NumericalAnalysisConfig,
)


RUN_PREFIX = "k2"
# vom Runner geschrieben, vom Report gelesen
RESULTS_FILE = "k2_results"
CALIBRATION_FILES = {
    "gate_threshold": "k2_gate_threshold",
    "streak_sensitivity": "k2_streak_sensitivity",
}
# Spalten der Streak-Schwellen in den Kalibrierungstabellen
STREAK_THRESHOLD_COLUMNS = {
    "weekday": "weekday_streak_threshold",
    "weekly": "weekly_streak_threshold",
    "long_term": "long_term_streak_threshold_pct",
}


# Cutover, Zeitfenster und Stärken kommen aus StandardScenarioConfig
@dataclass(frozen=True)
class K2Config:
    # im Kreislauf laufen alle Arten, isolated nur, was die Kalibrierung braucht
    kinds: tuple[str, ...] = (
        "control",
        "step_30",
        "step_50",
        "step",
        "step_200",
        "peak",
        "peak_6",
    )
    isolated_kinds: tuple[str, ...] = ("control", "step")
    # erkannt heißt hier Alarm am Ereignistag, nicht new_pattern
    single_day_kinds: tuple[str, ...] = ("peak", "peak_6")
    # eigener Reset (ohne Reset: Beginn eines new_pattern) nur, wenn die Kontrolle so viele Tage davor und danach keinen hat
    control_reset_tolerance_days: int = 7
    # Beginn der Heizperiode: die Kontrolle liegt knapp unter der Streak-Bedingung, jede Störung löst dort new_pattern aus.
    # Nur für Dauerlasten, Steht in der Erkennungstabelle, zählt aber nicht
    uncounted_cutovers: tuple[str, ...] = ("2013-10-15", "2014-10-10")

    # Anteil der Kontrolltage, an denen ein Einzeltag-Alarm gewollt ist
    target_alarm_pct: float = 5.0
    gate_threshold_decimals: int = 1
    max_false_new_pattern: float = 0.5
    # Raster der Streak-Schwellen
    weekday_streak_thresholds: tuple[float, ...] = (1.25, 1.5, 1.75, 2.0, 2.5, 2.75)
    weekly_streak_thresholds: tuple[float, ...] = (0.75, 1.0, 1.25, 1.5)
    long_term_streak_thresholds_pct: tuple[float, ...] = (12.5, 15.0, 20.0, 25.0)


DETECTOR_VARIANT = "DETECTOR"
VARIANT_LABELS: dict[str, str] = {DETECTOR_VARIANT: "Detektor"}
MODE_LABELS: dict[str, str] = {"isolated": "ohne Reset", "adaption": "mit Reset"}


def _variant(
    event_adaptation: bool, numerical_analysis_config: NumericalAnalysisConfig
) -> CycleConfig:
    return CycleConfig(
        forecasting_config=ForecastingConfig(),
        numerical_analysis_config=numerical_analysis_config,
        event_adaptation=event_adaptation,
        llm_mode="rule",
    )


# nur der Detektor ohne Reset, darauf wird kalibriert (die Scores hängen nicht von den Schwellen ab)
def build_isolated_configs() -> dict[str, CycleConfig]:
    return {DETECTOR_VARIANT: _variant(False, NumericalAnalysisConfig())}


# wie im echten Betrieb, Reset durch die Regel wie SYS2 (ohne LLM), mit den kalibrierten Schwellen
def build_adaption_configs(
    numerical_analysis_config: NumericalAnalysisConfig,
) -> dict[str, CycleConfig]:
    return {DETECTOR_VARIANT: _variant(True, numerical_analysis_config)}
