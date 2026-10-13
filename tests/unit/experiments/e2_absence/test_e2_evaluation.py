# python -m pytest tests/unit/experiments/e2_absence/test_e2_evaluation.py -v

import pandas as pd

from experiments.common.evaluation import SCALE_SUSTAINED_COLUMNS
from experiments.e2_absence.e2_evaluation import (
    PRECHECK_ANOMALY_COLUMNS,
    summarize_classification,
    summarize_answer_checks,
    summarize_classification_rates,
    summarize_e2,
    summarize_false_alarms,
    summarize_rule_agreement,
)
from src.common.sample_structured_state import valid_structured_state
from src.common.timestamps import local_midnight_utc
from src.config.config_forecasting import TextCheckConfig

TIMEZONE = "Europe/London"
WINDOW_START = local_midnight_utc("2013-09-14", TIMEZONE)
WINDOW_END = local_midnight_utc("2013-09-28", TIMEZONE)
EVENT_ID = "vacation-2013-09"
EXCLUDED = f"absence, excluding {EVENT_ID} from 2013-09-14 to 2013-09-28"
NO_EVENT = "absence without a matching calendar event: no action"

# Tag vor dem Urlaub, Urlaubstag 0 (Gate zu), 1 (Einzeltag), 8 (Drift und Reset), erster Tag nach der Rückkehr
DAYS = ["2013-09-13", "2013-09-14", "2013-09-15", "2013-09-22", "2013-09-28"]


def _config_days(
    config: str, classifications: list[str], reasons: list[str]
) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "analyzed_day": DAYS,
            # Mitternacht nach dem analysierten Tag, prognostiziert wird der Folgetag
            "decision_time": [
                local_midnight_utc(day, TIMEZONE, days_offset=1) for day in DAYS
            ],
            "config": config,
            "classification": classifications,
            "adaption_action": "none",
            "adaption_reason": reasons,
            "error": None,
            "day_bias_w": float("nan"),
            "day_error_w": float("nan"),
            "day_forecast_w": float("nan"),
            "mae_w": float("nan"),
            "mape_pct": float("nan"),
        }
    )


