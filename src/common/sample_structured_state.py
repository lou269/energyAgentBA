import copy
import json
from typing import cast

from src.structured_state.structured_state_schema import StructuredState


_BASE_STATE_JSON = """
{
  "analysis": {
    "daily_std": 52.71698472221818,
    "daily_std_expected": 45.19832571806167,
    "today_mean_expected_w": null,
    "weekday_expected_w": 320.81622125,
    "weekly_mean_w": null,
    "weekly_mean_expected_w": null,
    "long_term_window_mean_w": 405.7294889722222,
    "long_term_expected_w": null,
    "trend": "decreasing",
    "trend_change": -0.4256972486075171,
    "trend_slope_w_per_hour": -7.285383326086958,
    "weekday_deviation": 3.1141426541878765
  },
  "anomaly": {
    "available_scales": [
      "daily",
      "weekday",
      "long_term"
    ],
    "direction": "high",
    "dominant_scale": "daily",
    "level": "strong_anomaly",
    "peak_timestamp": "2015-12-15T10:00:00+00:00",
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
    "sustained_scales": [],
    "sustained_drift": false,
    "score": 3.7674342117758495
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
  "forecast": {
    "config_version": "0.5",
    "horizon_hours": 24,
    "model_id": "C2",
    "origin": "2015-12-15T11:00:00+00:00",
    "points": [
      {
        "lower_w": 136.31300837474032,
        "predicted_power_w": 459.3497910513548,
        "timestamp": "2015-12-15T11:00:00+00:00",
        "upper_w": 806.7920047346432
      },
      {
        "lower_w": 93.8402941508344,
        "predicted_power_w": 425.0973395948347,
        "timestamp": "2015-12-15T12:00:00+00:00",
        "upper_w": 753.1893577572625
      },
      {
        "lower_w": 103.4889395873406,
        "predicted_power_w": 413.2488958377861,
        "timestamp": "2015-12-15T13:00:00+00:00",
        "upper_w": 747.5874883269981
      },
      {
        "lower_w": 119.3312201216318,
        "predicted_power_w": 426.7827945700898,
        "timestamp": "2015-12-15T14:00:00+00:00",
        "upper_w": 724.2105116214306
      },
      {
        "lower_w": 133.5124260340953,
        "predicted_power_w": 455.0255445357891,
        "timestamp": "2015-12-15T15:00:00+00:00",
        "upper_w": 767.924891087322
      },
      {
        "lower_w": 187.1947104943323,
        "predicted_power_w": 485.35949638543434,
        "timestamp": "2015-12-15T16:00:00+00:00",
        "upper_w": 789.8196574799408
      },
      {
        "lower_w": 195.4736537039947,
        "predicted_power_w": 513.1964267653383,
        "timestamp": "2015-12-15T17:00:00+00:00",
        "upper_w": 824.5333749644994
      },
      {
        "lower_w": 202.7136422944788,
        "predicted_power_w": 540.8987890997116,
        "timestamp": "2015-12-15T18:00:00+00:00",
        "upper_w": 844.9581477042038
      },
      {
        "lower_w": 275.9146453215607,
        "predicted_power_w": 567.7135020085854,
        "timestamp": "2015-12-15T19:00:00+00:00",
        "upper_w": 879.6057890056105
      },
      {
        "lower_w": 265.2689513703411,
        "predicted_power_w": 582.136795833332,
        "timestamp": "2015-12-15T20:00:00+00:00",
        "upper_w": 901.8922222546336
      },
      {
        "lower_w": 276.6201196451436,
        "predicted_power_w": 566.1521429070211,
        "timestamp": "2015-12-15T21:00:00+00:00",
        "upper_w": 897.4885095755312
      },
      {
        "lower_w": 189.55496324323985,
        "predicted_power_w": 509.21612311195395,
        "timestamp": "2015-12-15T22:00:00+00:00",
        "upper_w": 844.7848227877519
      },
      {
        "lower_w": 87.51046299147498,
        "predicted_power_w": 419.87740065209937,
        "timestamp": "2015-12-15T23:00:00+00:00",
        "upper_w": 727.3112980382223
      },
      {
        "lower_w": 10.699829921087112,
        "predicted_power_w": 324.2205325299127,
        "timestamp": "2015-12-16T00:00:00+00:00",
        "upper_w": 642.7724799842188
      },
      {
        "lower_w": -66.9227759064721,
        "predicted_power_w": 251.74682905471025,
        "timestamp": "2015-12-16T01:00:00+00:00",
        "upper_w": 578.4492609078482
      },
      {
        "lower_w": -112.86022608186596,
        "predicted_power_w": 219.9968878482413,
        "timestamp": "2015-12-16T02:00:00+00:00",
        "upper_w": 528.060926198621
      },
      {
        "lower_w": -95.36420413093404,
        "predicted_power_w": 229.30488888950248,
        "timestamp": "2015-12-16T03:00:00+00:00",
        "upper_w": 544.3393358423043
      },
      {
        "lower_w": -76.42487388066228,
        "predicted_power_w": 269.1157113302455,
        "timestamp": "2015-12-16T04:00:00+00:00",
        "upper_w": 593.0087174956674
      },
      {
        "lower_w": 22.071952243598,
        "predicted_power_w": 327.3656407732127,
        "timestamp": "2015-12-16T05:00:00+00:00",
        "upper_w": 645.8705937082982
      },
      {
        "lower_w": 85.6758171262601,
        "predicted_power_w": 393.9137834452989,
        "timestamp": "2015-12-16T06:00:00+00:00",
        "upper_w": 678.6666531432767
      },
      {
        "lower_w": 147.92377854384227,
        "predicted_power_w": 457.4381298526461,
        "timestamp": "2015-12-16T07:00:00+00:00",
        "upper_w": 779.362654717964
      },
      {
        "lower_w": 167.51610782301665,
        "predicted_power_w": 503.1610528236909,
        "timestamp": "2015-12-16T08:00:00+00:00",
        "upper_w": 825.878026267355
      },
      {
        "lower_w": 188.21746019719757,
        "predicted_power_w": 517.7626646676785,
        "timestamp": "2015-12-16T09:00:00+00:00",
        "upper_w": 844.7959371951673
      },
      {
        "lower_w": 177.16699423974063,
        "predicted_power_w": 499.0458934429255,
        "timestamp": "2015-12-16T10:00:00+00:00",
        "upper_w": 832.6520065392092
      }
    ],
    "run_id": "validation_003",
    "summary": {
      "mean_interval_width_w": 637.0632404129152,
      "mean_w": 431.5469607088082,
      "peak_timestamp": "2015-12-15T20:00:00+00:00",
      "peak_w": 582.136795833332
    }
  },
  "observation": {
    "current_power_w": 1319.8837,
    "observation_end": "2015-12-15T11:00:00+00:00",
    "observation_start": "2015-12-15T10:00:00+00:00",
    "value_implausible": false
  },
  "schema_version": "1.7"
}
"""

_BASE_STATE = json.loads(_BASE_STATE_JSON)


def valid_structured_state() -> StructuredState:
    return cast(StructuredState, copy.deepcopy(_BASE_STATE))
