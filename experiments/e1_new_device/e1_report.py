# conda activate forecasting-env
# python -m experiments.e1_new_device.e1_report [run_directory] [control_run_directory]

from pathlib import Path

import pandas as pd

from docs.plots.plot_e1_new_device import build_e1_plot
from experiments.common.harness import COMPARISON_SUMMARY_FILE
from experiments.common.report import (
    NOISE_RULE_NOTE,
    format_commit,
    format_number,
    key_figures_table,
    paired_difference_columns,
    write_result_report,
)
from experiments.common.standard_config import DECIMALS, LOCAL_TIMEZONE, PROJECT_CONFIG
from experiments.e1_new_device.e1_config import (
    CONTROL_RUN_PREFIX,
    PERIOD_LABELS,
    RUN_PREFIX,
)
from experiments.e1_new_device.e1_evaluation import E1Summary, summarize_e1
from src.common.timestamps import local_midnight_utc
from src.config.config_forecasting import SYS_LABELS
from src.pipeline.io import (
    RAW_SUBDIR,
    optional_run_directory_from_argv,
    read_raw_json,
    run_directory_from_argv,
    user_output_directory,
)


def _read_comparison(run_directory: Path) -> pd.DataFrame:
    return pd.read_csv(
        run_directory / RAW_SUBDIR / COMPARISON_SUMMARY_FILE,
        parse_dates=["decision_time"],
    )


def build_forecast_table(forecast: pd.DataFrame) -> pd.DataFrame:
    table = pd.DataFrame(
        {
            "MAE vor Cutover [W]": forecast["mae_before_w"],
            "MAE ab Cutover [W]": forecast["mae_after_w"],
        }
    )
    if "control_mae_after_w" in forecast:
        table["MAE ab Cutover, Kontrolle [W]"] = forecast["control_mae_after_w"]
    table = table.join(paired_difference_columns(forecast, "Tage"))

    return table.rename(index=SYS_LABELS).rename_axis("System").reset_index()


def build_adaption_table(adaption: pd.DataFrame, reference_config: str) -> pd.DataFrame:
    adaption = adaption.set_index("config")

    table = pd.DataFrame(
        {
            "Adaption ab Prognosetag": adaption["adaption_forecast_day"].astype(
                "Int64"
            ),
            "MAE ab Adaption [W]": adaption["mean_mae_w"],
            f"{reference_config} im selben Zeitraum [W]": adaption[
                "reference_mean_mae_w"
            ],
        }
    ).join(paired_difference_columns(adaption, "Tage"))

    return table.rename(index=SYS_LABELS).rename_axis("System").reset_index()


def build_detection_table(
    detection: pd.DataFrame, target_classification: str
) -> pd.DataFrame:
    headers = {
        "config": "System",
        "first_detection_day": f"erster {target_classification} [Tag]",
        "target_days_after": f"{target_classification} ab Cutover [Tage]",
        "false_alarm_days_before": f"{target_classification} vor Cutover, Fehlalarm [Tage]",
        "control_target_days_after": f"{target_classification} ab Cutover, Kontrolle [Tage]",
        "adaptions_before": "Adaptionen vor Cutover",
        "adaptions_after": "Adaptionen ab Cutover",
        "first_adaption_day": "erste Adaption [Tag]",
    }

    return detection.assign(config=detection["config"].map(SYS_LABELS)).rename(
        columns=headers
    )


def build_classification_table(classifications: pd.DataFrame) -> pd.DataFrame:
    labels = pd.DataFrame(
        {
            "System": classifications["config"].map(SYS_LABELS),
            "Zeitraum": classifications["period"].map(PERIOD_LABELS).astype(str),
        }
    )
    counted = classifications.drop(columns=["config", "period"]).rename(
        columns={"days": "Tage", "failed_days": "ohne Ergebnis"}
    )

    return pd.concat([labels, counted], axis=1)


def build_event_log(events: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Tag": events["day_since_event"],
            "Datum": events["analyzed_day"],
            "System": events["config"].map(SYS_LABELS),
            "Klassifikation": events["classification"],
            "Adaption": events["adaption_action"],
            "Begründung": events["explanation"].fillna(events["error"]),
        }
    )


def build_setup(
    e1_config: dict,
    summary: E1Summary,
    manifest: dict,
    control_run_directory: Path | None,
) -> dict[str, str]:
    config_values = manifest["configs"]["values"]

    setup = {
        "Gerät(e)": ", ".join(e1_config["device_meter_keys"]),
        "Cutover": f"{e1_config['cutover_date']}, Tag 0 (alle Tage und Daten in Ortszeit)",
        "Analysierte Tage": (
            f"{summary.first_analyzed_day} bis {summary.last_analyzed_day}, "
            f"{summary.days_before} vor und {summary.days_after} ab Cutover"
        ),
        "Prognosemodell": config_values[e1_config["reference_config"]][
            "forecasting_config"
        ]["selected_prophet_variant"]["model_id"],
    }

    for label, values in config_values.items():
        if values["llm_config"]:
            setup[f"LLM {label}"] = (
                f"{values['llm_config']['model']}, Prompt {values['llm_config']['prompt_version']}"
            )

    setup["Kontrolllauf"] = (
        control_run_directory.name if control_run_directory is not None else "keiner"
    )
    setup["Commit"] = format_commit(manifest["code_version"])

    return setup


