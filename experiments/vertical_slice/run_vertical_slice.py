# python -m experiments.vertical_slice.run_vertical_slice

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from experiments.vertical_slice.llm.llm_client_new import (
    interpret_structured_state,
)
from experiments.vertical_slice.forecasting.baselines import (
    build_baseline_forecasts,
)
from experiments.vertical_slice.forecasting.prophet_forecast import (
    build_prophet_forecasts,
)
from experiments.vertical_slice.state.build_structured_state import (
    build_structured_state,
    summarize_prophet_forecast,
)
from src.config.project_config import ProjectConfig


FORECAST_HOURS = 24
ROLLING_WINDOW_DAYS = 7

LLM_MODEL = "qwen3:4b"
LLM_OUTPUT_LANGUAGE = "English"

SCENARIO_DIR = (
    Path(__file__).resolve().parent
    / "scenarios"
)

SCENARIO_NAMES = [
    "normal",
    "new_device",
    "vacation_with_context",
    "vacation_without_context",
]


def load_scenario(
    name: str,
) -> dict:
    path = SCENARIO_DIR / f"{name}.json"

    with path.open(
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


def build_detector_evidence(
    scenario: dict,
    cutoff: pd.Timestamp,
) -> dict:
    evidence = scenario.get(
        "detector_evidence",
        {},
    ).copy()

    offset = evidence.pop(
        "change_point_offset_hours",
        None,
    )

    evidence["change_point"] = (
        (
            cutoff
            + pd.Timedelta(hours=offset)
        ).isoformat()
        if offset is not None
        else None
    )

    return evidence


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

    # 3. Cutoff ungefähr in der Mitte
    #    der Validation auswählen
    cutoff = validation.index[
        len(validation) // 2
    ]

    # Nur Informationen bis einschließlich cutoff
    history = data.loc[
        :cutoff,
        "current_power",
    ]

    # Ground Truth der nächsten 24 Stunden.
    # Darf nur für spätere Evaluation benutzt werden.
    future = data.loc[
        cutoff + pd.Timedelta(hours=1):
        cutoff + pd.Timedelta(
            hours=FORECAST_HOURS
        ),
        "current_power",
    ]

    # 4. Forecast-Baselines
    baseline_forecasts = (
        build_baseline_forecasts(
            history,
            horizon_hours=FORECAST_HOURS,
        )
    )

    # 5. Prophet-Forecasts
    prophet_forecasts = (
        build_prophet_forecasts(
            history,
            horizon_hours=FORECAST_HOURS,
            rolling_window_days=(
                ROLLING_WINDOW_DAYS
            ),
        )
    )

    # 6. Forecasts zusammenfassen
    full_history_summary = (
        summarize_prophet_forecast(
            prophet_forecasts[
                "full_history"
            ]
        )
    )

    rolling_7d_summary = (
        summarize_prophet_forecast(
            prophet_forecasts[
                "rolling_7d"
            ]
        )
    )

    # 7. Allgemeine Informationen ausgeben
    print(
        f"\nCutoff: {cutoff}"
    )
    print(
        f"History observations: "
        f"{len(history)}"
    )
    print(
        f"Future observations: "
        f"{len(future)}"
    )

    print(
        "\nBaseline forecasts:"
    )
    print(
        baseline_forecasts
    )

    print(
        "\nProphet - Full History Summary:"
    )
    print(
        json.dumps(
            full_history_summary,
            indent=2,
        )
    )

    print(
        "\nProphet - Rolling 7 Days Summary:"
    )
    print(
        json.dumps(
            rolling_7d_summary,
            indent=2,
        )
    )

    # 8. Alle kontrollierten Szenarien
    #    durchlaufen
    scenario_results = []

    for scenario_name in SCENARIO_NAMES:
        print(
            "\n"
            + "=" * 70
        )
        print(
            f"SCENARIO: {scenario_name}"
        )
        print(
            "=" * 70
        )

        scenario = load_scenario(
            scenario_name
        )

        detector_evidence = (
            build_detector_evidence(
                scenario,
                cutoff,
            )
        )

        # expected wird absichtlich NICHT
        # an den Structured State gegeben.
        structured_state = (
            build_structured_state(
                data=data,
                history=history,
                cutoff=cutoff,
                prophet_summary=(
                    rolling_7d_summary
                ),
                calendar_context=(
                    scenario["context"]
                ),
                detector_evidence=(
                    detector_evidence
                ),
            )
        )

        print(
            "\nStructured State:"
        )
        print(
            json.dumps(
                structured_state,
                indent=2,
                ensure_ascii=False,
            )
        )

        # 9. LLM-Klassifikation
        llm_result = (
            interpret_structured_state(
                structured_state,
                model=LLM_MODEL,
                output_language=(
                    LLM_OUTPUT_LANGUAGE
                ),
            )
        )

        # 10. Erwartetes Ergebnis nur
        #     für Evaluation verwenden
        expected_classification = (
            scenario["expected"][
                "classification"
            ]
        )

        expected_adaptation = (
            scenario["expected"][
                "adaptation_required"
            ]
        )

        actual_classification = (
            llm_result[
                "classification"
            ]
        )

        actual_adaptation = (
            llm_result[
                "adaptation_recommendation"
            ][
                "recommended"
            ]
        )

        classification_correct = (
            actual_classification
            == expected_classification
        )

        adaptation_correct = (
            actual_adaptation
            == expected_adaptation
        )

        print(
            "\nLLM Result:"
        )
        print(
            json.dumps(
                llm_result,
                indent=2,
                ensure_ascii=False,
            )
        )

        print(
            "\nEvaluation:"
        )
        print(
            "Expected classification: "
            f"{expected_classification}"
        )
        print(
            "Actual classification:   "
            f"{actual_classification}"
        )
        print(
            "Classification correct:  "
            f"{classification_correct}"
        )

        print(
            "Expected adaptation:      "
            f"{expected_adaptation}"
        )
        print(
            "Actual adaptation:        "
            f"{actual_adaptation}"
        )
        print(
            "Adaptation correct:       "
            f"{adaptation_correct}"
        )

        scenario_results.append(
            {
                "scenario": (
                    scenario_name
                ),
                "expected_classification": (
                    expected_classification
                ),
                "actual_classification": (
                    actual_classification
                ),
                "classification_correct": (
                    classification_correct
                ),
                "expected_adaptation": (
                    expected_adaptation
                ),
                "actual_adaptation": (
                    actual_adaptation
                ),
                "adaptation_correct": (
                    adaptation_correct
                ),
            }
        )

    # 11. Kompakte Zusammenfassung
    print(
        "\n"
        + "=" * 70
    )
    print(
        "SCENARIO SUMMARY"
    )
    print(
        "=" * 70
    )

    for result in scenario_results:
        print(
            f"{result['scenario']}: "
            f"classification="
            f"{result['actual_classification']} "
            f"(expected="
            f"{result['expected_classification']}, "
            f"correct="
            f"{result['classification_correct']}), "
            f"adaptation="
            f"{result['actual_adaptation']} "
            f"(expected="
            f"{result['expected_adaptation']}, "
            f"correct="
            f"{result['adaptation_correct']})"
        )


if __name__ == "__main__":
    main()