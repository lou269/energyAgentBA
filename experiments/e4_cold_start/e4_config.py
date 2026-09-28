from dataclasses import dataclass

from experiments.common.standard_config import KIND_LABELS
from src.config.config_forecasting import C1_STATIC, ProphetVariantConfig

RUN_PREFIX = "e4"
# vom Runner geschrieben, vom Report gelesen
FORECAST_METRICS_FILE = "e4_forecast_metrics"
SYSTEM_RESULTS_FILE = "e4_system_results"
# Szenario ohne Injektion im Kreislauf
CLEAN_SCENARIO = "clean"

SCENARIO_LABELS = {CLEAN_SCENARIO: "ohne Injektion"} | KIND_LABELS
CRITERION_LABELS = {
    "no_malfunction": "keine Fehlfunktion",
    "usable_from_start": "von Anfang an nutzbar",
    "adapts": "passt sich an",
    "adaptive_vs_static": "adaptiv gegen statisch",
}
CHECK_LABELS = {
    "resets_in_settling": "Resets, solange nicht alle Skalen einen Score haben",
    "forecast_skill_first_window_pct": "Skill der Prognose gegenüber der Baseline in Woche 1 [%]",
    "first_gate_scale_day": "erster Tag mit Gate-Skala, spätester Termin",
    "forecast_settling_day": "Einschwingtag Prognose",
    "notification_settling_day": "Einschwingtag Meldungen, spätester Termin",
    "detection_settling_day": "Einschwingtag Erkennung, spätester Termin und Art",
    "classification_settling_day": "Einschwingtag Einordnung, spätester Termin und Art",
    "static_worse_share": "Anteil der Fenster ab Woche 2, in denen statisch an jedem Termin schlechter ist",
}
# Kennzahl und Bezug, {total} ist die Bezugsgröße aus summarize_price
PRICE_LABELS = {
    "mae_gap_w": ("Zusatz-MAE der Prognose [W]", "bei {total} W mit langem Kaltstart"),
    "only_shortest": (
        "Meldetage nur mit kurzem Kaltstart",
        "von {total} sauberen Tagen",
    ),
    "only_longest": (
        "Meldetage nur mit langem Kaltstart",
        "von {total} sauberen Tagen",
    ),
    "unknown": ("unknown-Tage", "von {total} sauberen Tagen"),
    "missed": ("verpasste Injektionen", "von {total}, die der lange Kaltstart meldet"),
    "class_other": (
        "Injektionen mit anderer Klasse",
        "von {total}, die der lange Kaltstart meldet",
    ),
    "class_unknown": (
        "Injektionen mit unknown statt Klasse",
        "von {total}, die der lange Kaltstart meldet",
    ),
}


@dataclass(frozen=True)
class E4Config:
    experiment_id: str = "E4"
    split: str = "train"

    # je eine Jahreszeit, wie K2, nur Winter einen Monat später: ab 15.01. läge Weihnachten in der CS30-Historie, nicht aber in CS7
    start_dates: tuple[str, ...] = (
        "2013-10-15",
        "2014-02-15",
        "2014-04-15",
        "2014-07-15",
    )
    evaluation_days: int = 56

    # E4a: C1 hängt dauerhaft an N, deshalb alle Längen
    forecast_coldstart_days: tuple[int, ...] = (7, 14, 30, 60)
    # nur auf den N Tagen vor Start trainiert, danach nie wieder
    static_variant: ProphetVariantConfig = C1_STATIC

    # E4b: im Vorfilter zählt nur die Gesamthistorie N + Tag, der Verlauf steckt schon in der x-Achse von CS7
    system_coldstart_days: tuple[int, ...] = (7, 60)
    system: str = "SYS3"
    # gleiche Tagesenergie, einmal auf 6 h konzentriert (daily), einmal über den Tag verteilt (nur weekday)
    injection_kinds: tuple[str, ...] = ("peak_6", "level_250")
    # um Tag 28, ab dem CS7 weekday hat: 26 wird noch ohne eingeordnet, 35 mit
    injection_days: tuple[int, ...] = (3, 10, 18, 26, 35)

    # Tages-MAEs schwanken stark, die Abstandskurve im Plot wird kausal über so viele Tage gemittelt
    smoothing_days: int = 7
    window_edges_days: tuple[int, ...] = (7, 14, 28, 56)
