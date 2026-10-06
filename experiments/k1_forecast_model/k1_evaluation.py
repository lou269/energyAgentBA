from dataclasses import dataclass

import pandas as pd

from experiments.common.evaluation import (
    add_overall_rows,
    local_dates,
    summarize_paired_differences,
)
from src.forecasting.evaluation import (
    score_daily_means,
    select_primary_naive_reference,
)

# steht in der Monatstabelle als letzte Zeile, sortiert hinter "2015-04"
WHOLE_YEAR = "Jahr"


def choose_primary_naive_reference(
    overall_metrics: pd.DataFrame,
    *,
    split: str,
    baseline_model_ids: tuple[str, ...],
    configured_reference: str | None,
) -> str | None:
    # auf der Validierung gewählt, auf dem Test-Split gilt die vorher festgelegte Referenz
    if split == "validation":
        return select_primary_naive_reference(overall_metrics, baseline_model_ids)
    return configured_reference


def score_forecast_days(
    forecasts: pd.DataFrame, actual_daily_mean_w: pd.Series
) -> pd.DataFrame:
    """Fehler des Tagesmittels je Modell und Prognosetag (Mittel der 24 Prognosewerte gegen das Ist-Tagesmittel), ohne Ist-Tagesmittel bleibt der Fehler leer"""
    forecasts = forecasts.assign(
        forecast_origin=pd.to_datetime(forecasts["forecast_origin"], utc=True)
    )

    # treated_daily liegt auf der lokalen Mitternacht, also genau auf dem forecast_origin
    days = score_daily_means(
        forecasts,
        actual_daily_mean_w,
        group_column="model_id",
        day_column="forecast_origin",
    )

    return days.assign(forecast_day=local_dates(days["forecast_origin"]))


def summarize_daily_error(days: pd.DataFrame) -> pd.DataFrame:
    by_model = days.groupby("model_id")

    return pd.DataFrame(
        {
            "daily_mae_w": by_model["day_error_w"].mean(),
            "daily_mape_pct": (days["day_error_w"] / days["actual_w"])
            .groupby(days["model_id"])
            .mean()
            * 100,
            "daily_count": by_model["day_error_w"].count(),
        }
    )


def summarize_overall(
    results: dict[str, pd.DataFrame], days: pd.DataFrame
) -> pd.DataFrame:
    """Gesamtfehler je Modell, Skill im Tagesfehler gegen die naive Referenz des Modus und Abdeckung des Prognoseintervalls"""
    reference = str(results["primary_naive_reference"]["model_id"].iloc[0])
    overall = results["overall_metrics"].set_index("model_id")
    daily = summarize_daily_error(days)
    skill = 1 - daily["daily_mae_w"] / daily["daily_mae_w"][reference]

    intervals = results["interval_metrics"]
    coverage = intervals.loc[intervals["scope"].eq("overall")].set_index("model_id")[
        "empirical_coverage"
    ]

    return pd.DataFrame(
        {
            "daily_mae_w": daily["daily_mae_w"],
            "daily_mape_pct": daily["daily_mape_pct"],
            "daily_count": daily["daily_count"],
            "mae_w": overall["mae_w"],
            "rmse_w": overall["rmse_w"],
            "mape_pct": overall["mape_pct"],
            "skill_pct": skill * 100,
            "coverage_pct": coverage * 100,
            "refit_seconds": overall["total_refit_runtime_seconds"],
            "retraining_count": overall["retraining_count"],
        }
    ).sort_values("daily_mae_w")


def best_variant(overall: pd.DataFrame, variant_ids: tuple[str, ...]) -> str:
    # gewählt wird über den Tagesfehler, nur die Tagesmenge geht an den Nutzer
    return str(overall.loc[list(variant_ids), "daily_mae_w"].idxmin())


def compare_to_best_variant(
    days: pd.DataFrame, variant_ids: tuple[str, ...], best: str
) -> pd.DataFrame:
    """Tagesfehler jeder Variante minus Tagesfehler der besten, gepaart je Prognosetag"""
    day_errors = days.loc[days["model_id"].isin(variant_ids)].pivot(
        index="forecast_origin", columns="model_id", values="day_error_w"
    )

    return summarize_paired_differences(day_errors, best).sort_values("mean_delta")


