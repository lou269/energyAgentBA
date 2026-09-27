from dataclasses import dataclass

RUN_PREFIX = "e4"
# vom Runner geschrieben, vom Report gelesen
FORECASTS_FILE = "forecasts"
ORIGIN_METRICS_FILE = "origin_metrics"


@dataclass(frozen=True)
class E4Config:
    experiment_id: str = "E4"
    # alle Starttermine liegen im Train-Split
    split: str = "train"

    # je eine Jahreszeit im Train-Split, wie K2, nur Winter einen Monat später: ab 15.01. läge Weihnachten in der CS30-Historie, nicht aber in CS7
    start_dates: tuple[str, ...] = (
        "2013-10-15",
        "2014-02-15",
        "2014-04-15",
        "2014-07-15",
    )

    # C3_30 sieht nie mehr als 30 Tage, CS30 ist damit schon der eingeschwungene Zustand
    coldstart_days: tuple[int, ...] = (7, 14, 30)

    evaluation_days: int = 56

    # Tages-MAEs schwanken stark, die Lernkurve wird kausal über so viele Tage gemittelt
    smoothing_days: int = 7

    window_edges_days: tuple[int, ...] = (7, 14, 28, 56)
