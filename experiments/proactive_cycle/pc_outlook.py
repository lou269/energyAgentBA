from typing import TypedDict, cast

import numpy as np
import pandas as pd

from src.common.timestamps import local_isoformat, shift_local_days
from src.config.config_forecasting import LLMConfig
from src.llm.client import LLMClient
from src.llm.inference import request_validated_json, state_messages
from src.numerical_analysis.multi_scale_analysis import expected_weekday_mean
from src.pipeline.schema_validation import validate_fields

TEXT_FIELDS = ("explanation", "user_recommendation", "uncertainty")


class OutlookState(TypedDict):
    decision_time: str
    weekday: str
    forecast_kwh: float
    # null, wenn die Historie für den Wochentag zu wenige Tage hat
    usual_kwh: float | None
    deviation_pct: float | None


class OutlookOutput(TypedDict):
    explanation: str
    user_recommendation: str
    uncertainty: str


def day_mean_retransformation_factor(
    history: pd.Series,
    forecast_day: pd.Timestamp,
    *,
    reference_window_rolling_days: int,
    min_weekday_reference_samples: int,
    local_timezone: str,
) -> float | None:
    # Prophet rechnet im Log-Raum, ein Stundenwert der Prognose ist typischer (geometrische) Wert
    # Die Tagessumme braucht das Mittel, der Faktor ist das Verhältnis beider je Stunde, summiert über den Tag
    local_history = history.tz_convert(local_timezone)
    window_start = shift_local_days(
        forecast_day, -reference_window_rolling_days, local_timezone
    )
    index = pd.DatetimeIndex(local_history.index)
    same_weekday = local_history[
        (index >= window_start)
        & (index.dayofweek == forecast_day.tz_convert(local_timezone).dayofweek)
        & (local_history > 0)
    ]
    same_index = pd.DatetimeIndex(same_weekday.index)
    if same_index.normalize().nunique() < min_weekday_reference_samples:
        return None

    hours = same_index.hour
    arithmetic = same_weekday.groupby(hours).mean().sum()
    log_values = pd.Series(np.log(same_weekday.to_numpy()), index=same_weekday.index)
    geometric = np.exp(log_values.groupby(hours).mean()).sum()

    return float(arithmetic / geometric)


def weekday_reference(
    history: pd.Series,
    decision_time: pd.Timestamp,
    *,
    rolling_days: int,
    min_samples: int,
    robust: bool,
    local_timezone: str,
) -> tuple[float | None, float | None]:
    # üblicher Tagesmittelwert in W und Rücktransformationsfaktor für den Wochentag, None bei zu wenigen Tagen
    day = decision_time.tz_convert(local_timezone)
    usual_mean_w = expected_weekday_mean(
        history,
        day,
        reference_window_rolling_days=rolling_days,
        min_weekday_reference_samples=min_samples,
        robust=robust,
        local_timezone=local_timezone,
    )
    factor = day_mean_retransformation_factor(
        history,
        day,
        reference_window_rolling_days=rolling_days,
        min_weekday_reference_samples=min_samples,
        local_timezone=local_timezone,
    )

    return usual_mean_w, factor


def build_outlook_state(
    forecast: pd.DataFrame,
    decision_time: pd.Timestamp,
    *,
    usual_mean_w: float | None,
    retransformation_factor: float | None,
    decimals: int,
    local_timezone: str,
) -> OutlookState:
    # horizon kann mehr als den Tag der Entscheidung abdecken
    day_end = shift_local_days(decision_time, 1, local_timezone)
    day = forecast.loc[forecast["target_timestamp"] < day_end]

    # Stundenwerte in W, die Summe über 23, 24 oder 25 Stunden gibt Wh. Ohne genug Vergleichstage gibt es
    # weder Faktor noch üblichen Wert, die Prognose bleibt dann unkorrigiert
    forecast_kwh = float(day["y_pred"].sum()) / 1000 * (retransformation_factor or 1.0)
    usual_kwh = None if usual_mean_w is None else usual_mean_w * len(day) / 1000
    deviation_pct = (
        None
        if usual_kwh is None or usual_kwh <= 0
        else (forecast_kwh - usual_kwh) / usual_kwh * 100
    )

    return {
        "decision_time": local_isoformat(decision_time, local_timezone),
        "weekday": decision_time.tz_convert(local_timezone).day_name(),
        "forecast_kwh": round(forecast_kwh, decimals),
        "usual_kwh": None if usual_kwh is None else round(usual_kwh, decimals),
        "deviation_pct": (
            None if deviation_pct is None else round(deviation_pct, decimals)
        ),
    }


def infer_outlook(
    state: OutlookState, *, client: LLMClient, prompt: str, llm_config: LLMConfig
) -> OutlookOutput:
    output_schema = {
        "type": "object",
        "properties": {
            field: {"type": "string", "minLength": 1} for field in TEXT_FIELDS
        },
        "required": list(TEXT_FIELDS),
        "additionalProperties": False,
    }

    output, _attempts = request_validated_json(
        client,
        state_messages(prompt, state),
        output_schema,
        validate_outlook_output,
        model=llm_config.model,
        temperature=llm_config.temperature,
        presence_penalty=llm_config.presence_penalty,
        seed=llm_config.seed,
        max_attempts=llm_config.max_attempts,
        num_predict=llm_config.num_predict,
        num_ctx=llm_config.num_ctx,
        think=llm_config.think,
        keep_alive=llm_config.keep_alive,
    )

    return output


def validate_outlook_output(parsed: object) -> OutlookOutput:
    if not isinstance(parsed, dict):
        raise TypeError("Outlook output must be an object.")
    validate_fields(parsed, frozenset(TEXT_FIELDS), "Outlook output")

    return cast(OutlookOutput, parsed)
