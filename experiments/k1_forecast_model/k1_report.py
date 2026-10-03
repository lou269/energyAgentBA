# conda activate forecasting-env
# python -m experiments.k1_forecast_model.k1_report [retraining|seasonality] [run_directory]

import sys
from pathlib import Path

import pandas as pd

from docs.plots.plot_k1_forecast_model import build_forecast_model_plot
from docs.plots.plot_k1_seasonality import build_seasonality_plot
from src.common.target_series import read_preprocessed_daily_target
from src.config.config_forecasting import MODEL_LABELS as FORECAST_MODEL_LABELS
from experiments.common.report import (
    NOISE_RULE_NOTE,
    format_commit,
    format_number,
    key_figures_table,
    paired_difference_columns,
    write_result_report,
)
from experiments.common.standard_config import DECIMALS, PROJECT_CONFIG
from experiments.k1_forecast_model.k1_config import (
    REFERENCE_FILE,
    RUN_PREFIX,
    SEASONALITY_METRICS_FILE,
    SEASONALITY_RUN_PREFIX,
    SPLIT_DIRECTORY_SUFFIX,
)
from experiments.k1_forecast_model.k1_evaluation import (
    ModeSummary,
    compare_to_best_variant,
    summarize_modes,
    summarize_overall,
    summarize_seasonal_forecast,
)
from src.pipeline.io import (
    RAW_SUBDIR,
    read_raw_json,
    run_directory_from_argv,
    user_output_directory,
)

MODE_DESCRIPTIONS: dict[str, str] = {
    "rolling": "{coldstart_days} Tage Historie vor Split-Start, wie der Online-Zyklus",
    "macro": "gesamte Historie vor Split-Start",
}

EXCLUSION_LABELS: dict[str, str] = {
    "missing_target": "Messwert fehlt",
    "target_imputed": "imputiert",
}

MODEL_LABELS: dict[str, str] = FORECAST_MODEL_LABELS | {
    "S1": "S1 expanding + Jahressaison"
}

RESULT_FILES = (
    "forecasts",
    "overall_metrics",
    "origin_metrics",
    "mae_skill",
    "interval_metrics",
    "target_exclusions",
    REFERENCE_FILE,
)


def build_overall_table(
    overall: pd.DataFrame, reference_model: str, nominal_interval_level: float
) -> pd.DataFrame:
    table = pd.DataFrame(
        {
            "MAE [W]": overall["mae_w"],
            "RMSE [W]": overall["rmse_w"],
            "MAPE [%]": overall["mape_pct"],
            "Tagesfehler MAE [W]": overall["daily_mae_w"],
            "Tagesfehler MAPE [%]": overall["daily_mape_pct"],
            f"Skill ggü. {reference_model} [%]": overall["skill_pct"],
            f"Intervall-Abdeckung [%], Soll {nominal_interval_level * 100:.0f}": overall[
                "coverage_pct"
            ],
            "Refit-Zeit gesamt [s]": overall["refit_seconds"],
        }
    )

    return table.rename(index=MODEL_LABELS).rename_axis("Modell").reset_index()


def build_paired_table(paired: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Modus": paired["mode"],
            "Modell": paired["variant"].map(MODEL_LABELS),
            "Referenz": paired["reference"].map(MODEL_LABELS),
        }
    ).join(paired_difference_columns(paired, "Origins"))


def build_setup(
    config: dict, modes: list[ModeSummary], code_version: dict
) -> dict[str, str]:
    # beide Modi werten denselben Split aus, die Prognosetage sind gleich
    days = modes[0]

    setup = {
        "Split": (
            f"{config['split']}, {days.first_forecast_day} bis {days.last_forecast_day}, "
            f"{days.forecast_day_count} Prognosetage (Ortszeit)"
        ),
    }
    for mode in modes:
        setup[f"Modus {mode.mode}"] = MODE_DESCRIPTIONS[mode.mode].format(
            coldstart_days=config["cycle_coldstart_days"]
        )

    setup["Naive Referenz"] = ", ".join(
        f"{mode.mode} {mode.reference_model}" for mode in modes
    )
    setup["Prognose"] = (
        f"{config['horizon_days']} Tag ab lokaler Mitternacht, Intervall {config['interval_width'] * 100:.0f} %"
    )
    setup["Konfiguration"] = f"{config['config_version']}, Seed {config['seed']}"
    setup["Commit"] = format_commit(code_version)

    return setup


