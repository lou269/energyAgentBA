# conda run -n forecasting-env python -m experiments.proposal_experiments.e1_new_device.e1_analysis
# optional: <lauf> [kontrolllauf] als Argumente, z.B. "003 003", Standard ist der jeweils neueste Lauf unter experiments/output/e1

import sys
from pathlib import Path

import pandas as pd

from docs.plots.plot_e1_new_device import build_e1_plot
from experiments.shared_analysis import (
    NOISE_RULE_NOTE,
    compare_mae_to_reference,
    compare_mae_to_reference_after_adaption,
    count_days_by_period,
    list_decision_events,
    paired_difference_columns,
    summarize_mae_before_after,
)
from src.common.result_report import (
    format_commit,
    format_number,
    key_figures_table,
    write_result_report,
)
from src.common.timestamps import local_midnight_utc
from src.config.config_forecasting import SYS_LABELS
from src.config.project_config import ProjectConfig
from src.pipeline.io import (
    RAW_SUBDIR,
    find_run_directory,
    read_raw_json,
    resolve_run_directory,
    user_output_directory,
)

PERIOD_LABELS = {"before_event": "vor Cutover", "after_event": "ab Cutover"}
CONTROL_PERIOD_LABEL = "ab Cutover, Kontrolle"


def _resolve_control_run_directory(output_directory: Path) -> Path | None:
    # anders als der Hauptlauf optional, ohne Kontrolllauf fällt nur der Treatment/Control-Vergleich weg
    if len(sys.argv) > 2:
        return resolve_run_directory(output_directory, "e1_control", sys.argv[2])

    latest_control_run = find_run_directory(output_directory, prefix="e1_control")
    return latest_control_run[1] if latest_control_run is not None else None


def _read_comparison(run_directory: Path) -> pd.DataFrame:
    return pd.read_csv(
        run_directory / RAW_SUBDIR / "comparison_summary.csv",
        parse_dates=["decision_time"],
    )


def _by_period(counts: pd.DataFrame, configs: list[str]) -> pd.DataFrame:
    return counts.pivot(index="config", columns="period").reindex(configs)


def build_forecast_table(
    mae_before_after: pd.DataFrame,
    control_mae_before_after: pd.DataFrame | None,
    reference_comparison: pd.DataFrame,
) -> pd.DataFrame:
    mae = mae_before_after.pivot(index="config", columns="period", values="mean_mae_w")
    reference = reference_comparison.set_index("config")

    table = pd.DataFrame(
        {
            "MAE vor Cutover [W]": mae["before_event"],
            "MAE ab Cutover [W]": mae["after_event"],
        }
    ).join(paired_difference_columns(reference, "Tage"))
    # ab Cutover sind Haupt- und Kontrollreihe identisch, nur das Modell hat die Geräte vorher nie gesehen
    if control_mae_before_after is not None:
        control_mae = control_mae_before_after.pivot(
            index="config", columns="period", values="mean_mae_w"
        )
        table.insert(2, "MAE ab Cutover, Kontrolle [W]", control_mae["after_event"])

    return table.rename(index=SYS_LABELS).rename_axis("System").reset_index()


def build_adaption_table(
    adaption_comparison: pd.DataFrame, reference_config: str
) -> pd.DataFrame:
    # ab Cutover vermischt Tage vor und nach dem Eingriff, hier nur die Tage mit adaptiertem Modell
    adaption = adaption_comparison.set_index("config")

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


def summarize_detection(
    counts: pd.DataFrame,
    control_counts: pd.DataFrame | None,
    events: pd.DataFrame,
    *,
    target_classification: str,
    configs: list[str],
) -> pd.DataFrame:
    days = _by_period(counts, configs)
    hits = events.loc[
        events["classification"].eq(target_classification)
        & events["day_since_event"].ge(0)
    ]

    detection = pd.DataFrame(index=configs)
    detection["first_detection_day"] = hits.groupby("config")["day_since_event"].min()
    detection["target_days_after"] = days.get((target_classification, "after_event"), 0)
    detection["false_alarm_days_before"] = days.get(
        (target_classification, "before_event"), 0
    )
    if control_counts is not None:
        control_days = _by_period(control_counts, configs)
        detection["control_target_days_after"] = control_days.get(
            (target_classification, "after_event"), 0
        )
    detection["adaptions_before"] = days[("adaption_days", "before_event")]
    detection["adaptions_after"] = days[("adaption_days", "after_event")]

    return detection.astype("Int64").rename_axis("config").reset_index()


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
    }

    return detection.assign(config=detection["config"].map(SYS_LABELS)).rename(
        columns=headers
    )