def build_notes(summary: E1Summary, *, has_control: bool) -> list[str]:
    notes = [
        NOISE_RULE_NOTE,
        "Tag = Entscheidungstag seit Cutover: an Tag n meldet das System, eingeordnet ist dabei Tag n-1 (Spalte Datum). Ab Cutover zählt deshalb erst ab Tag 1",
    ]

    if summary.no_adaption:
        notes.append(
            "Ab Cutover wurde in keinem System eine Adaption ausgelöst, die Tabelle Prognose ab Adaption bleibt deshalb leer"
        )

    for row in summary.failed.to_dict("records"):
        notes.append(
            f"{SYS_LABELS[row['config']]}: {row['failed_days']} von {row['days']} Tagen ohne gültiges Ergebnis"
        )

    if not has_control:
        notes.append("Kein Kontrolllauf gefunden, Vergleich ohne Gerät fehlt")

    return notes


def build_key_figures(
    detection: pd.DataFrame,
    adaption_comparison: pd.DataFrame,
    *,
    target_classification: str,
    reference_config: str,
) -> pd.DataFrame:
    rows = [
        (
            f"{SYS_LABELS[row['config']]}: erster {target_classification} [Tag seit Cutover]",
            row["first_detection_day"],
            f"{row['false_alarm_days_before']} Fehlalarme vor Cutover",
        )
        for row in detection.to_dict("records")
    ]
    rows += [
        (
            f"{SYS_LABELS[row['config']]}: Adaption ausgelöst",
            (
                "nein"
                if pd.isna(row["first_adaption_day"])
                else f"ja, ab Tag {row['first_adaption_day']}"
            ),
            f"{row['adaptions_after']} Adaptionstage ab Cutover",
        )
        for row in detection.to_dict("records")
    ]
    rows += [
        (
            f"{SYS_LABELS[row['config']]}: MAE-Differenz zu {reference_config} ab Adaption [W]",
            row["mean_delta"],
            f"±{format_number(2 * row['delta_standard_error'], DECIMALS)} W, {row['paired_count']} Tage, "
            f"belastbar: {'ja' if row['exceeds_noise'] else 'nein'}",
        )
        for row in adaption_comparison.to_dict("records")
    ]

    return key_figures_table(rows)


def main() -> None:
    run_directory = run_directory_from_argv(PROJECT_CONFIG.e1_output_dir, RUN_PREFIX)
    # anders als der Hauptlauf optional, ohne Kontrolllauf fällt nur der Treatment/Control-Vergleich weg
    control_run_directory = optional_run_directory_from_argv(
        PROJECT_CONFIG.e1_output_dir, CONTROL_RUN_PREFIX, 2
    )

    manifest = read_raw_json(run_directory, "run_manifest")
    # als dict, ältere Läufe haben Felder, die E1Config nicht mehr kennt
    e1_config = read_raw_json(run_directory, "run_config")["e1_config"]
    reference_config = e1_config["reference_config"]
    target_classification = e1_config["target_classification"]
    cutover_time = local_midnight_utc(e1_config["cutover_date"], LOCAL_TIMEZONE)

    comparison = _read_comparison(run_directory)
    control_comparison = (
        _read_comparison(control_run_directory)
        if control_run_directory is not None
        else None
    )
    summary = summarize_e1(
        comparison,
        control_comparison,
        cutover_time=cutover_time,
        reference_config=reference_config,
        target_classification=target_classification,
    )

    tables = {
        "key_figures": (
            "Kennzahlen",
            build_key_figures(
                summary.detection,
                summary.adaption,
                target_classification=target_classification,
                reference_config=reference_config,
            ),
        ),
        "result_detection": (
            "Erkennung",
            build_detection_table(summary.detection, target_classification),
        ),
        "result_forecast_after_adaption": (
            f"Prognose ab Adaption, gepaart gegen {reference_config}",
            build_adaption_table(summary.adaption, reference_config),
        ),
        "event_log": ("Ereignisprotokoll", build_event_log(summary.events)),
    }
    appendix = {
        "result_forecast": (
            f"Prognose vor und ab Cutover, gepaart gegen {reference_config}",
            build_forecast_table(summary.forecast),
        ),
        "result_classifications": (
            "Klassifikationen je Zeitraum [Tage]",
            build_classification_table(summary.classifications),
        ),
    }

    output_directory = user_output_directory(run_directory)
    build_e1_plot(
        comparison,
        control_comparison,
        output_directory,
        cutover_time=cutover_time,
        reference_config=reference_config,
    )

    write_result_report(
        output_directory,
        title=f"E1 Neues Gerät, Lauf {run_directory.name}",
        setup=build_setup(e1_config, summary, manifest, control_run_directory),
        tables=tables,
        notes=build_notes(summary, has_control=control_run_directory is not None),
        images=["e1_timeline.png"],
        decimals=DECIMALS,
        appendix=appendix,
    )

    print(f"Result written to {output_directory / 'ergebnis.md'}")


if __name__ == "__main__":
    main()
