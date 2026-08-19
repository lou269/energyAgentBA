# python -m experiments.vertical_slice.run2

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

import pandas as pd

from experiments.vertical_slice.llm.llm_client_new import (
    interpret_structured_state,
)
from experiments.vertical_slice.llm_evaluation.run_evaluation import run_llm_evaluation
from src.config.project_config import ProjectConfig
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

# Modelle, die miteinander verglichen werden sollen
LLM_MODELS = [
    "qwen3:4b",
    "qwen3:8b",
    "qwen3.5:9b",
    "llama3.1:8b"
]

LLM_OUTPUT_LANGUAGE = "English"
LLM_SEED = 42
LLM_MAX_ATTEMPTS = 2


LLM_COMPARISON_FILE = (
    Path(__file__).resolve().parent
    / "results"
    / "llm_model_comparison.json"
)

def log_model_status(message: str) -> None:
    timestamp = datetime.now().astimezone().strftime(
        "%Y-%m-%d %H:%M:%S"
    )
    print(f"[{timestamp}] {message}")
    
    
def main() -> None:
    project_config = ProjectConfig()

    # 1. Vorhandene stündliche Analyse laden
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
            "No validation data found in "
            "anomaly_scores_hourly.csv."
        )

    # 3. Forecast-Zeitpunkt in der Mitte der Validation
    cutoff = validation.index[
        len(validation) // 2
    ]

    history = data.loc[
        :cutoff,
        "current_power",
    ]

    # 4. Prophet-Forecast
    prophet_forecasts = build_prophet_forecasts(
        history,
        horizon_hours=FORECAST_HOURS,
        rolling_window_days=ROLLING_WINDOW_DAYS,
    )

    rolling_7d_summary = summarize_prophet_forecast(
        prophet_forecasts["rolling_7d"]
    )

    # 5. Simulierte Kalenderzustände
    calendar_contexts = {
        "Normal": build_normal_calendar_context(),
        "No Calendar": build_no_calendar_context(),
        "Vacation": build_vacation_calendar_context(
            cutoff
        ),
    }

    # 6. Structured States einmal erzeugen.
    # Alle Modelle bekommen exakt denselben Input.
    states = {
        scenario_name: build_structured_state(
            data=data,
            history=history,
            cutoff=cutoff,
            prophet_summary=rolling_7d_summary,
            calendar_context=calendar_context,
        )
        for scenario_name, calendar_context
        in calendar_contexts.items()
    }

    # 7. Vergleichsergebnis vorbereiten
    comparison = {
        "run_timestamp": datetime.now(
            timezone.utc
        ).isoformat(),
        "cutoff": cutoff.isoformat(),
        "forecast_hours": FORECAST_HOURS,
        "rolling_window_days": ROLLING_WINDOW_DAYS,
        "seed": LLM_SEED,
        "output_language": LLM_OUTPUT_LANGUAGE,
        "models": {},
    }

    # 8. Alle Modelle durchlaufen
    for model in LLM_MODELS:
        model_results = {}

        start_time = perf_counter()

        log_model_status(
            f"Starting output model: {model}"
        )

        for scenario_name, structured_state in states.items():
            try:
                llm_result = interpret_structured_state(
                    structured_state,
                    model=model,
                    output_language=LLM_OUTPUT_LANGUAGE,
                    seed=LLM_SEED,
                    max_attempts=LLM_MAX_ATTEMPTS,
                )

                model_results[scenario_name] = {
                    "status": "success",
                    "structured_state": structured_state,
                    "llm_output": llm_result,
                }

            except Exception as error:
                cause = error.__cause__

                model_results[scenario_name] = {
                    "status": "error",
                    "structured_state": structured_state,
                    "llm_output": None,
                    "error": {
                        "type": type(error).__name__,
                        "message": str(error),
                        "cause_type": (
                            type(cause).__name__
                            if cause is not None
                            else None
                        ),
                        "cause_message": (
                            str(cause)
                            if cause is not None
                            else None
                        ),
                    },
                }

                log_model_status(
                    f"Failed model={model}, "
                    f"scenario={scenario_name}: "
                    f"{type(error).__name__}: {error}"
                )

        comparison["models"][model] = model_results

        duration_seconds = perf_counter() - start_time

        log_model_status(
            f"Finished output model: {model} "
            f"({duration_seconds:.2f}s)"
        )
    # 9. Gesamten Modellvergleich speichern
    LLM_COMPARISON_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with LLM_COMPARISON_FILE.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            comparison,
            file,
            indent=2,
            ensure_ascii=False,
            default=str,
        )
        
    base_state = states["Normal"]

    run_llm_evaluation(base_state)


if __name__ == "__main__":
    main()
    #ollama run qwen3.5:9b
    #ollama run llama3.1:8b