from dataclasses import dataclass


RUN_PREFIX = "k2"
# vom Runner geschrieben, vom Report gelesen
GRID_FILE = "k2_grid"
RESETS_FILE = "k2_resets"
DIAGNOSIS_FILE = "k2_diagnosis"
# Spalten der Streak-Schwellen in den Tabellen
STREAK_THRESHOLD_COLUMNS = {
    "weekly": "weekly_streak_threshold",
    "long_term": "long_term_streak_threshold_pct",
}


@dataclass(frozen=True)
class K2Config:
    # Anteil der validation-Tage, an denen eine Niveau-Skala ohne Reset anhält, für beide Skalen gleich
    # # Legt nur das Verhältnis der beiden Schwellen fest, gewählt wird über die Resets
    sustained_shares: tuple[float, ...] = tuple(
        round(0.02 + 0.01 * step, 2) for step in range(29)
    )
    # höchstens so viele Resets im durchgehenden Lauf über validation (etwa 2 je Jahr)
    max_resets: int = 4

    # Diagnose, nicht für die Wahl: Szenarien an Cutovern im Abstand von margin_after_days der Standard-Szenarien,
    # damit sich die Tage nach den Cutovern nicht überlappen
    diagnosis_kinds: tuple[str, ...] = (
        "control",
        "scaled",
        "ramp_28",
        "ramp_28_down",
        "ramp_56",
        "ramp_56_down",
        "peak",
        "level",
    )
