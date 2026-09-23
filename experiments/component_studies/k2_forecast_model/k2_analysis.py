# conda activate forecasting-env
# python -m experiments.component_studies.k2_forecast_model.k2_analysis [run_directory]

import sys
from pathlib import Path

import pandas as pd

from docs.plots.plot_forecast_model_vergleich import build_forecast_model_plot
from experiments.component_studies.k2_forecast_model.k2_config import SPLIT_DIRECTORY_SUFFIX
from experiments.proposal_experiments.shared_analysis import summarize_paired_differences
from src.common.result_report import write_result_report
from src.config.config_forecasting import MODEL_LABELS
from src.config.project_config import ProjectConfig
from src.pipeline.io import RAW_SUBDIR, read_raw_json, resolve_run_directory

RESULT_FILES = ("overall_metrics", "origin_metrics", "mae_skill", "interval_metrics", "target_exclusions", "primary_naive_reference")

MODE_DESCRIPTIONS = {
    "rolling": "{coldstart_days} Tage Historie vor Split-Start, wie der Online-Zyklus",
    "macro": "gesamte Historie vor Split-Start",
}
EXCLUSION_LABELS = {"missing_target": "Messwert fehlt", "target_imputed": "imputiert"}


def _read_mode(mode_directory: Path) -> dict[str, pd.DataFrame]:
    return {name: pd.read_csv(mode_directory / f"{name}.csv") for name in RESULT_FILES}


def _reference_baseline(results: dict[str, pd.DataFrame]) -> str:
    return str(results["primary_naive_reference"]["model_id"].iloc[0])


def _best_variant(results: dict[str, pd.DataFrame], variant_ids: tuple[str, ...]) -> str:
    overall = results["overall_metrics"].set_index("model_id")
    return str(overall.loc[list(variant_ids), "mae_w"].idxmin())


def build_overall_table(results: dict[str, pd.DataFrame], *, nominal_interval_level: float) -> pd.DataFrame:
    reference_baseline = _reference_baseline(results)
    overall = results["overall_metrics"].set_index("model_id")

    skill = results["mae_skill"]
    skill = skill.loc[skill["reference_model_id"].eq(reference_baseline)].set_index("model_id")["mae_skill"]

    intervals = results["interval_metrics"]
    coverage = intervals.loc[intervals["scope"].eq("overall")].set_index("model_id")["empirical_coverage"]

    table = pd.DataFrame(
        {
            "MAE [W]": overall["mae_w"],
            "RMSE [W]": overall["rmse_w"],
            "MAPE [%]": overall["mape_pct"],
            f"Skill ggü. {reference_baseline} [%]": skill * 100,
            f"Intervall-Abdeckung [%], Soll {nominal_interval_level * 100:.0f}": coverage * 100,
            "Refit-Zeit gesamt [s]": overall["total_refit_runtime_seconds"],
        }
    ).sort_values("MAE [W]")

    return table.rename(index=MODEL_LABELS).rename_axis("Modell").reset_index()


def build_paired_table(results_by_mode: dict[str, dict[str, pd.DataFrame]], variant_ids: tuple[str, ...]) -> pd.DataFrame:
    frames = []

    for mode, results in results_by_mode.items():
        best = _best_variant(results, variant_ids)
        origins = results["origin_metrics"]
        mae = origins.loc[origins["model_id"].isin(variant_ids)].pivot(index="forecast_origin", columns="model_id", values="mae_w")
        paired = summarize_paired_differences(mae, best).sort_values("mean_delta")

        frames.append(
            pd.DataFrame(
                {
                    "Modus": mode,
                    "Modell": paired["variant"].map(MODEL_LABELS),
                    "Referenz": MODEL_LABELS[best],
                    "MAE-Differenz [W]": paired["mean_delta"],
                    "2 Standardfehler [W]": 2 * paired["delta_standard_error"],
                    "Origins besser als Referenz [%]": paired["better_share"] * 100,
                    "belastbar": paired["exceeds_noise"].map({True: "ja", False: "nein"}),
                }
            )
        )

    return pd.concat(frames, ignore_index=True)


