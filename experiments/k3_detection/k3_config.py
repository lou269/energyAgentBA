from dataclasses import dataclass, field, replace

from src.config.config_forecasting import (
    CycleConfig,
    ForecastingConfig,
    NumericalAnalysisConfig,
)


RUN_PREFIX = "k3"
# vom Runner geschrieben, vom Report gelesen
RESULTS_FILE = "k3_results"
CALIBRATION_FILES = {
    "grid": "k3_calibration_grid",
    "operating_points": "k3_calibration_operating_points",
    "by_cutover": "k3_calibration_by_cutover",
    "loco": "k3_calibration_loco",
}


# Cutover, Zeitfenster und Stärken kommen aus StandardScenarioConfig
@dataclass(frozen=True)
class K3Config:
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
    # eigener Reset nur, wenn die Kontrolle so viele Tage davor und danach keinen hat
    control_reset_tolerance_days: int = 7
    # Beginn der Heizperiode: die Kontrolle liegt knapp unter der Streak-Bedingung, jede Störung löst dort new_pattern aus.
    # Steht in der Erkennungstabelle, zählt aber nicht
    uncounted_cutovers: tuple[str, ...] = ("2013-10-15",)

    # Variante -> (max_reference_window_growth_days, reference_window_rolling_days)
    reference_windows: dict[str, tuple[int | None, int | None]] = field(
        default_factory=lambda: {
            "REF_STATIC": (60, None),
            "REF_EXPANDING": (None, None),
            "REF_ROLL60": (None, 60),
            "REF_ROLL35": (None, 35),
        }
    )

    # Stufe 3: Schwellen und Referenzfenster zusammen kalibrieren, rein offline auf den isolated-Läufen
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


REFERENCE_WINDOW_LABELS: dict[str, str] = {
    "REF_STATIC": "Statisch",
    "REF_EXPANDING": "Expanding",
    "REF_ROLL60": "Rolling 60",
    "REF_ROLL35": "Rolling 35",
}
MODE_LABELS: dict[str, str] = {"isolated": "ohne Reset", "adaption": "mit Reset"}


def _variant(
    event_adaptation: bool, growth_days: int | None, rolling_days: int | None
) -> CycleConfig:
    return CycleConfig(
        forecasting_config=ForecastingConfig(),
        numerical_analysis_config=replace(
            NumericalAnalysisConfig(),
            max_reference_window_growth_days=growth_days,
            reference_window_rolling_days=rolling_days,
        ),
        event_adaptation=event_adaptation,
        llm_mode="rule",
    )


def build_mode_configs(
    reference_windows: dict[str, tuple[int | None, int | None]],
) -> dict[str, dict[str, CycleConfig]]:
    # isolated: nur der Detektor, darauf wird kalibriert. adaption: Gates wie im echten Betrieb, mit Reset durch die Regel wie SYS2 (ohne LLM)
    return {
        "isolated": {
            label: _variant(False, growth, rolling)
            for label, (growth, rolling) in reference_windows.items()
        },
        "adaption": {
            label: _variant(True, growth, rolling)
            for label, (growth, rolling) in reference_windows.items()
        },
    }


def kinds_by_mode(k3_config: K3Config) -> dict[str, tuple[str, ...]]:
    return {"isolated": k3_config.isolated_kinds, "adaption": k3_config.kinds}
