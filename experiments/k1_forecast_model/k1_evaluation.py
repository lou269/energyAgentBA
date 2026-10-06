from dataclasses import dataclass

import pandas as pd

from experiments.common.evaluation import (
    add_overall_rows,
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


def _best_variant(
    results: dict[str, pd.DataFrame], variant_ids: tuple[str, ...]
) -> str:
    overall = results["overall_metrics"].set_index("model_id")
    return str(overall.loc[list(variant_ids), "mae_w"].idxmin())


def summarize_daily_error(
    forecasts: pd.DataFrame, actual_daily_mean_w: pd.Series
) -> pd.DataFrame:
    """Fehler des Tagesmittels je Modell (Mittel der 24 Prognosewerte gegen das Ist-Tagesmittel), nur Tage mit lauter bewerteten Stunden"""
    forecasts = forecasts.assign(
        forecast_origin=pd.to_datetime(forecasts["forecast_origin"], utc=True)
    )
    complete = forecasts.groupby(["model_id", "forecast_origin"])[
        "target_eligible"
    ].transform("all")

    # treated_daily liegt auf der lokalen Mitternacht, also genau auf dem forecast_origin
    days = score_daily_means(
        forecasts.loc[complete],
        actual_daily_mean_w,
        group_column="model_id",
        day_column="forecast_origin",
    )
    by_model = days.groupby("model_id")

    return pd.DataFrame(
        {
            "daily_mae_w": by_model["day_error_w"].mean(),
            "daily_mape_pct": (days["day_error_w"] / days["actual_w"])
            .groupby(days["model_id"])
            .mean()
            * 100,
            "daily_count": by_model.size(),
        }
    )


def summarize_overall(
    results: dict[str, pd.DataFrame], actual_daily_mean_w: pd.Series
) -> pd.DataFrame:
    """Gesamtfehler je Modell, Skill gegen die naive Referenz des Modus und Abdeckung des Prognoseintervalls"""
    reference = str(results["primary_naive_reference"]["model_id"].iloc[0])
    overall = results["overall_metrics"].set_index("model_id")

    skill = results["mae_skill"]
    skill = skill.loc[skill["reference_model_id"].eq(reference)].set_index("model_id")[
        "mae_skill"
    ]

    intervals = results["interval_metrics"]
    coverage = intervals.loc[intervals["scope"].eq("overall")].set_index("model_id")[
        "empirical_coverage"
    ]

    daily = summarize_daily_error(results["forecasts"], actual_daily_mean_w)

    return pd.DataFrame(
        {
            "mae_w": overall["mae_w"],
            "rmse_w": overall["rmse_w"],
            "mape_pct": overall["mape_pct"],
            "daily_mae_w": daily["daily_mae_w"],
            "daily_mape_pct": daily["daily_mape_pct"],
            "daily_count": daily["daily_count"],
            "skill_pct": skill * 100,
            "coverage_pct": coverage * 100,
            "refit_seconds": overall["total_refit_runtime_seconds"],
            "retraining_count": overall["retraining_count"],
        }
    ).sort_values("mae_w")


def compare_to_best_variant(
    results_by_mode: dict[str, dict[str, pd.DataFrame]], variant_ids: tuple[str, ...]
) -> pd.DataFrame:
    frames = []

    for mode, results in results_by_mode.items():
        best = _best_variant(results, variant_ids)
        origins = results["origin_metrics"]
        mae = origins.loc[origins["model_id"].isin(variant_ids)].pivot(
            index="forecast_origin", columns="model_id", values="mae_w"
        )
        paired = summarize_paired_differences(mae, best).sort_values("mean_delta")
        frames.append(paired.assign(mode=mode, reference=best))

    return pd.concat(frames, ignore_index=True)


@dataclass(frozen=True)
class ModeSummary:
    mode: str
    best_model: str
    best_mae_w: float
    reference_model: str
    reference_mae_w: float
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


def summarize_modes(
    results_by_mode: dict[str, dict[str, pd.DataFrame]],
    paired: pd.DataFrame,
    variant_ids: tuple[str, ...],
    actual_daily_mean_w: pd.Series,
) -> list[ModeSummary]:
    """Je Modus alles, was Setup, Kennzahlen und Hinweise brauchen"""
    summaries = []

    for mode, results in results_by_mode.items():
        best = _best_variant(results, variant_ids)
        reference = str(results["primary_naive_reference"]["model_id"].iloc[0])
        overall = summarize_overall(results, actual_daily_mean_w)
        metrics = results["overall_metrics"].set_index("model_id")

        skill = overall.loc[list(variant_ids), "skill_pct"]
        exclusions = results["target_exclusions"]
        exclusions = exclusions.loc[exclusions["model_id"].eq(best)]
        forecast_days = results["origin_metrics"]["forecast_day"]
        mode_paired = paired.loc[paired["mode"].eq(mode)]

        summaries.append(
            ModeSummary(
                mode=mode,
                best_model=best,
                best_mae_w=overall["mae_w"][best],
                reference_model=reference,
                reference_mae_w=overall["mae_w"][reference],
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

    return summaries


@dataclass(frozen=True)
class SeasonalForecastSummary:
    by_month: pd.DataFrame
    paired: pd.DataFrame


def summarize_seasonal_forecast(
    origin_metrics: pd.DataFrame, comparisons: tuple[tuple[str, str], ...]
) -> SeasonalForecastSummary:
    """MAE je Kalendermonat und Modell, dazu die gepaarten Differenzen über das ganze Jahr je (Variante, Referenz)"""
    months = origin_metrics.assign(month=origin_metrics["forecast_day"].str[:7])
    by_month = (
        add_overall_rows(months, "month", WHOLE_YEAR)
        .pivot_table(index="month", columns="model_id", values="mae_w")
        .rename_axis(columns=None)
        .reset_index()
    )

    mae = origin_metrics.pivot(
        index="forecast_origin", columns="model_id", values="mae_w"
    )
    paired = pd.concat(
        [
            summarize_paired_differences(mae[[reference, variant]], reference).assign(
                reference=reference
            )
            for variant, reference in comparisons
        ],
        ignore_index=True,
    )

    return SeasonalForecastSummary(by_month=by_month, paired=paired)