def test_absence_only_counts_as_a_hit_with_the_calendar_event() -> None:
    comparison = pd.concat(
        [
            _config_days(
                "SYS1",
                ["normal", "low", "low", "new_pattern", "low"],
                [""] * 5,
            ),
            # ohne Kalender geraten, absence_action findet keinen Eintrag
            _config_days(
                "SYS3_CTX0",
                ["normal", "absence", "absence", "new_pattern", "normal"],
                ["", NO_EVENT, NO_EVENT, "", ""],
            ),
            _config_days(
                "SYS3_CTX1",
                ["normal", "absence", "absence", "absence", "absence"],
                [
                    "",
                    EXCLUDED,
                    f"{EXCLUDED}, already excluded: no action",
                    f"{EXCLUDED}, already excluded: no action",
                    NO_EVENT,
                ],
            ),
        ],
        ignore_index=True,
    )
    # Gate im Urlaub an allen drei Tagen offen, nach der Rückkehr ebenfalls
    anomaly = pd.DataFrame(
        {column: float("nan") for column in PRECHECK_ANOMALY_COLUMNS},
        index=range(len(comparison)),
    )
    anomaly["config"] = comparison["config"]
    anomaly["analyzed_day"] = comparison["analyzed_day"]
    anomaly["anomaly_level"] = ["normal", "unusual", "unusual", "normal", "unusual"] * 3
    anomaly["sustained_drift"] = [False, False, False, True, False] * 3
    # die Drift kommt aus beiden Niveau-Skalen, über sie öffnet das Gate
    anomaly["weekly_sustained"] = anomaly["sustained_drift"]
    anomaly["long_term_sustained"] = anomaly["sustained_drift"]
    anomaly["today_mean"] = [300.0, 150.0, 150.0, 150.0, 300.0] * 3
    # die Prognose nach dem Tag vor dem Urlaub gilt Urlaubstag 0, die letzte dem zweiten Tag nach der Rückkehr
    first_and_last = comparison.index[comparison["analyzed_day"].isin(DAYS[::4])]
    sys1 = first_and_last[comparison.loc[first_and_last, "config"].eq("SYS1")]
    sys3 = first_and_last[comparison.loc[first_and_last, "config"].eq("SYS3_CTX1")]
    comparison.loc[sys1, "day_bias_w"] = [150.0, -50.0]
    comparison.loc[sys3, "day_bias_w"] = [100.0, 0.0]
    comparison["day_error_w"] = comparison["day_bias_w"].abs()
    comparison["mae_w"] = comparison["day_error_w"]

    summary = summarize_e2(
        comparison,
        anomaly,
        # Kalender abgerufen vor dem Urlaub, nicht an Urlaubstag 0, abgerufen an Tag 1, nicht nach der Rückkehr
        pd.DataFrame(
            {
                "config": "SYS3_CTX1",
                "analyzed_day": [DAYS[0], DAYS[1], DAYS[2], DAYS[4]],
                "calendar_available": [True, False, True, False],
            }
        ),
        pd.DataFrame({"reduction_w": [100.0]}),
        window_start=WINDOW_START,
        window_end=WINDOW_END,
        target_classification="absence",
        absence_event_id=EVENT_ID,
        counter_configs=[],
        reference_config="SYS1",
        context_reference_config="SYS3_CTX0",
    )

    hits = summary.absence_classification.set_index("config")
    assert list(hits.loc["SYS3_CTX0", ["hit_days", "unsupported_absence_days"]]) == [
        0,
        2,
    ]
    assert list(
        hits.loc[
            "SYS3_CTX1", ["gate_open_days", "hit_days", "unsupported_absence_days"]
        ]
    ) == [3, 3, 1]

    phases = summary.phases.set_index(["config", "phase"])
    assert list(
        phases.loc[
            ("SYS3_CTX0", "absence"),
            ["absence_classified_days", "new_pattern_days", "notification_days"],
        ]
    ) == [2, 1, 1]

    calls = summary.calendar_calls.set_index("config")
    assert list(
        calls.loc["SYS3_CTX1", ["useful", "superfluous", "missed", "saved"]]
    ) == [1, 1, 1, 1]

    forecast = summary.forecast.set_index(["config", "phase"])
    assert "before" not in forecast.index.get_level_values("phase")
    assert forecast.loc[("SYS1", "absence"), "mean_day_bias_w"] == 150.0
    assert forecast.loc[("SYS1", "after_return"), "mean_day_bias_w"] == -50.0
    assert forecast.loc[("SYS1", "after_return"), "mean_day_error_w"] == 50.0
    assert forecast.loc[("SYS3_CTX1", "after_return"), "mean_delta"] == -50.0

    # als Gegenfall ist kein absence ein Treffer, alle zählen als ohne Beleg
    counter = summarize_e2(
        comparison,
        anomaly,
        pd.DataFrame(columns=["config", "analyzed_day", "calendar_available"]),
        pd.DataFrame({"reduction_w": [100.0]}),
        window_start=WINDOW_START,
        window_end=WINDOW_END,
        target_classification="absence",
        absence_event_id=EVENT_ID,
        counter_configs=["SYS3_CTX1"],
        reference_config="SYS1",
        context_reference_config="SYS3_CTX0",
    ).absence_classification.set_index("config")
    assert list(counter.loc["SYS3_CTX1", ["hit_days", "unsupported_absence_days"]]) == [
        0,
        4,
    ]


def _classification_run(
    config: str,
    classifications: list[str],
    gate_open: list[bool],
    kind: str = "peaks",
) -> pd.DataFrame:
    # Tag 0 bis 5, der 15.04. ist Tag 0, die Reihe steht in kind
    return pd.DataFrame(
        {
            "config": config,
            "kind": kind,
            "cutover_date": "2014-04-15",
            "analyzed_day": [f"2014-04-{14 + day}" for day in range(6)],
            "decision_time": [
                local_midnight_utc(f"2014-04-{15 + day}", TIMEZONE).isoformat()
                for day in range(6)
            ],
            "classification": classifications,
            "adaption_action": "none",
            "error": None,
            "gate_open": gate_open,
            "sustained_drift": False,
            "dominant_scale": "daily",
            **{column: False for column in SCALE_SUSTAINED_COLUMNS},
        }
    )


