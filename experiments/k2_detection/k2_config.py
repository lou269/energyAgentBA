from dataclasses import dataclass


RUN_PREFIX = "k2"
# vom Runner geschrieben, vom Report gelesen
EVENTS_FILE = "k2_events"
GRID_FILE = "k2_grid"
EVENT_HITS_FILE = "k2_event_hits"
DIAGNOSIS_FILE = "k2_diagnosis"
# Spalten der Streak-Schwellen in den Tabellen
STREAK_THRESHOLD_COLUMNS = {
    "weekday": "weekday_streak_threshold",
    "weekly": "weekly_streak_threshold",
    "long_term": "long_term_streak_threshold_pct",
}


# Cutover, Zeitfenster und Stärken kommen aus StandardScenarioConfig
@dataclass(frozen=True)
class K2Config:
    # Train-Split: kalibriert wird nur bis zu diesem lokalen Kalendertag (einschließlich), er beginnt mit der Reihe
    train_end: str = "2015-04-29"

    # Raster der Streak-Schwellen
    weekday_streak_thresholds: tuple[float, ...] = (1.75, 2.0, 2.5, 2.75)
    weekly_streak_thresholds: tuple[float, ...] = (0.5, 0.75, 1.0, 1.25, 1.5)
    long_term_streak_thresholds_pct: tuple[float, ...] = (10.0, 12.5, 15.0, 20.0, 25.0)

    event_reference_days: int = 28
    event_transition_days: int = 28
    event_min_change_pct: float = 20.0
    event_min_duration_days: int = 10
    event_smoothing_days: int = 7
    event_share: float = 0.75
    # Kandidaten innerhalb dieser Tage gehören zu einem Ereignis
    event_merge_days: int = 28

    # Treffer: ein Reset ab so vielen Tagen vor dem Beginn eines Ereignisses, bis das Ereignis bestätigt ist
    hit_days_before: int = 10
    # falsche Resets je Jahr (außerhalb der Trefferfenster), Grenze für die Wahl der Schwellen
    max_false_resets_per_year: float = 1.5

    # Diagnose: Änderungen, die der Detektor erkennen soll, bei langsamer Änderung nicht, Spitzen am Ereignistag
    positive_kinds: tuple[str, ...] = (
        "scaled",
        "scaled_down",
        "ramp_28",
        "ramp_28_down",
    )
    negative_kinds: tuple[str, ...] = ("ramp_56", "ramp_56_down")
    single_day_kinds: tuple[str, ...] = ("peak", "peak_6")

    # Ziele für die Kurzfassung im Report
    target_detected_share: float = 0.8
    max_slow_fired_share: float = 0.2
    # Zeilen des Rasters im Report, die volle Tabelle steht in der CSV
    report_grid_rows: int = 10

    # erst Übergang plus Haltedauer bestätigen das Ereignis, früher ist es nach der Definition keines
    @property
    def hit_days_after(self) -> int:
        return self.event_transition_days + self.event_min_duration_days

    # Eingriffe der Diagnose
    @property
    def diagnosis_kinds(self) -> tuple[str, ...]:
        return self.positive_kinds + self.negative_kinds + self.single_day_kinds
