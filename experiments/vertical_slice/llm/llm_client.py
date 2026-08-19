from __future__ import annotations

import json

from ollama import chat


SYSTEM_PROMPT = """
You are the interpretation component of a household electricity
forecasting system.

You receive a structured state containing:
- current and historical electricity consumption information
- numerical trend analysis
- anomaly detection results
- a 24-hour Prophet forecast with uncertainty
- optional calendar context

Use only the supplied information.

Do not invent appliances, events, user behavior, calendar events,
holidays, occupancy patterns, or causes that are not explicitly
supported by the structured state.

Do not compare the current observation directly with forecast values
for different timestamps as if they represented the same point in time.

The forecast describes future expected consumption only.
The current observation describes the state at the cutoff timestamp.

Classify the current situation into exactly one of:

normal
absence
temporary_peak
new_pattern
seasonal_change
measurement_issue
unknown

Distinguish between numerical evidence, contextual evidence, and
hypotheses.

If evidence for a cause is insufficient, state that explicitly instead
of inventing an explanation.

The adaptation recommendation is only a recommendation.
Do not assume that model adaptation has already happened.

Important evidence rules:

- Never perform or state numerical comparisons unless they are
  directly supported by values referring to the same concept and
  compatible time period.

- Do not compare current_power_w with future forecast minimum,
  maximum, mean, or peak values to classify the current state.

- Forecast information describes the future only.

- Do not infer that a numerical trend is caused by calendar context.
  A calendar event may support a classification, but correlation
  must not be presented as a proven cause.

- Do not invent typical behavior during vacations, absence,
  weekends, holidays, appliance usage, or return times.

- Do not invent thresholds.

- If anomaly.level is supplied, use it as the numerical anomaly
  classification. Do not derive a new anomaly class from
  anomaly.score.

- numerical_evidence must contain only literal facts supported by
  observation, analysis, anomaly, or forecast.

- contextual_evidence must contain only literal facts supplied
  inside context.

- If calendar_available is false, say that calendar context is
  unavailable. Do not interpret an empty event list as evidence that
  no events exist.

- If the numerical state is normal but calendar context indicates
  absence, explicitly state that the absence classification is
  context-based rather than anomaly-based.
"""


OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "classification": {
            "type": "string",
            "enum": [
                "normal",
                "absence",
                "temporary_peak",
                "new_pattern",
                "seasonal_change",
                "measurement_issue",
                "unknown",
            ],
        },
        "confidence": {
            "type": "number",
            "minimum": 0,
            "maximum": 1,
        },
        "numerical_evidence": {
            "type": "array",
            "items": {
                "type": "string",
            },
        },
        "contextual_evidence": {
            "type": "array",
            "items": {
                "type": "string",
            },
        },
        "explanation": {
            "type": "string",
        },
        "adaptation_recommendation": {
            "type": "object",
            "properties": {
                "required": {
                    "type": "boolean",
                },
                "reason": {
                    "type": "string",
                },
            },
            "required": [
                "required",
                "reason",
            ],
            "additionalProperties": False,
        },
    },
    "required": [
        "classification",
        "confidence",
        "numerical_evidence",
        "contextual_evidence",
        "explanation",
        "adaptation_recommendation",
    ],
    "additionalProperties": False,
}


def interpret_structured_state(
    structured_state: dict,
    *,
    model: str = "qwen3:8b",
) -> dict:
    response = chat(
        model=model,
        messages=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": json.dumps(
                    structured_state,
                    ensure_ascii=False,
                ),
            },
        ],
        format=OUTPUT_SCHEMA,
        options={
            "temperature": 0,
        },
        think=False,
    )

    content = response.message.content

    if not content:
        raise ValueError(
            "Ollama returned an empty response."
        )

    return json.loads(content)