@dataclass(frozen=True)
class ModeSummary:
    mode: str
    best_model: str
    best_daily_mae_w: float
    reference_model: str
    reference_daily_mae_w: float
    skill_min_pct: float
    skill_max_pct: float
    worse_than_best: int
    compared_variants: int
    daily_count: int
    excluded_target_count: int
    possible_target_count: int
    # (Grund, Anzahl) der nicht bewerteten Zielstunden des besten Modells
    exclusion_reasons: list[tuple[str, int]]
    first_forecast_day: str
    last_forecast_day: str
    forecast_day_count: int


@dataclass(frozen=True)
class RetrainingSummary:
    modes: list[ModeSummary]
    # je Modus Gesamtfehler je Modell und Tagesfehler je Modell und Prognosetag
    overall: dict[str, pd.DataFrame]
    days: dict[str, pd.DataFrame]
    # Abstand jeder Variante zur besten, alle Modi
    paired: pd.DataFrame


def summarize_retraining(
    results_by_mode: dict[str, dict[str, pd.DataFrame]],
    variant_ids: tuple[str, ...],
    actual_daily_mean_w: pd.Series,
) -> RetrainingSummary:
    """Je Modus Gesamtfehler, beste Variante nach Tagesfehler und gepaarter Abstand zu ihr, dazu alles für Setup, Kennzahlen und Hinweise"""
    modes = []
    overall_by_mode = {}
    days_by_mode = {}
    paired_frames = []

    for mode, results in results_by_mode.items():
        days = score_forecast_days(results["forecasts"], actual_daily_mean_w)
        overall = summarize_overall(results, days)
        best = best_variant(overall, variant_ids)
        reference = str(results["primary_naive_reference"]["model_id"].iloc[0])
        metrics = results["overall_metrics"].set_index("model_id")
        mode_paired = compare_to_best_variant(days, variant_ids, best)

        skill = overall.loc[list(variant_ids), "skill_pct"]
        exclusions = results["target_exclusions"]
        exclusions = exclusions.loc[exclusions["model_id"].eq(best)]
        forecast_days = results["origin_metrics"]["forecast_day"]

        overall_by_mode[mode] = overall
        days_by_mode[mode] = days
        paired_frames.append(mode_paired.assign(mode=mode, reference=best))
        modes.append(
            ModeSummary(
                mode=mode,
                best_model=best,
                best_daily_mae_w=overall["daily_mae_w"][best],
                reference_model=reference,
                reference_daily_mae_w=overall["daily_mae_w"][reference],
                skill_min_pct=skill.min(),
                skill_max_pct=skill.max(),
                worse_than_best=int(mode_paired["exceeds_noise"].sum()),
                compared_variants=len(mode_paired),
                daily_count=int(overall["daily_count"][best]),
                excluded_target_count=metrics["excluded_target_count"][best],
                possible_target_count=metrics["possible_target_count"][best],
                exclusion_reasons=list(
                    zip(
                        exclusions["target_exclusion_reason"],
                        exclusions["excluded_target_count"],
                    )
                ),
                first_forecast_day=forecast_days.min(),
                last_forecast_day=forecast_days.max(),
                forecast_day_count=forecast_days.nunique(),
            )
        )

    return RetrainingSummary(
        modes=modes,
        overall=overall_by_mode,
        days=days_by_mode,
        paired=pd.concat(paired_frames, ignore_index=True),
    )


@dataclass(frozen=True)
class SeasonalForecastSummary:
    by_month: pd.DataFrame
    paired: pd.DataFrame


def summarize_seasonal_forecast(
    forecasts: pd.DataFrame,
    actual_daily_mean_w: pd.Series,
    comparisons: tuple[tuple[str, str], ...],
) -> SeasonalForecastSummary:
    """Tagesfehler je Kalendermonat und Modell, dazu die gepaarten Differenzen über das ganze Jahr je (Variante, Referenz)"""
    days = score_forecast_days(forecasts, actual_daily_mean_w)
    months = days.assign(month=days["forecast_day"].dt.strftime("%Y-%m"))
    by_month = (
        add_overall_rows(months, "month", WHOLE_YEAR)
        .pivot_table(index="month", columns="model_id", values="day_error_w")
        .rename_axis(columns=None)
        .reset_index()
    )

    day_errors = days.pivot(
        index="forecast_origin", columns="model_id", values="day_error_w"
    )
    paired = pd.concat(
        [
            summarize_paired_differences(
                day_errors[[reference, variant]], reference
            ).assign(reference=reference)
            for variant, reference in comparisons
        ],
        ignore_index=True,
    )

    return SeasonalForecastSummary(by_month=by_month, paired=paired)
