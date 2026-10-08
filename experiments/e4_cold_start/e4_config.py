from dataclasses import dataclass, field

from experiments.common.standard_config import LLM_SYSTEM

from src.config.config_forecasting import C1_STATIC, ProphetVariantConfig

RUN_PREFIX = "e4"
# vom Runner geschrieben, vom Report gelesen
FORECAST_METRICS_FILE = "e4_forecast_metrics"
SYSTEM_RESULTS_FILE = "e4_system_results"
# Szenario ohne Injektion im Kreislauf
CLEAN_SCENARIO = "clean"


@dataclass(frozen=True)
class E4Config:
    experiment_id: str = "E4"

    # Standard-Cutover als Starttermine je Abschnitt, nur die ohne Reset
    cutovers: dict[str, tuple[str, ...]] = field(
        default_factory=lambda: {
            "validation": ("CO2", "CO3", "CO5"),
            "test": ("CO6", "CO7"),
        }
    )
    evaluation_days: int = 56

    # E4a: C1 hängt dauerhaft an N, deshalb alle Längen
    forecast_coldstart_days: tuple[int, ...] = (7, 14, 30, 60)
    # nur auf den N Tagen vor Start trainiert, danach nie wieder
    static_variant: ProphetVariantConfig = C1_STATIC

    # E4b: im Vorfilter zählt nur die Gesamthistorie N + Tag, der Verlauf steckt schon in der x-Achse von CS7
    system_coldstart_days: tuple[int, ...] = (7, 60)
    system: str = LLM_SYSTEM
    # Katalog-Arten, beide am 99-%-Quantil echter Tage: peak auf 6 h konzentriert (daily), level über den Tag verteilt (nur weekday)
    injection_kinds: tuple[str, ...] = ("peak", "level")
    # um Tag 22, ab dem CS7 weekday hat: 18 wird noch ohne eingeordnet, 26 mit
    injection_days: tuple[int, ...] = (3, 10, 18, 26, 35)

    # Tages-MAEs schwanken stark, die Abstandskurve im Plot wird kausal über so viele Tage gemittelt
    smoothing_days: int = 7
    window_edges_days: tuple[int, ...] = (7, 14, 28, 56)
