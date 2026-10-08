# conda activate forecasting-env
# python -m experiments.k4_forecast_model.k4_report [retraining|seasonality] [run_directory]

import sys
from pathlib import Path

import pandas as pd

from docs.plots.plot_k4_forecast_model import build_forecast_model_plot
from docs.plots.plot_k4_seasonality import build_seasonality_plot
from src.common.target_series import read_preprocessed_daily_target
from src.pipeline.io import read_split_bounds
from src.config.config_forecasting import MODEL_LABELS as FORECAST_MODEL_LABELS
from experiments.common.report import (
    NOISE_RULE_NOTE,
    format_commit,
    format_number,
    key_figures_table,
    paired_difference_columns,
    write_result_report,
)
from experiments.common.standard_config import (
    LOCAL_TIMEZONE,
    PROJECT_CONFIG,
    STANDARD_CONFIG,
)
from experiments.k4_forecast_model.k4_config import (
    REFERENCE_FILE,
    RUN_PREFIX,
    SEASONALITY_FORECASTS_FILE,
    SEASONALITY_RUN_PREFIX,
    SPLIT_DIRECTORY_SUFFIX,
)
from experiments.k4_forecast_model.k4_evaluation import (
    ModeSummary,
    summarize_retraining,
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
    "Y1": "Y1 expanding + Jahressaison"
}

RESULT_FILES = (
    "forecasts",
    "overall_metrics",
    "origin_metrics",
    "interval_metrics",
    "target_exclusions",
    REFERENCE_FILE,
)


