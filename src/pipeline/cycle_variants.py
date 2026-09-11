from src.config.config_forecasting import ForecastingConfig, LLMConfig, NumericalAnalysisConfig,ProphetVariantConfig
from src.pipeline.daily_cycle import CycleConfig


# dieselben Werte wie COLD_START_PROPHET_VARIANTS in k2_cold_start, hier separat gehalten statt importiert - src/ soll nicht von experiments/ abhängen
_C1_STATIC = ProphetVariantConfig(
    model_id="C1",
    history_mode="fixed_train",
    rolling_window_hours=None,
    retraining_interval_hours=None,
)

_C2_EXPANDING = ProphetVariantConfig(
    model_id="C2",
    history_mode="expanding",
    rolling_window_hours=None,
    retraining_interval_hours=24,
)


SYS_VARIANTS: dict[str, CycleConfig] = {
    "SYS0": CycleConfig(
        forecasting_config=ForecastingConfig(selected_prophet_variant=_C1_STATIC),
        numerical_analysis_config=NumericalAnalysisConfig(),
        event_adaptation=False,
        llm_mode="off",
    ),
    "SYS1": CycleConfig(
        forecasting_config=ForecastingConfig(selected_prophet_variant=_C2_EXPANDING),
        numerical_analysis_config=NumericalAnalysisConfig(),
        event_adaptation=False,
        llm_mode="off",
    ),
    "SYS2": CycleConfig(
        forecasting_config=ForecastingConfig(selected_prophet_variant=_C2_EXPANDING),
        numerical_analysis_config=NumericalAnalysisConfig(),
        event_adaptation=True,
        llm_mode="rule",
    ),
    "SYS3": CycleConfig(
        forecasting_config=ForecastingConfig(selected_prophet_variant=_C2_EXPANDING),
        numerical_analysis_config=NumericalAnalysisConfig(),
        event_adaptation=True,
        llm_mode="real",
        llm_config=LLMConfig(model="qwen3.5:9b"),
    ),
}