def build_setup(config: dict, results_by_mode: dict[str, dict[str, pd.DataFrame]]) -> dict[str, str]:
    # beide Modi werten denselben Split aus, die Prognosetage sind gleich
    forecast_days = results_by_mode[config["comparison_modes"][0]]["origin_metrics"]["forecast_day"]

    setup = {
        "Split": (
            f"{config['split']}, {forecast_days.min()} bis {forecast_days.max()}, "
            f"{forecast_days.nunique()} Prognosetage (Ortszeit)"
        ),
    }

    for mode in results_by_mode:
        setup[f"Modus {mode}"] = MODE_DESCRIPTIONS[mode].format(coldstart_days=config["cycle_coldstart_days"])

    setup["Naive Referenz"] = ", ".join(f"{mode} {_reference_baseline(results)}" for mode, results in results_by_mode.items())
    setup["Prognose"] = f"{config['horizon_days']} Tag ab lokaler Mitternacht, Intervall {config['interval_width'] * 100:.0f} %"
    setup["Konfiguration"] = f"{config['config_version']}, Seed {config['seed']}"

    return setup


def build_notes(results_by_mode: dict[str, dict[str, pd.DataFrame]], variant_ids: tuple[str, ...]) -> list[str]:
    notes = ["belastbar: Betrag der MAE-Differenz größer als 2 Standardfehler der Differenzen je Origin"]

    for mode, results in results_by_mode.items():
        best = _best_variant(results, variant_ids)
        overall = results["overall_metrics"].set_index("model_id").loc[best]
        exclusions = results["target_exclusions"]
        reasons = ", ".join(
            f"{EXCLUSION_LABELS.get(row['target_exclusion_reason'], row['target_exclusion_reason'])} {row['excluded_target_count']}"
            for row in exclusions.loc[exclusions["model_id"].eq(best)].to_dict("records")
        )
        notes.append(
            f"{mode}: {overall['excluded_target_count']} von {overall['possible_target_count']} Zielstunden nicht bewertet ({reasons})"
        )

    return notes


def main() -> None:
    project_config = ProjectConfig()
    decimals = project_config.result_decimals

    run_directory = resolve_run_directory(project_config.k2_output_dir, "k2", sys.argv[1] if len(sys.argv) > 1 else None)
    config = read_raw_json(run_directory, "run_config")["experiment_config"]
    variant_ids = tuple(variant["model_id"] for variant in config["prophet_variants"])
    mode_directories = {
        mode: run_directory / RAW_SUBDIR / f"{mode}_{SPLIT_DIRECTORY_SUFFIX[config['split']]}" for mode in config["comparison_modes"]
    }
    results_by_mode = {mode: _read_mode(directory) for mode, directory in mode_directories.items()}

    tables = {
        f"ergebnis_gesamtfehler_{mode}": (
            f"Gesamtfehler {mode}", build_overall_table(results, nominal_interval_level=config["interval_width"]),
        )
        for mode, results in results_by_mode.items()
    }
    tables["ergebnis_paarvergleich"] = (
        "Abstand zum besten Prophet-Modell, gepaart je Origin", build_paired_table(results_by_mode, variant_ids),
    )

    for mode, directory in mode_directories.items():
        build_forecast_model_plot(
            directory,
            run_directory / mode,
            split=config["split"],
            comparison_mode=mode,
            baseline_model_ids=tuple(config["baseline_model_ids"]),
            variant_model_ids=variant_ids,
            reference_baseline=_reference_baseline(results_by_mode[mode]),
        )

    write_result_report(
        run_directory,
        title=f"K2 Retraining-Vergleich, Lauf {run_directory.name}",
        setup=build_setup(config, results_by_mode),
        tables=tables,
        notes=build_notes(results_by_mode, variant_ids),
        images=[f"{mode}/forecast_model_vergleich.png" for mode in mode_directories],
        decimals=decimals,
    )

    print(f"Ergebnis unter {run_directory / 'ergebnis.md'}")


if __name__ == "__main__":
    main()