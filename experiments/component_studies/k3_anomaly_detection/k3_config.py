from dataclasses import dataclass, replace

from src.config.config_forecasting import CycleConfig, ForecastingConfig, NumericalAnalysisConfig


@dataclass(frozen=True)
class K3Config:
    # lokale Kalendertage, je eine Jahreszeit, alle im Train-Split und ohne bekannte Kalenderereignisse im Fenster
    cutover_dates: tuple[str, ...] = ("2013-10-15", "2014-01-15", "2014-04-15", "2014-07-15")

    # Historie beginnt Kaltstart + diese Tage vor dem Cutover
    monitoring_before_cutover_days: int = 60
    margin_after_days: int = 60

    step_injection_w: float = 100.0


# Deckel 90, Kaltstart 30 und Rolling 35 sind mit k3_001 beantwortet und laufen nicht mehr mit
REFERENCE_WINDOWS: dict[str, dict[str, int | None]] = {
    "REF_STATIC": {},
    "REF_EXPANDING": {"max_reference_window_growth_days": None},
    "REF_ROLL60": {"max_reference_window_growth_days": None, "reference_window_rolling_days": 60},
}


def _variant(event_adaptation: bool, reference_window: dict[str, int | None]) -> CycleConfig:
    return CycleConfig(
        forecasting_config=ForecastingConfig(),
        numerical_analysis_config=replace(NumericalAnalysisConfig(), **reference_window),
        event_adaptation=event_adaptation,
        llm_mode="rule",
    )


# isolated: nur der Detektor, adaption: geschlossener Kreislauf mit Regel-Klassifikation wie SYS2 (ohne LLM, K4 ist noch offen)
K3_MODES: dict[str, dict[str, CycleConfig]] = {
    "isolated": {label: _variant(False, window) for label, window in REFERENCE_WINDOWS.items()},
    "adaption": {label: _variant(True, window) for label, window in REFERENCE_WINDOWS.items()},
}