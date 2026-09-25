from dataclasses import dataclass, replace

from src.config.config_forecasting import (
    C2_EXPANDING,
    C3_ROLLING_30,
    MODEL_LABELS as FORECAST_MODEL_LABELS,
    ProphetVariantConfig,
)

FORECAST_RUN_PREFIX = "e3_forecast"
DRIFT_RUN_PREFIX = "e3_drift"
# vom Runner geschrieben, vom Report gelesen
ORIGIN_METRICS_FILE = "origin_metrics"
DRIFT_RESULTS_FILE = "e3_drift_results"

# unterscheidet sich von C2 nur in der Jahressaisonalität
S1_EXPANDING_YEARLY = replace(C2_EXPANDING, model_id="S1", yearly_seasonality=True)


@dataclass(frozen=True)
class E3Config:
    experiment_id: str = "E3"
    split: str = "train"

    # forecast: ein volles Jahr, davor gut ein Jahr Historie ab Datenbeginn (01.04.2013). Liegt ganz im Train-Split (bis 29.04.2015)
    forecast_start_date: str = "2014-04-15"
    forecast_days: int = 365
    prophet_variants: tuple[ProphetVariantConfig, ...] = (
        C3_ROLLING_30,
        C2_EXPANDING,
        S1_EXPANDING_YEARLY,
    )
    # (Variante, Referenz): Jahressaisonalität allein, längere Historie allein, beides gegen das produktive Modell
    comparisons: tuple[tuple[str, str], ...] = (
        ("S1", "C2"),
        ("C2", "C3_30"),
        ("S1", "C3_30"),
    )

    # drift: abrupte Stufe und Rampen auf dasselbe Niveau (scale_factor), das System wie im Betrieb, nur Regel statt LLM.
    # Rampen höchstens so lang wie margin_after_days der Standard-Szenarien (60), sonst endet der Lauf mitten im Anstieg
    kinds: tuple[str, ...] = ("control", "scaled", "ramp_28", "ramp_56")
    system_id: str = "SYS2"


MODEL_LABELS: dict[str, str] = FORECAST_MODEL_LABELS | {
    "S1": "S1 expanding + Jahressaison"
}