def build_classification_table(
    counts: pd.DataFrame, control_counts: pd.DataFrame | None, configs: list[str]
) -> pd.DataFrame:
    frames = [counts.assign(Zeitraum=counts["period"].map(PERIOD_LABELS))]
    if control_counts is not None:
        control_after = control_counts.loc[control_counts["period"].eq("after_event")]
        frames.append(control_after.assign(Zeitraum=CONTROL_PERIOD_LABEL))

    table = pd.concat(frames, ignore_index=True)
    table = table.loc[table["config"].isin(configs)].fillna(0)

    classifications = [
        column
        for column in table.columns
        if column
        not in ("config", "period", "Zeitraum", "days", "adaption_days", "failed_days")
    ]
    table["System"] = table["config"].map(SYS_LABELS)
    table["Zeitraum"] = pd.Categorical(
        table["Zeitraum"], [*PERIOD_LABELS.values(), CONTROL_PERIOD_LABEL]
    )
    table = table.sort_values(["System", "Zeitraum"])

    counted = table[["days", *classifications, "failed_days"]].astype("Int64")
    counted = counted.rename(columns={"days": "Tage", "failed_days": "ohne Ergebnis"})
    return pd.concat(
        [table[["System", "Zeitraum"]].astype(str), counted], axis=1
    ).reset_index(drop=True)


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
    comparison: pd.DataFrame,
    counts: pd.DataFrame,
    manifest: dict,
    control_run_directory: Path | None,
) -> dict[str, str]:
    config_values = manifest["configs"]["values"]
    days = counts.loc[counts["config"].eq(e1_config["reference_config"])].set_index(
        "period"
    )["days"]

    setup = {
        "Gerät(e)": ", ".join(e1_config["device_meter_keys"]),
        "Cutover": f"{e1_config['cutover_date']}, Tag 0 (alle Tage und Daten in Ortszeit)",
        "Analysierte Tage": (
            f"{comparison['analyzed_day'].min()} bis {comparison['analyzed_day'].max()}, "
            f"{days['before_event']} vor und {days['after_event']} ab Cutover"
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


def build_notes(counts: pd.DataFrame, *, has_control: bool) -> list[str]:
    notes = [NOISE_RULE_NOTE]

    failed = counts.groupby("config", as_index=False)[["failed_days", "days"]].sum()
    for row in failed.loc[failed["failed_days"] > 0].to_dict("records"):
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
    decimals: int,
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
            f"{SYS_LABELS[row['config']]}: MAE-Differenz zu {reference_config} ab Adaption [W]",
            row["mean_delta"],
            f"±{format_number(2 * row['delta_standard_error'], decimals)} W, {row['paired_count']} Tage, "
            f"belastbar: {'ja' if row['exceeds_noise'] else 'nein'}",
        )
        for row in adaption_comparison.to_dict("records")
    ]

    return key_figures_table(rows)


def main() -> None:
    project_config = ProjectConfig()
    local_timezone = project_config.timezone
    decimals = project_config.result_decimals

    run_directory = resolve_run_directory(
        project_config.e1_output_dir, "e1", sys.argv[1] if len(sys.argv) > 1 else None
    )
    control_run_directory = _resolve_control_run_directory(project_config.e1_output_dir)

    manifest = read_raw_json(run_directory, "run_manifest")
    # als dict, ältere Läufe haben Felder, die E1Config nicht mehr kennt
    e1_config = read_raw_json(run_directory, "run_config")["e1_config"]
    reference_config = e1_config["reference_config"]
    target_classification = e1_config["target_classification"]
    cutover_time = local_midnight_utc(e1_config["cutover_date"], local_timezone)

    comparison = _read_comparison(run_directory)
    configs = sorted(
        comparison.loc[comparison["classification"].notna(), "config"].unique()
    )

    counts = count_days_by_period(comparison, cutover_time, local_timezone)
    events = list_decision_events(
        comparison, cutover_time, target_classification, local_timezone
    )
    mae_before_after = summarize_mae_before_after(comparison, cutover_time)
    reference_comparison = compare_mae_to_reference(
        comparison, cutover_time, reference_config
    )
    adaption_comparison = compare_mae_to_reference_after_adaption(
        comparison, cutover_time, reference_config, local_timezone
    )

    control_comparison = control_counts = control_mae_before_after = None
    if control_run_directory is not None:
        control_comparison = _read_comparison(control_run_directory)
        control_counts = count_days_by_period(
            control_comparison, cutover_time, local_timezone
        )
        control_mae_before_after = summarize_mae_before_after(
            control_comparison, cutover_time
        )

    detection = summarize_detection(
        counts,
        control_counts,
        events,
        target_classification=target_classification,
        configs=configs,
    )

    tables = {
        "key_figures": (
            "Kennzahlen",
            build_key_figures(
                detection,
                adaption_comparison,
                target_classification=target_classification,
                reference_config=reference_config,
                decimals=decimals,
            ),
        ),
        "result_detection": (
            "Erkennung",
            build_detection_table(detection, target_classification),
        ),
        "result_forecast_after_adaption": (
            f"Prognose ab Adaption, gepaart gegen {reference_config}",
            build_adaption_table(adaption_comparison, reference_config),
        ),
        "event_log": ("Ereignisprotokoll", build_event_log(events)),
    }
    appendix = {
        "result_forecast": (
            f"Prognose vor und ab Cutover, gepaart gegen {reference_config}",
            build_forecast_table(
                mae_before_after,
                control_mae_before_after,
                reference_comparison,
            ),
        ),
        "result_classifications": (
            "Klassifikationen je Zeitraum [Tage]",
            build_classification_table(counts, control_counts, configs),
        ),
    }

    output_directory = user_output_directory(run_directory)

    build_e1_plot(
        comparison,
        control_comparison,
        output_directory,
        cutover_time=cutover_time,
        reference_config=reference_config,
        local_timezone=local_timezone,
    )

    write_result_report(
        output_directory,
        title=f"E1 Neues Gerät, Lauf {run_directory.name}",
        setup=build_setup(
            e1_config, comparison, counts, manifest, control_run_directory
        ),
        tables=tables,
        notes=build_notes(counts, has_control=control_run_directory is not None),
        images=["e1_timeline.png"],
        decimals=decimals,
        appendix=appendix,
    )

    print(f"Result written to {output_directory / 'ergebnis.md'}")


if __name__ == "__main__":
    main()
