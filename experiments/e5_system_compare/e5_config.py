from __future__ import annotations

from dataclasses import dataclass

RUN_PREFIX = "e5"
# vom Runner geschrieben, vom Report gelesen
RESULTS_FILE = "e5_results"
# Ordner je Reihe und Cutover unter raw/, darüber ordnet die Evaluation Laufzeiten und LLM-Antworten zu
SCENARIO_DIRECTORY = "{series}_{cutover_date}"


@dataclass(frozen=True)
class E5Config:
    # bis zum Test-Lauf auf zwei Standard-Cutovern aus dem Train-Split, Zahlen daraus sind kein Beleg.
    # Beide im Winterhalbjahr wie der spätere Test-Cutover
    cutover_dates: tuple[str, ...] = ("2013-10-15", "2014-01-15")

    reference_system: str = "SYS1"
    rule_system: str = "SYS2"
    llm_system: str = "SYS3"

    margin_before_days: int = 14
    # (Tag ab Cutover, Art) nacheinander in einer Reihe. Erst die Spitzen und der Festhänger, die Dauerlast zuletzt, nach ihrem Reset fehlen Skalen.
    # Die zweite Spitze liegt nach dem Streak-Fenster (7 Tage) der ersten und auf einem anderen Wochentag, der Festhänger nach dem der zweiten
    events: tuple[tuple[int, str], ...] = (
        (0, "peak_6"),
        (10, "peak_6"),
        (17, "stuck"),
        (21, "step_200"),
    )
    # rund 30 Tage nach Beginn der Dauerlast
    margin_after_days: int = 51