def test_classification_is_judged_per_event_on_its_first_day_with_open_gate() -> None:
    # Ereignis 1 an Tag 0 (bewertet an Tag 1), Ereignis 2 an Tag 2 (bewertet an Tag 3)
    events = {"peaks": ((0, "peak_strong"), (2, "peak_strong"))}
    runs = [
        _classification_run(
            "SYS2",
            ["normal", "peak", "normal", "peak", "normal", "normal"],
            [False, True, False, True, False, False],
        ),
        _classification_run(
            "SYS3",
            ["normal", "peak", "normal", "low", "normal", "normal"],
            [False, True, False, True, False, False],
        ),
        # Gate bei Ereignis 2 nie offen, also dort nie bewertet
        _classification_run(
            "SYS1",
            ["normal", "peak", "normal", "normal", "normal", "normal"],
            [False, True, False, False, False, False],
        ),
    ]

    events_table = summarize_classification(pd.concat(runs, ignore_index=True), events)
    result = events_table.set_index(["config", "event"])

    assert result.loc[("SYS2", 1), "judged_day"] == 1
    assert result.loc[("SYS2", 1), "trigger_scale"] == "daily"
    assert result.loc[("SYS2", 1), "expected"] == "peak"
    assert result.loc[("SYS2", 2), "correct"]
    assert result.loc[("SYS3", 1), "correct"]
    assert not result.loc[("SYS3", 2), "correct"]
    assert not result.loc[("SYS1", 2), "detected"]
    assert pd.isna(result.loc[("SYS1", 2), "correct"])

    rates = summarize_classification_rates(events_table).set_index(
        ["config", "expected"]
    )
    assert rates.loc[("SYS3", "all"), "events"] == 2
    assert rates.loc[("SYS3", "all"), "correct"] == 1
    assert rates.loc[("SYS3", "peak"), "correct_pct"] == 50
    assert rates.loc[("SYS1", "all"), "detected"] == 1
    assert rates.loc[("SYS1", "all"), "correct_pct"] == 100


def test_rule_agreement_lists_the_days_with_another_class_and_counts_notifications() -> (
    None
):
    peaks = ["normal", "peak", "normal", "peak", "normal", "normal"]
    gate = [False, True, False, True, False, False]
    runs = [
        _classification_run("SYS2", peaks, gate),
        # am Tag 3 ordnet das LLM als low statt peak ein
        _classification_run(
            "SYS3", ["normal", "peak", "normal", "low", "normal", "normal"], gate
        ),
        # die Kontrolle ohne Ereignis, beide gleich
        _classification_run("SYS2", ["normal"] * 6, [False] * 6, kind="control"),
        _classification_run("SYS3", ["normal"] * 6, [False] * 6, kind="control"),
    ]

    agreement = summarize_rule_agreement(
        pd.concat(runs, ignore_index=True), rule_system="SYS2", llm_system="SYS3"
    )
    summary = agreement.summary.set_index("series")

    assert list(summary.loc["peaks", ["days", "gate_open_days", "deviation_days"]]) == [
        6,
        2,
        1,
    ]
    assert list(
        summary.loc["peaks", ["rule_notification_days", "llm_notification_days"]]
    ) == [2, 1]
    assert summary.loc["control", "deviation_days"] == 0
    assert agreement.deviations["days_since_cutover"].tolist() == [3]
    assert agreement.deviations["classification_llm"].tolist() == ["low"]


