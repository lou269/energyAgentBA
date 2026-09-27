from dataclasses import dataclass

import pandas as pd

from experiments.common.evaluation import summarize_paired_differences
from src.forecasting.evaluation import select_primary_naive_reference


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


def summarize_overall(results: dict[str, pd.DataFrame]) -> pd.DataFrame:
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

    return pd.DataFrame(
        {
            "mae_w": overall["mae_w"],
            "rmse_w": overall["rmse_w"],
            "mape_pct": overall["mape_pct"],
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
) -> list[ModeSummary]:
    """Je Modus alles, was Setup, Kennzahlen und Hinweise brauchen"""
    summaries = []

    for mode, results in results_by_mode.items():
        best = _best_variant(results, variant_ids)
        reference = str(results["primary_naive_reference"]["model_id"].iloc[0])
        overall = summarize_overall(results)
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