def build_notes(modes: list[ModeSummary]) -> list[str]:
    notes = [
        NOISE_RULE_NOTE,
        "Tagesfehler: Fehler des Tagesmittels (Mittel der 24 Prognosewerte gegen das Ist-Tagesmittel), nicht der Mittelwert der Stundenfehler",
    ]

    for mode in modes:
        reasons = ", ".join(
            f"{EXCLUSION_LABELS.get(reason, reason)} {count}"
            for reason, count in mode.exclusion_reasons
        )
        notes.append(
            f"{mode.mode}: Tagesfehler aus {mode.daily_count} von {mode.forecast_day_count} Tagen (nur Tage mit lauter bewerteten Stunden)"
        )
        notes.append(
            f"{mode.mode}: {mode.excluded_target_count} von {mode.possible_target_count} Zielstunden nicht bewertet ({reasons})"
        )

    return notes


def build_key_figures(modes: list[ModeSummary]) -> pd.DataFrame:
    rows: list[tuple[str, object, str]] = []

    for mode in modes:
        name, reference = mode.mode, mode.reference_model
        rows += [
            (
                f"{name}: MAE bestes Modell {MODEL_LABELS[mode.best_model]} [W]",
                mode.best_mae_w,
                f"{reference} {format_number(mode.reference_mae_w, DECIMALS)} W",
            ),
            (
                f"{name}: Skill der Prophet-Varianten ggü. {reference} [%]",
                mode.skill_max_pct,
                f"Spanne {format_number(mode.skill_min_pct, DECIMALS)} bis {format_number(mode.skill_max_pct, DECIMALS)} %",
            ),
            (
                f"{name}: Varianten belastbar schlechter als das beste Modell",
                mode.worse_than_best,
                f"von {mode.compared_variants}",
            ),
        ]

    return key_figures_table(rows)


def report_retraining(run_directory: Path) -> Path:
    run_config = read_raw_json(run_directory, "run_config")
    config = run_config["k1_config"]
    variant_ids = tuple(variant["model_id"] for variant in config["prophet_variants"])
    mode_directories = {
        mode: run_directory
        / RAW_SUBDIR
        / f"{mode}_{SPLIT_DIRECTORY_SUFFIX[config['split']]}"
        for mode in config["comparison_modes"]
    }
    results_by_mode = {
        mode: {name: pd.read_csv(directory / f"{name}.csv") for name in RESULT_FILES}
        for mode, directory in mode_directories.items()
    }

    paired = compare_to_best_variant(results_by_mode, variant_ids)
    actual_daily = read_preprocessed_daily_target(PROJECT_CONFIG)
    modes = summarize_modes(results_by_mode, paired, variant_ids, actual_daily)

    output_directory = user_output_directory(run_directory)
    tables = {"key_figures": ("Kennzahlen", build_key_figures(modes))}

    for mode in modes:
        results = results_by_mode[mode.mode]
        overall = summarize_overall(results, actual_daily)

        tables[f"result_overall_{mode.mode}"] = (
            f"Gesamtfehler {mode.mode}",
            build_overall_table(
                overall, mode.reference_model, config["interval_width"]
            ),
        )
        build_forecast_model_plot(
            overall,
            results["origin_metrics"],
            output_directory / mode.mode,
            split=config["split"],
            comparison_mode=mode.mode,
            baseline_model_ids=tuple(config["baseline_model_ids"]),
            variant_model_ids=variant_ids,
            reference_baseline=mode.reference_model,
        )

    tables["result_paired"] = (
        "Abstand zum besten Prophet-Modell, gepaart je Origin",
        build_paired_table(paired),
    )

    write_result_report(
        output_directory,
        title=f"K1 Retraining-Vergleich, Lauf {run_directory.name}",
        setup=build_setup(config, modes, run_config["code_version"]),
        tables=tables,
        notes=build_notes(modes),
        images=[f"{mode}/forecast_model_comparison.png" for mode in mode_directories],
        decimals=DECIMALS,
    )

    return output_directory