def test_a_reset_is_false_when_the_llm_resets_and_the_rule_does_not() -> None:
    events = {
        "control": (),
        "peaks": ((0, "peak_strong"), (2, "peak_strong")),
        "scaled": ((0, "scaled_strong"),),
    }
    gate = [False, True, False, True, False, False]
    classes = {
        "control": ["normal"] * 6,
        "peaks": ["normal", "peak", "normal", "peak", "peak", "new_pattern"],
        "scaled": ["normal", "new_pattern", "normal", "normal", "normal", "normal"],
    }
    # je Reihe die Tage mit Reset: Regel und LLM
    reset_days = {
        "control": ([], [2]),
        "peaks": ([5], [3, 5]),
        "scaled": ([1], [1]),
    }
    runs = []
    for series, (rule_days, llm_days) in reset_days.items():
        for config, days in (("SYS2", rule_days), ("SYS3", llm_days)):
            run = _classification_run(config, classes[series], gate, kind=series)
            run.loc[days, "adaption_action"] = "advance_history_start"
            runs.append(run)

    alarms = summarize_false_alarms(
        pd.concat(runs, ignore_index=True),
        events,
        rule_system="SYS2",
        llm_system="SYS3",
    )
    resets = alarms.resets.set_index("series")
    notifications = alarms.notifications.set_index(["config", "series"])

    # die Dauerlast verlangt einen Reset, sie zählt nicht mit
    assert alarms.resets["series"].tolist() == ["control", "peaks", "all"]
    assert list(resets.loc["control"]) == [6, 0, 1, 1]
    # der Reset an Tag 5 kommt auch von der Regel, nur Tag 3 ist falsch
    assert list(resets.loc["peaks"]) == [6, 1, 2, 1]
    assert list(resets.loc["all"]) == [12, 1, 3, 2]
    # Tag 1 und 3 sind die Ereignisse der Spitzen, bei der Dauerlast zählt erst Tag 1 dazu
    assert list(notifications.loc[("SYS2", "peaks")]) == [4, 2]
    assert list(notifications.loc[("SYS2", "scaled")]) == [1, 0]
    assert list(notifications.loc[("SYS2", "all")]) == [11, 2]


def test_answer_checks_find_missing_evidence_and_words_across_time_zones() -> None:
    config = TextCheckConfig()
    # der State schreibt die lokale Zeit mit Offset, die Antwort UTC
    local_times = [f"2015-06-0{day}T00:00:00+01:00" for day in (2, 3, 4)]
    utc_times = [f"2015-06-0{day}T23:00:00+00:00" for day in (1, 2, 3)]
    scenario = "event-2015-06/ctx1"
    states = pd.DataFrame(
        {
            "scenario": scenario,
            "config": "SYS3_CTX1",
            "decision_time": local_times,
            "state": [
                {**valid_structured_state(), "decision_time": time}
                for time in local_times
            ],
        }
    )
    outputs = pd.DataFrame(
        {
            "scenario": scenario,
            "config": "SYS3_CTX1",
            "decision_time": utc_times,
            "analyzed_day": ["2015-06-02", "2015-06-03", "2015-06-04"],
            "classification": ["absence", "absence", "peak"],
            "explanation": ["Laut Kalender weg."] * 2 + ["Ein Ausreißer."],
            "user_recommendation": ["Nichts zu tun."] * 2 + ["Schalte die Geräte aus."],
            "uncertainty": ["Gering."] * 3,
            "evidence_paths": [
                "anomaly.level;context.events.0.title",
                "anomaly.level",
                "anomaly.level;anomaly.direction",
            ],
        }
    )

    checks = summarize_answer_checks(
        outputs,
        states,
        target_classification="absence",
        control_words=config.control_words,
        number_tolerance=config.number_tolerance,
        rounding_step=config.rounding_step,
        prompt_numbers=(7.0, 28.0),
    )
    row = checks.summary.iloc[0]

    assert list(
        row[
            [
                "answers",
                "unsupported_answers",
                "violation_answers",
                "target_answers",
                "target_supported_answers",
            ]
        ]
    ) == [3, 1, 1, 2, 1]
    assert checks.findings["analyzed_day"].tolist() == ["2015-06-03", "2015-06-04"]
    assert "context.events.<index>.title" in checks.findings["missing_evidence"].iloc[0]