def build_overall_table(
    overall: pd.DataFrame, reference_model: str, nominal_interval_level: float
) -> pd.DataFrame:
    table = pd.DataFrame(
        {
            "Tagesfehler MAE [W]": overall["daily_mae_w"],
            "Tagesfehler MAPE [%]": overall["daily_mape_pct"],
            f"Skill Tagesfehler ggü. {reference_model} [%]": overall["skill_pct"],
            "Stunden-MAE [W]": overall["mae_w"],
            "Stunden-RMSE [W]": overall["rmse_w"],
            "Stunden-MAPE [%]": overall["mape_pct"],
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
    ).join(paired_difference_columns(paired, "Tage"))


def build_setup(
    config: dict, split: str, modes: list[ModeSummary], code_version: dict
) -> dict[str, str]:
    # beide Modi werten denselben Split aus, die Prognosetage sind gleich
    days = modes[0]

    setup = {
        "Split": (
            f"{split}, {days.first_forecast_day} bis {days.last_forecast_day}, "
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
        "Tagesfehler: Fehler des Tagesmittels (Mittel der 24 Prognosewerte gegen das Ist-Tagesmittel), nicht der Mittelwert der Stundenfehler. "
        "Beste Variante, Skill und gepaarter Abstand beruhen auf ihm, die Stundenfehler stehen nur zum Vergleich",
    ]

    for mode in modes:
        reasons = ", ".join(
            f"{EXCLUSION_LABELS.get(reason, reason)} {count}"
            for reason, count in mode.exclusion_reasons
        )
        notes.append(
            f"{mode.mode}: Tagesfehler aus {mode.daily_count} von {mode.forecast_day_count} Tagen (nur Tage mit Ist-Tagesmittel)"
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
                f"{name}: Tagesfehler bestes Modell {MODEL_LABELS[mode.best_model]} [W]",
                mode.best_daily_mae_w,
                f"{reference} {format_number(mode.reference_daily_mae_w, STANDARD_CONFIG.decimals)} W",
            ),
            (
                f"{name}: Skill der Prophet-Varianten im Tagesfehler ggü. {reference} [%]",
                mode.skill_max_pct,
                f"Spanne {format_number(mode.skill_min_pct, STANDARD_CONFIG.decimals)} bis {format_number(mode.skill_max_pct, STANDARD_CONFIG.decimals)} %",
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
    config = run_config["k4_config"]
    split = run_config["standard_config"]["split"]
    variant_ids = tuple(variant["model_id"] for variant in config["prophet_variants"])
    mode_directories = {
        mode: run_directory / RAW_SUBDIR / f"{mode}_{SPLIT_DIRECTORY_SUFFIX[split]}"
        for mode in config["comparison_modes"]
    }
    results_by_mode = {
        mode: {name: pd.read_csv(directory / f"{name}.csv") for name in RESULT_FILES}
        for mode, directory in mode_directories.items()
    }

    summary = summarize_retraining(
        results_by_mode,
        variant_ids,
        read_preprocessed_daily_target(PROJECT_CONFIG, split),
    )
    modes = summary.modes

    output_directory = user_output_directory(run_directory)
    tables = {"key_figures": ("Kennzahlen", build_key_figures(modes))}

    for mode in modes:
        overall = summary.overall[mode.mode]

        tables[f"result_overall_{mode.mode}"] = (
            f"Gesamtfehler {mode.mode}",
            build_overall_table(
                overall, mode.reference_model, config["interval_width"]
            ),
        )
        build_forecast_model_plot(
            overall,
            summary.days[mode.mode],
            output_directory / mode.mode,
            split=split,
            comparison_mode=mode.mode,
            baseline_model_ids=tuple(config["baseline_model_ids"]),
            variant_model_ids=variant_ids,
            reference_baseline=mode.reference_model,
        )

    tables["result_paired"] = (
        "Abstand zum besten Prophet-Modell im Tagesfehler, gepaart je Prognosetag",
        build_paired_table(summary.paired),
    )

    write_result_report(
        output_directory,
        title=f"K4 Retraining-Vergleich, Lauf {run_directory.name}",
        setup=build_setup(config, split, modes, run_config["code_version"]),
        tables=tables,
        notes=build_notes(modes),
        images=[f"{mode}/forecast_model_comparison.png" for mode in mode_directories],
        decimals=STANDARD_CONFIG.decimals,
    )

    return output_directory


def report_seasonality(run_directory: Path) -> Path:
    run_config = read_raw_json(run_directory, "run_config")
    config = run_config["k4_config"]
    split = run_config["standard_config"]["split"]
    reference_model_id = config["primary_naive_reference"]
    model_ids = [variant["model_id"] for variant in config["seasonality_variants"]]
    split_start, _split_end = read_split_bounds(PROJECT_CONFIG, split)
    seasonality_start = split_start.tz_convert(LOCAL_TIMEZONE).date()

    summary = summarize_seasonal_forecast(
        pd.read_csv(run_directory / RAW_SUBDIR / f"{SEASONALITY_FORECASTS_FILE}.csv"),
        read_preprocessed_daily_target(PROJECT_CONFIG, split),
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
                        f"{comparison}: Differenz im Tagesfehler über das Jahr [W]",
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
            "Tagesfehler je Monat [W]",
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
        title=f"K4 Prognose mit und ohne Jahressaisonalität, Lauf {run_directory.name}",
        setup={
            "Auswertung": f"{config['seasonality_days']} Tage ab {seasonality_start} "
            f"({split}), je Tag eine 24-h-Prognose, Historie ab Datenbeginn",
            "Varianten": ", ".join(MODEL_LABELS[model_id] for model_id in model_ids),
            "Naive Referenz": MODEL_LABELS[reference_model_id],
            "Commit": format_commit(run_config["code_version"]),
        },
        tables=tables,
        notes=[
            "Y1 − C2 ist der Effekt der Jahressaisonalität allein, C2 − C3_30 der der längeren Historie",
            "Monat 2014-04 und 2015-04 sind je ein halber Monat",
            NOISE_RULE_NOTE,
        ],
        images=["k4_mae_by_month.png"],
        decimals=STANDARD_CONFIG.decimals,
    )

    return output_directory


def main() -> None:
    part = sys.argv[1] if len(sys.argv) > 1 else "retraining"

    if part == "seasonality":
        output_directory = report_seasonality(
            run_directory_from_argv(
                PROJECT_CONFIG.k4_output_dir, SEASONALITY_RUN_PREFIX, 2
            )
        )
    else:
        output_directory = report_retraining(
            run_directory_from_argv(PROJECT_CONFIG.k4_output_dir, RUN_PREFIX, 2)
        )

    print(f"Result written to {output_directory / 'ergebnis.md'}")


if __name__ == "__main__":
    main()
