import logging
from pathlib import Path

import numpy as np

from experiments.proactive_cycle.pc_outlook import (
    build_outlook_state,
    infer_outlook,
    weekday_reference,
)
from src.common.timestamps import local_date_text
from src.config.config_forecasting import CycleConfig, LLMConfig
from src.llm.client import OllamaClient
from src.llm.inference import LLMInferenceError
from src.pipeline.comparison_harness import (
    ScenarioData,
    coldstart_history,
    observations_since,
)
from src.pipeline.daily_cycle import CycleState, run_cycle
from src.pipeline.io import append_jsonl

logger = logging.getLogger(__name__)


def run_outlook_days(
    scenario: ScenarioData,
    cycle_config: CycleConfig,
    outlook_file: Path,
    *,
    prompt: str,
    llm_config: LLMConfig,
    decimals: int,
    local_timezone: str,
) -> None:
    np.random.seed(cycle_config.forecasting_config.seed)
    analysis_config = cycle_config.numerical_analysis_config

    state = CycleState(
        history=coldstart_history(
            scenario.target_series, scenario.decision_times[0], local_timezone
        ),
        prophet_model=None,
        model_history=None,
        model_fitted_at=None,
    )
    client = OllamaClient(timeout_seconds=llm_config.request_timeout_seconds)

    try:
        for decision_time in scenario.decision_times:
            new_observations = observations_since(
                scenario.target_series, state.history, decision_time
            )
            result, state = run_cycle(
                state,
                new_observations,
                decision_time,
                cycle_config,
                local_timezone=local_timezone,
            )

            usual_mean_w, retransformation_factor = weekday_reference(
                state.history,
                decision_time,
                rolling_days=analysis_config.reference_window_rolling_days,
                min_samples=analysis_config.min_weekday_reference_samples,
                robust="weekday" in analysis_config.single_day_scales,
                local_timezone=local_timezone,
            )
            outlook_state = build_outlook_state(
                result.forecast,
                decision_time,
                usual_mean_w=usual_mean_w,
                retransformation_factor=retransformation_factor,
                decimals=decimals,
                local_timezone=local_timezone,
            )
            try:
                output = infer_outlook(
                    outlook_state, client=client, prompt=prompt, llm_config=llm_config
                )
                error = None
            except LLMInferenceError as failure:
                output = None
                error = failure.attempts[-1].validation_error

            append_jsonl(
                {"state": outlook_state, "output": output, "error": error},
                outlook_file,
            )
            logger.info(
                "%s: %s",
                local_date_text(decision_time, local_timezone),
                "ok" if output else error,
            )
    finally:
        client.unload_model(llm_config.model)
        client.close()
