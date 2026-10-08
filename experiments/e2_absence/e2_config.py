from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from experiments.common.standard_config import (
    GOLDSTANDARD_EXPECTED,
    LLM_SYSTEM,
    REFERENCE_SYSTEM,
    RULE_SYSTEM,
)

RUN_PREFIX = "e2"
PRECHECK_RUN_PREFIX = "e2_precheck"
# vom Runner geschrieben, vom Report gelesen
COMPARISON_FILE = "e2_comparison_summary"
REDUCTION_FILE = "e2_reduction_by_day"
CLASSIFICATION_FILE = "e2_classification_days"
# von e2_select_channels geschrieben (nilmtk-env), von e2_scenarios gelesen
CHANNEL_RANKING_FILE = "absence_channel_ranking"
CHANNEL_DATA_FILE = "absence_channel_data_hourly"


@dataclass(frozen=True)
class E2Config:
    calendar_events_file: Path = (
        Path(__file__).resolve().parent / "calendar_events.json"
    )
    split: str = "validation"

    # je Urlaub ein eigenes Szenario, 14 und 21 Tage
    absence_event_ids: tuple[str, ...] = ("event-2014-08", "event-2015-10")
    # Gegenfall: Eintrag zur selben Zeit, aber absence falsch
    # In counter_ctx steht nur er im Kalender, in den anderen Varianten nur der Urlaubseintrag
    counter_event_ids: dict[str, str] = field(
        default_factory=lambda: {"event-2014-08": "event-2014-08-visit"}
    )
    counter_ctx: str = "ctx1_visit"

    decision_time_margin_before_days: int = 30
    # bis die Urlaubstage aus dem long_term-Fenster (28 Tage) wieder herausfallen
    decision_time_margin_after_days: int = 30

    min_coverage_share_for_subtraction: float = 0.9

    target_classification: str = GOLDSTANDARD_EXPECTED["absence"]
    # Prognose je Phase gepaart gegen das System ohne Adaption
    reference_config: str = REFERENCE_SYSTEM
    plot_configs: tuple[str, ...] = ("SYS1", "SYS3_CTX0", "SYS3_CTX1")

    # je Kontextvariante: Name im Ergebnis -> Systemvariante
    ctx_systems: dict[str, dict[str, str]] = field(
        default_factory=lambda: {
            "ctx0": {"SYS1": "SYS1", "SYS2": "SYS2", "SYS3_CTX0": "SYS3"},
            "ctx1": {"SYS3_CTX1": "SYS3"},
            "ctx1_visit": {"SYS3_CTX1_VISIT": "SYS3"},
            "ctx2": {"SYS3_CTX2": "SYS3_TOOL"},
        }
    )

    # Einordnung auf Ereignisreihen ohne Kalender: Reihe -> (Tag ab Cutover, Art) nacheinander in einem Lauf
    # Starke Arten, damit das Gate sicher öffnet und es um die Klasse geht
    # Spitzen auf verschiedenen Wochentagen, jeweils nach dem Streak-Fenster (7 Tage)
    event_cutover_id: str = "CO4"
    event_series: dict[str, tuple[tuple[int, str], ...]] = field(
        default_factory=lambda: {
            "scaled": ((0, "scaled_strong"),),
            "peaks": ((0, "peak_strong"), (10, "peak_strong"), (20, "peak_strong")),
            "stucks": ((0, "stuck"), (10, "stuck"), (20, "stuck")),
        }
    )
    event_systems: tuple[str, ...] = (REFERENCE_SYSTEM, RULE_SYSTEM, LLM_SYSTEM)

    # Vorprüfung ohne LLM: öffnet der Urlaub das Gate überhaupt, die Regel sieht keinen Kalender, ctx0 reicht
    precheck_ctx_systems: dict[str, dict[str, str]] = field(
        default_factory=lambda: {"ctx0": {"SYS1": "SYS1", "SYS2": "SYS2"}}
    )

    # Kanalauswahl aus e2_select_channels (nilmtk-env) je Urlaub, Eingabe für das Szenario, liegt unter e2_output_dir
    def channel_selection_subdir(self, event_id: str) -> Path:
        return Path("channel_selection") / event_id
