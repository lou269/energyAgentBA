import copy
import json
from typing import cast

from src.structured_state.structured_state_schema import StructuredState


_BASE_STATE_JSON = """
{
  "anomaly": {
    "available_scales": [
      "daily",
      "weekday",
      "long_term"
    ],
    "alarm_scales": [
      "daily",
      "weekday"
    ],
    "direction": "high",
    "level": "unusual",
    "scale_anomaly_streak_days": {
      "weekly": null,
      "long_term": 1.0
    },
    "scale_exceeding_since": {
      "weekly": null,
      "long_term": "2015-12-15"
    },
    "scale_deviation_pct": {
      "weekday": 311.41426541878765,
      "weekly": null,
      "long_term": 225.3183
    },
    "sustained_scales": [],
    "sustained_drift": false
  },
  "context": {
    "events": [
      {
        "end": "2015-12-22T00:00:00+00:00",
        "event_id": "event-2015-12",
        "title": "Urlaub bei Oma",
        "known_at": "2015-11-15T00:00:00+00:00",
        "start": "2015-12-15T00:00:00+00:00"
      }
    ],
    "retrieved_at": "2015-12-16T00:00:00+00:00",
    "source": "simulated_calendar",
    "source_available": true,
    "window_end": "2015-12-17T00:00:00+00:00",
    "window_start": "2015-12-15T00:00:00+00:00"
  },
  "decision_time": "2015-12-16T00:00:00+00:00",
  "observation": {
    "observation_end": "2015-12-16T00:00:00+00:00",
    "observation_start": "2015-12-15T00:00:00+00:00",
    "value_implausible": false
  },
  "schema_version": "2.4"
}
"""

_BASE_STATE = json.loads(_BASE_STATE_JSON)


def valid_structured_state() -> StructuredState:
    return cast(StructuredState, copy.deepcopy(_BASE_STATE))
