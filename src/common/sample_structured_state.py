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
    "direction": "high",
    "level": "strong_anomaly",
    "scale_scores": {
      "daily": 3.7674342117758495,
      "weekday": 3.734920041231248,
      "weekly": null,
      "long_term": 3.264114829329143
    },
    "scale_anomaly_streak_days": {
      "daily": 1.0,
      "weekday": 1.0,
      "weekly": null,
      "long_term": 1.0
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
        "event_id": "vacation-2015-12",
        "event_type": "absence",
        "known_at": "2015-11-15T00:00:00+00:00",
        "start": "2015-12-15T00:00:00+00:00"
      }
    ],
    "retrieved_at": "2015-12-15T11:00:00+00:00",
    "source": "simulated_calendar",
    "source_available": true,
    "window_end": "2015-12-16T11:00:00+00:00",
    "window_start": "2015-12-14T11:00:00+00:00"
  },
  "decision_time": "2015-12-15T11:00:00+00:00",
  "observation": {
    "observation_end": "2015-12-15T11:00:00+00:00",
    "observation_start": "2015-12-15T10:00:00+00:00",
    "value_implausible": false
  },
  "schema_version": "1.8"
}
"""

_BASE_STATE = json.loads(_BASE_STATE_JSON)


def valid_structured_state() -> StructuredState:
    return cast(StructuredState, copy.deepcopy(_BASE_STATE))
