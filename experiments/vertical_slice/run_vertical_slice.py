# python -m experiments.vertical_slice.run_vertical_slice

from __future__ import annotations

import json

import pandas as pd

from experiments.vertical_slice.llm.llm_client import interpret_structured_state
#from experiments.vertical_slice.llm.llm_client_new import interpret_structured_state 
from src.config.project_config import ProjectConfig
from experiments.vertical_slice.forecasting.baselines import (
    build_baseline_forecasts,
)
from experiments.vertical_slice.forecasting.prophet_forecast import (
    build_prophet_forecasts,
)
from experiments.vertical_slice.context.simulated_calendar import (
    build_no_calendar_context,
    build_normal_calendar_context,
    build_vacation_calendar_context,
)
from experiments.vertical_slice.state.build_structured_state import (
    build_structured_state,
    summarize_prophet_forecast,
)

FORECAST_HOURS = 24
ROLLING_WINDOW_DAYS = 7


def main():
    project_config = ProjectConfig()

    # 1. Bereits vorhandene stündliche Analyse laden
    data = pd.read_csv(
        project_config.numerical_analysis_output_dir
        / "anomaly_scores_hourly.csv",
        parse_dates=["timestamp"],
        index_col="timestamp",
    )

    # 2. Validation-Split auswählen
    validation = data.loc[
        data["split"].eq("validation")
    ]

    if validation.empty:
        raise ValueError(
            "No validation data found in anomaly_scores_hourly.csv."
        )

    # 3. Forecast-Zeitpunkt ungefähr in der Mitte
    #    der Validation wählen
    cutoff = validation.index[
        len(validation) // 2
    ]

    # Alles, was zum Zeitpunkt t bekannt ist
    history = data.loc[
        :cutoff,
        "current_power",
    ]

    # Tatsächliche nächsten 24 Stunden
    # ausschließlich für spätere Evaluation
    future = data.loc[
        cutoff + pd.Timedelta(hours=1):
        cutoff + pd.Timedelta(hours=FORECAST_HOURS),
        "current_power",
    ]

    # 4. Baseline-Forecasts
    baseline_forecasts = build_baseline_forecasts(
        history,
        horizon_hours=FORECAST_HOURS,
    )

    # 5. Prophet-Forecasts
    prophet_forecasts = build_prophet_forecasts(
        history,
        horizon_hours=FORECAST_HOURS,
        rolling_window_days=ROLLING_WINDOW_DAYS,
    )

    # 6. Prophet-Forecasts zusammenfassen
    full_history_summary = summarize_prophet_forecast(
        prophet_forecasts["full_history"]
    )

    rolling_7d_summary = summarize_prophet_forecast(
        prophet_forecasts["rolling_7d"]
    )

    # 7. Simulierte Kalenderzustände
    no_calendar_context = build_no_calendar_context()

    normal_calendar_context = (
        build_normal_calendar_context()
    )

    vacation_calendar_context = (
        build_vacation_calendar_context(
            cutoff
        )
    )

    # 8. Structured State mit Rolling-7-Day-Prophet
    normal_state = build_structured_state(
        data=data,
        history=history,
        cutoff=cutoff,
        prophet_summary=rolling_7d_summary,
        calendar_context=normal_calendar_context,
    )

    no_calendar_state = build_structured_state(
        data=data,
        history=history,
        cutoff=cutoff,
        prophet_summary=rolling_7d_summary,
        calendar_context=no_calendar_context,
    )

    vacation_state = build_structured_state(
        data=data,
        history=history,
        cutoff=cutoff,
        prophet_summary=rolling_7d_summary,
        calendar_context=vacation_calendar_context,
    )

    # 9. Ergebnisse für den experimentellen Test anzeigen
    print(f"Cutoff: {cutoff}")
    print(f"History observations: {len(history)}")
    print(f"Future observations: {len(future)}")

    print("\nBaseline forecasts:")
    print(baseline_forecasts)

    print("\nProphet - Full History Summary:")
    print(full_history_summary)

    print("\nProphet - Rolling 7 Days Summary:")
    print(rolling_7d_summary)

    print("\nStructured State - Normal:")
    print(
        json.dumps(
            normal_state,
            indent=2,
        )
    )

    print("\nStructured State - No Calendar:")
    print(
        json.dumps(
            no_calendar_state,
            indent=2,
        )
    )

    print("\nStructured State - Vacation:")
    print(
        json.dumps(
            vacation_state,
            indent=2,
        )
    )
    normal_llm_result = interpret_structured_state(
        normal_state
    )

    print("\nLLM - Normal State:")
    print(
        json.dumps(
            normal_llm_result,
            indent=2,
            ensure_ascii=False,
        )
    )
    
    no_calendar_llm_result = interpret_structured_state(
        no_calendar_state
    )

    vacation_llm_result = interpret_structured_state(
        vacation_state
    )

    print("\nLLM - No Calendar:")
    print(
        json.dumps(
            no_calendar_llm_result,
            indent=2,
            ensure_ascii=False,
        )
    )

    print("\nLLM - Vacation:")
    print(
        json.dumps(
            vacation_llm_result,
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()