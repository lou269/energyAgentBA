from collections.abc import Collection
from dataclasses import dataclass

import pandas as pd

from experiments.common.evaluation import check_answer_text
from experiments.common.standard_config import LOCAL_TIMEZONE
from experiments.proactive_cycle.pc_outlook import TEXT_FIELDS
from src.common.timestamps import local_date_text

RATING_COLUMNS = [
    "item",
    "weekday",
    "forecast_kwh",
    "usual_kwh",
    "deviation_pct",
] + list(TEXT_FIELDS)


@dataclass(frozen=True)
class ProactiveCycleSummary:
    days: pd.DataFrame
    day_count: int
    validity_percent: float
    violation_count: int


def check_day(
    record: dict,
    *,
    control_words: Collection[str],
    number_tolerance: float,
    rounding_step: float,
) -> dict:
    state = record["state"]
    output = record["output"]
    row = {
        "day": local_date_text(pd.Timestamp(state["decision_time"]), LOCAL_TIMEZONE),
        "weekday": state["weekday"],
        "forecast_kwh": state["forecast_kwh"],
        "usual_kwh": state["usual_kwh"],
        "deviation_pct": state["deviation_pct"],
        "valid": output is not None,
        "error": record["error"],
        "violations": "",
    }
    for field in TEXT_FIELDS:
        row[field] = "" if output is None else output[field]

    if output is None:
        return row

    text = " ".join(output[field] for field in TEXT_FIELDS)
    row["violations"] = check_answer_text(
        text,
        state,
        control_words=control_words,
        number_tolerance=number_tolerance,
        rounding_step=rounding_step,
    )

    return row


def summarize_outlook(
    records: list[dict],
    *,
    control_words: Collection[str],
    number_tolerance: float,
    rounding_step: float,
) -> ProactiveCycleSummary:
    days = pd.DataFrame(
        [
            check_day(
                record,
                control_words=control_words,
                number_tolerance=number_tolerance,
                rounding_step=rounding_step,
            )
            for record in records
        ]
    )

    return ProactiveCycleSummary(
        days=days,
        day_count=len(days),
        validity_percent=float(days["valid"].mean() * 100),
        violation_count=int(days["violations"].ne("").sum()),
    )


def build_rating_export(days: pd.DataFrame, *, seed: int) -> pd.DataFrame:
    shuffled = days.loc[days["valid"]].sample(frac=1, random_state=seed)
    shuffled = shuffled.assign(
        item=[f"A{number:02d}" for number in range(1, len(shuffled) + 1)]
    )

    return shuffled[RATING_COLUMNS]
