import numpy as np
import pandas as pd

from experiments.k3_llm.k3_evaluation import check_answer_texts, summarize_sequence
from src.common.timestamps import local_calendar_range, local_midnight_utc
from src.config.config_forecasting import TextCheckConfig
from tests.unit.llm._state_fixture import valid_structured_state

TIMEZONE = "Europe/London"


def _run(
    kind: str,
    gate_open: list[bool],
    classifications: list[str],
    resets: list[bool] | None = None,
    errors: list[str | None] | None = None,
) -> pd.DataFrame:
    # Tag -1 bis 4, der 15.04. ist Tag 0
    decision_times = local_calendar_range(
        local_midnight_utc("2014-04-14", TIMEZONE),
        1,
        local_midnight_utc("2014-04-19", TIMEZONE),
        TIMEZONE,
    )
    return pd.DataFrame(
        {
            "kind": kind,
            "cutover_date": "2014-04-15",
            "config": "MDL0",
            "decision_time": [time.isoformat() for time in decision_times],
            "classification": classifications,
            "alarm": gate_open,
            "gate_open": gate_open,
            "new_pattern": [value == "new_pattern" for value in classifications],
            "reference_reset": resets or [False] * 6,
            "error": errors or [np.nan] * 6,
        }
    )


def test_sequence_counts_the_expected_class_only_on_days_the_event_opened_the_gate() -> (
    None
):
    runs = [
        _run(
            "control",
            [False, False, False, False, True, False],
            ["normal", "normal", "normal", "normal", "peak", "normal"],
        ),
        _run(
            "scaled_strong",
            [False, False, True, True, True, False],
            ["normal", "normal", "peak", "new_pattern", "new_pattern", "normal"],
            resets=[False, False, False, True, False, False],
            errors=[None, None, None, None, None, "timeout"],
        ),
        _run(
            "peak_strong",
            [False, False, True, False, False, False],
            ["normal", "normal", "peak", "normal", "normal", "normal"],
        ),
        # Gate nur dort offen, wo es auch im Kontrolllauf offen ist
        _run(
            "level",
            [False, False, False, False, True, False],
            ["normal", "normal", "normal", "normal", "peak", "normal"],
        ),
    ]

    summary = summarize_sequence(pd.concat(runs, ignore_index=True))
    events = summary.events.set_index("kind")
    models = summary.models.set_index("config")

    assert events.loc["scaled_strong", "expected_classification"] == "new_pattern"
    # Tag 3 zählt nicht, dort ist das Gate auch ohne Stufe offen
    assert events.loc["scaled_strong", "correct_days"] == 1
    assert events.loc["scaled_strong", "first_correct_day"] == 2
    assert events.loc["scaled_strong", "resets"] == 1
    assert events.loc["peak_strong", "first_correct_day"] == 1
    assert pd.isna(events.loc["level", "first_correct_day"])

    assert models.loc["MDL0", "detected_kinds"] == 2
    assert models.loc["MDL0", "event_kinds"] == 3
    assert models.loc["MDL0", "control_notification_days"] == 1
    assert models.loc["MDL0", "failed_days"] == 1


def test_text_check_counts() -> None:
    state = valid_structured_state()
    config = TextCheckConfig()
    text = {"explanation": "Etwa 311 % mehr.", "uncertainty": "Ursache offen."}
    answers = pd.DataFrame(
        [
            {
                "model_id": "MDL0",
                "case_id": "peak",
                "classification": "peak",
                "user_recommendation": "Prüfe, ob etwas lief.",
                "state": state,
            },
            {
                "model_id": "MDL1",
                "case_id": "peak",
                "classification": "peak",
                "user_recommendation": "Schalte die Waschmaschine aus.",
                "state": state,
            },
        ]
    ).assign(**text)
    results = pd.DataFrame(
        {
            "model_id": ["MDL0", "MDL1"],
            "case_id": ["peak", "peak"],
            "evidence_paths": [
                "anomaly.level;anomaly.direction",
                "anomaly.level",
            ],
        }
    )
    no_outputs = pd.DataFrame(
        columns=[
            "scenario",
            "config",
            "decision_time",
            "analyzed_day",
            "classification",
            "explanation",
            "user_recommendation",
            "uncertainty",
            "evidence_paths",
        ]
    )
    no_states = pd.DataFrame(columns=["scenario", "config", "decision_time", "state"])

    checks = check_answer_texts(
        answers,
        results,
        no_outputs,
        no_states,
        model_order=["MDL0", "MDL1"],
        device_words=config.device_words,
        control_words=config.control_words,
        number_tolerance=config.number_tolerance,
        prompt_numbers=(7.0, 30.0),
    ).models.set_index("model_id")

    assert checks.loc["MDL0", "single_violations"] == 0
    assert checks.loc["MDL0", "single_missing_evidence"] == 0
    assert checks.loc["MDL1", "single_violations"] == 1
    assert checks.loc["MDL1", "single_missing_evidence"] == 1
    assert checks.loc["MDL1", "single_device_mentions"] == 1
    assert checks.loc["MDL0", "single_device_mentions"] == 0
    assert checks["sequence_answers"].sum() == 0
