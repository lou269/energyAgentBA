# python -m pytest tests/unit/experiments/e2_absence/test_e2_evaluation.py -v

import pandas as pd

from experiments.e2_absence.e2_evaluation import PRECHECK_ANOMALY_COLUMNS, summarize_e2
from src.common.timestamps import local_midnight_utc

TIMEZONE = "Europe/London"
WINDOW_START = local_midnight_utc("2013-09-14", TIMEZONE)
WINDOW_END = local_midnight_utc("2013-09-28", TIMEZONE)
EVENT_ID = "vacation-2013-09"
EXCLUDED = f"absence, excluding {EVENT_ID} from 2013-09-14 to 2013-09-28"
NO_EVENT = "absence without a matching calendar event: no action"

# Tag vor dem Urlaub, Urlaubstag 0 (Gate zu), 1 (Einzeltag), 8 (Drift und Reset), erster Tag nach der Rückkehr
DAYS = ["2013-09-13", "2013-09-14", "2013-09-15", "2013-09-22", "2013-09-28"]


def _config_days(
    config: str, classifications: list[str], reasons: list[str], mae: list[float]
) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "analyzed_day": DAYS,
            "config": config,
            "classification": classifications,
            "adaption_action": "none",
            "adaption_reason": reasons,
            "error": None,
            "mae_w": mae,
        }
    )


def test_absence_only_counts_as_a_hit_with_the_calendar_event() -> None:
    comparison = pd.concat(
        [
            _config_days(
                "SYS1",
                ["normal", "low", "low", "new_pattern", "low"],
                [""] * 5,
                [50.0, 60.0, 70.0, 80.0, 90.0],
            ),
            # ohne Kalender geraten, absence_action findet keinen Eintrag
            _config_days(
                "SYS3_CTX0",
                ["normal", "absence", "absence", "new_pattern", "normal"],
                ["", NO_EVENT, NO_EVENT, "", ""],
                [50.0, 60.0, 70.0, 80.0, 90.0],
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
                [50.0, 70.0, 80.0, 70.0, 80.0],
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

    summary = summarize_e2(
        comparison,
        anomaly,
        pd.DataFrame(columns=["config", "analyzed_day", "calendar_available"]),
        pd.DataFrame(columns=["config", "forecast_day", "y_pred"]),
        pd.DataFrame({"reduction_w": [100.0]}),
        window_start=WINDOW_START,
        window_end=WINDOW_END,
        target_classification="absence",
        absence_event_id=EVENT_ID,
        reference_config="SYS1",
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
    ) == [2, 1, 3]

    forecast = summary.forecast.set_index(["config", "phase"])
    assert forecast.loc[("SYS3_CTX1", "after_return"), "mean_delta"] == -10.0