def report_seasonality(run_directory: Path) -> Path:
    run_config = read_raw_json(run_directory, "run_config")
    config = run_config["k1_config"]
    reference_model_id = config["primary_naive_reference"]
    model_ids = [variant["model_id"] for variant in config["seasonality_variants"]]

    origin_metrics = pd.read_csv(
        run_directory / RAW_SUBDIR / f"{SEASONALITY_METRICS_FILE}.csv",
        dtype={"forecast_day": str},
    )
    summary = summarize_seasonal_forecast(
        origin_metrics,
        tuple(
            (variant, reference)
            for variant, reference in config["seasonality_comparisons"]
        ),
    )

    comparisons = [
        f"{variant} − {reference}"
        for variant, reference in zip(
            summary.paired["variant"], summary.paired["reference"]
        )
    ]
    by_month = summary.by_month[["month"] + model_ids + [reference_model_id]]

    tables = {
        "key_figures": (
            "Kennzahlen",
            key_figures_table(
                [
                    (
                        f"{comparison}: MAE-Differenz über das Jahr [W]",
                        delta,
                        "negativ = Variante besser, belastbar "
                        + ("ja" if exceeds_noise else "nein"),
                    )
                    for comparison, delta, exceeds_noise in zip(
                        comparisons,
                        summary.paired["mean_delta"],
                        summary.paired["exceeds_noise"],
                    )
                ]
            ),
        ),
        "result_by_month": (
            "MAE je Monat [W]",
            by_month.rename(columns={"month": "Monat"} | MODEL_LABELS),
        ),
        "result_paired": (
            "Gepaarte Differenzen über das Jahr, je Prognosetag",
            pd.concat(
                [
                    pd.DataFrame({"Vergleich": comparisons}),
                    paired_difference_columns(summary.paired, "Tage"),
                ],
                axis=1,
            ),
        ),
    }

    output_directory = user_output_directory(run_directory)
    build_seasonality_plot(
        summary.by_month,
        output_directory,
        model_ids=model_ids,
        reference_model_id=reference_model_id,
        model_labels=MODEL_LABELS,
    )

    write_result_report(
        output_directory,
        title=f"K1 Prognose mit und ohne Jahressaisonalität, Lauf {run_directory.name}",
        setup={
            "Auswertung": f"{config['seasonality_days']} Tage ab {config['seasonality_start_date']} "
            f"({config['seasonality_split']}), je Tag eine 24-h-Prognose, Historie ab Datenbeginn",
            "Varianten": ", ".join(MODEL_LABELS[model_id] for model_id in model_ids),
            "Naive Referenz": MODEL_LABELS[reference_model_id],
            "Commit": format_commit(run_config["code_version"]),
        },
        tables=tables,
        notes=[
            "S1 − C2 ist der Effekt der Jahressaisonalität allein, C2 − C3_30 der der längeren Historie",
            "Monat 2014-04 und 2015-04 sind je ein halber Monat",
            NOISE_RULE_NOTE,
        ],
        images=["k1_mae_by_month.png"],
        decimals=DECIMALS,
    )

    return output_directory


def main() -> None:
    part = sys.argv[1] if len(sys.argv) > 1 else "retraining"

    if part == "seasonality":
        output_directory = report_seasonality(
            run_directory_from_argv(
                PROJECT_CONFIG.k1_output_dir, SEASONALITY_RUN_PREFIX, 2
            )
        )
    else:
        output_directory = report_retraining(
            run_directory_from_argv(PROJECT_CONFIG.k1_output_dir, RUN_PREFIX, 2)
        )

    print(f"Result written to {output_directory / 'ergebnis.md'}")


if __name__ == "__main__":
    main()
