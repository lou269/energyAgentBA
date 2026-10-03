from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

RUN_PREFIX = "e2"
PRECHECK_RUN_PREFIX = "e2_precheck"
# vom Runner geschrieben, vom Report gelesen
COMPARISON_FILE = "e2_comparison_summary"
REDUCTION_FILE = "e2_reduction_by_day"
# von e2_select_channels geschrieben (nilmtk-env), von e2_scenarios gelesen
CHANNEL_RANKING_FILE = "absence_channel_ranking"
CHANNEL_DATA_FILE = "absence_channel_data_hourly"


@dataclass(frozen=True)
class E2Config:
    calendar_events_file: Path = (
        Path(__file__).resolve().parent / "calendar_events.json"
    )
    # Kanalauswahl aus e2_select_channels (nilmtk-env), Eingabe für das Szenario, liegt unter e2_output_dir
    channel_selection_subdir: Path = Path("channel_selection")

    # 14 Tage, davor 30 und danach 28 ruhige Tage in der K2-Kontrolle (Gate zu, keine Drift, kein Reset)
    active_absence_event_id: str = "vacation-2013-09"

    decision_time_margin_before_days: int = 30
    # bis die Urlaubstage aus dem long_term-Fenster (30 Tage) wieder herausfallen
    decision_time_margin_after_days: int = 30

    min_coverage_share_for_subtraction: float = 0.9

    target_classification: str = "absence"
    # Prognose je Phase gepaart gegen das System ohne Adaption
    reference_config: str = "SYS1"
    plot_configs: tuple[str, ...] = ("SYS1", "SYS3_CTX0", "SYS3_CTX1")

    # je Kontextvariante: Name im Ergebnis -> Systemvariante
    ctx_systems: dict[str, dict[str, str]] = field(
        default_factory=lambda: {
            "ctx0": {"SYS1": "SYS1", "SYS2": "SYS2", "SYS3_CTX0": "SYS3"},
            "ctx1": {"SYS3_CTX1": "SYS3"},
            "ctx2": {"SYS3_CTX2": "SYS3_TOOL"},
        }
    )

    # Vorprüfung ohne LLM: öffnet der Urlaub das Gate überhaupt, die Regel sieht keinen Kalender, ctx0 reicht
    precheck_ctx_systems: dict[str, dict[str, str]] = field(
        default_factory=lambda: {"ctx0": {"SYS1": "SYS1", "SYS2": "SYS2"}}
    )
