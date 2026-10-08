from __future__ import annotations

from dataclasses import dataclass

from experiments.common.standard_config import LLM_SYSTEM, REFERENCE_SYSTEM, RULE_SYSTEM

RUN_PREFIX = "e3"
# vom Runner geschrieben, vom Report gelesen
RESULTS_FILE = "e3_results"
# Ordner je Reihe und Cutover unter raw/, darüber ordnet die Evaluation Laufzeiten und LLM-Antworten zu
SCENARIO_DIRECTORY = "{series}_{cutover_date}"


@dataclass(frozen=True)
class E3Config:
    # bis zum Test-Lauf auf zwei Cutovern in validation, Zahlen daraus sind kein Beleg.
    # Beide im Winterhalbjahr wie der spätere Test-Cutover
    split: str = "validation"
    cutover_dates: tuple[str, ...] = ("2014-10-15", "2015-01-15")

    reference_system: str = REFERENCE_SYSTEM
    rule_system: str = RULE_SYSTEM
    llm_system: str = LLM_SYSTEM

    margin_before_days: int = 14
    # (Tag ab Cutover, Art) nacheinander in einer Reihe. Erst die Spitzen und der Festhänger, die Dauerlast zuletzt, nach ihrem Reset fehlen Skalen.
    # Die zweite Spitze liegt nach dem Streak-Fenster (7 Tage) der ersten und auf einem anderen Wochentag, der Festhänger nach dem der zweiten.
    # Starke Arten, hier geht es um die Wirkung der Adaption und nicht um die Erkennung
    events: tuple[tuple[int, str], ...] = (
        (0, "peak_strong"),
        (10, "peak_strong"),
        (17, "stuck"),
        (21, "scaled_strong"),
    )
    # rund 30 Tage nach Beginn der Dauerlast
    margin_after_days: int = 51
