from dataclasses import dataclass, replace

from src.config.config_forecasting import (
    CycleConfig,
    ForecastingConfig,
    NumericalAnalysisConfig,
)


@dataclass(frozen=True)
class K3Config:
    # lokale Kalendertage, je eine Jahreszeit, alle im Train-Split und ohne bekannte Kalenderereignisse im Fenster
    cutover_dates: tuple[str, ...] = (
        "2013-10-15",
        "2014-01-15",
        "2014-04-15",
        "2014-07-15",
    )

    # Historie beginnt Kaltstart + diese Tage vor dem Cutover
    monitoring_before_cutover_days: int = 60
    margin_after_days: int = 60

    step_injection_w: float = 100.0


# Stufe 3: Schwellen und Referenzfenster zusammen kalibrieren, rein offline auf den isolated-Läufen eines K3-Laufs
@dataclass(frozen=True)
class K3CalibrationConfig:
    slow_scales: tuple[str, ...] = ("weekly", "long_term")

    # bis 4,0, weil Rolling 35 nur 5 Referenztage je Wochentag hat und weekday dort deutlich breiter streut
    gate_thresholds: tuple[float, ...] = (
        2.0,
        2.1,
        2.2,
        2.3,
        2.4,
        2.5,
        2.6,
        2.7,
        2.8,
        2.9,
        3.0,
        3.2,
        3.4,
        3.6,
        3.8,
        4.0,
    )
    # darf unter 2 liegen, die eigentliche Hürde ist die Streak mit 6 von 7 Tagen
    slow_scale_thresholds: tuple[float, ...] = (
        1.0,
        1.25,
        1.5,
        1.75,
        2.0,
        2.5,
        3.0,
        3.5,
        4.0,
        4.5,
        5.0,
    )

    target_alarm_rate: float = 0.05
    max_false_new_pattern: float = 1.0


REFERENCE_WINDOWS: dict[str, dict[str, int | None]] = {
    "REF_STATIC": {
        "max_reference_window_growth_days": 60,
        "reference_window_rolling_days": None,
    },
    "REF_EXPANDING": {
        "max_reference_window_growth_days": None,
        "reference_window_rolling_days": None,
    },
    "REF_ROLL60": {
        "max_reference_window_growth_days": None,
        "reference_window_rolling_days": 60,
    },
    "REF_ROLL35": {
        "max_reference_window_growth_days": None,
        "reference_window_rolling_days": 35,
    },
}
REFERENCE_WINDOW_LABELS: dict[str, str] = {
    "REF_STATIC": "Statisch",
    "REF_EXPANDING": "Expanding",
    "REF_ROLL60": "Rolling 60",
    "REF_ROLL35": "Rolling 35",
}


def _variant(
    event_adaptation: bool, reference_window: dict[str, int | None]
) -> CycleConfig:
    return CycleConfig(
        forecasting_config=ForecastingConfig(),
        numerical_analysis_config=replace(
            NumericalAnalysisConfig(), **reference_window
        ),
        event_adaptation=event_adaptation,
        llm_mode="rule",
    )


# isolated: nur der Detektor, adaption: geschlossener Kreislauf mit Regel-Klassifikation wie SYS2 (ohne LLM, K4 ist noch offen)
K3_MODES: dict[str, dict[str, CycleConfig]] = {
    "isolated": {
        label: _variant(False, window) for label, window in REFERENCE_WINDOWS.items()
    },
    "adaption": {
        label: _variant(True, window) for label, window in REFERENCE_WINDOWS.items()
    },
}
K3_MODE_LABELS: dict[str, str] = {"isolated": "ohne Reset", "adaption": "mit Reset"}
