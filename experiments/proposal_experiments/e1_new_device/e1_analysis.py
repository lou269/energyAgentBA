# conda run -n forecasting-env python -m experiments.proposal_experiments.e1_new_device.e1_analysis
# optional: <run_directory> [control_run_directory] als Argumente, Standard ist der jeweils neueste Lauf unter experiments/output/e1

import sys
from pathlib import Path

import pandas as pd

from docs.plots.plot_e1_new_device import build_e1_plot
from experiments.proposal_experiments.e_config import E1Config
from experiments.proposal_experiments.shared_analysis import (
    compare_mae_before_after_effect,
    compare_mae_to_reference,
    count_days_by_period,
    list_decision_events,
    summarize_mae_before_after,
)
from src.common.result_report import format_number, write_result_report
from src.common.timestamps import local_midnight_utc
from src.config.config_forecasting import SYS_LABELS
from src.config.project_config import ProjectConfig
from src.pipeline.io import RAW_SUBDIR, find_run_directory, read_raw_json, resolve_run_directory

PERIOD_LABELS = {"before_event": "vor Cutover", "after_event": "ab Cutover"}
CONTROL_PERIOD_LABEL = "ab Cutover, Kontrolle"


def _resolve_control_run_directory(output_directory: Path) -> Path | None:
    # anders als der Hauptlauf optional, ohne Kontrolllauf fällt nur der Treatment/Control-Vergleich weg
    if len(sys.argv) > 2:
        return Path(sys.argv[2])

    latest_control_run = find_run_directory(output_directory, prefix="e1_control")
    return latest_control_run[1] if latest_control_run is not None else None


def _read_comparison(run_directory: Path) -> pd.DataFrame:
    return pd.read_csv(run_directory / RAW_SUBDIR / "comparison_summary.csv", parse_dates=["decision_time"])


def _by_period(counts: pd.DataFrame, configs: list[str]) -> pd.DataFrame:
    return counts.pivot(index="config", columns="period").reindex(configs)


def build_forecast_table(
    mae_before_after: pd.DataFrame,
    reference_comparison: pd.DataFrame,
    mae_effect: pd.DataFrame | None,
    reference_config: str,
) -> pd.DataFrame:
    mae = mae_before_after.pivot(index="config", columns="period", values="mean_mae_w")
    reference = reference_comparison.set_index("config")

    table = pd.DataFrame(
        {
            "MAE vor Cutover [W]": mae["before_event"],
            "MAE ab Cutover [W]": mae["after_event"],
            f"Differenz zu {reference_config} ab Cutover [W]": reference["mean_delta"],
            f"Tage besser als {reference_config} [%]": reference["better_share"] * 100,
        }
    )
    if mae_effect is not None:
        table["Geräteeffekt auf MAE [W]"] = mae_effect.set_index("config")["device_effect_mae_w"]

    return table.rename(index=SYS_LABELS).rename_axis("System").reset_index()


def build_detection_table(
    counts: pd.DataFrame,
    control_counts: pd.DataFrame | None,
    events: pd.DataFrame,
    *,
    target_classification: str,
    configs: list[str],
) -> pd.DataFrame:
    days = _by_period(counts, configs)
    hits = events.loc[events["classification"].eq(target_classification) & events["day_since_event"].ge(0)]

    table = pd.DataFrame(index=configs)
    table[f"erster {target_classification} [Tag]"] = hits.groupby("config")["day_since_event"].min()
    table[f"{target_classification} ab Cutover [Tage]"] = days.get((target_classification, "after_event"), 0)
    table[f"{target_classification} vor Cutover, Fehlalarm [Tage]"] = days.get((target_classification, "before_event"), 0)
    if control_counts is not None:
        control_days = _by_period(control_counts, configs)
        table[f"{target_classification} ab Cutover, Kontrolle [Tage]"] = control_days.get((target_classification, "after_event"), 0)
    table["Adaptionen vor Cutover"] = days[("adaption_days", "before_event")]
    table["Adaptionen ab Cutover"] = days[("adaption_days", "after_event")]

    return table.astype("Int64").rename(index=SYS_LABELS).rename_axis("System").reset_index()


def build_classification_table(counts: pd.DataFrame, control_counts: pd.DataFrame | None, configs: list[str]) -> pd.DataFrame:
    frames = [counts.assign(Zeitraum=counts["period"].map(PERIOD_LABELS))]
    if control_counts is not None:
        control_after = control_counts.loc[control_counts["period"].eq("after_event")]
        frames.append(control_after.assign(Zeitraum=CONTROL_PERIOD_LABEL))

    table = pd.concat(frames, ignore_index=True)
    table = table.loc[table["config"].isin(configs)].fillna(0)

    classifications = [
        column for column in table.columns
        if column not in ("config", "period", "Zeitraum", "days", "adaption_days", "failed_days")
    ]
    table["System"] = table["config"].map(SYS_LABELS)
    table["Zeitraum"] = pd.Categorical(table["Zeitraum"], [*PERIOD_LABELS.values(), CONTROL_PERIOD_LABEL])
    table = table.sort_values(["System", "Zeitraum"])

    counted = table[["days", *classifications, "failed_days"]].astype("Int64")
    counted = counted.rename(columns={"days": "Tage", "failed_days": "ohne Ergebnis"})
    return pd.concat([table[["System", "Zeitraum"]].astype(str), counted], axis=1).reset_index(drop=True)


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
    e1_config: E1Config,
    comparison: pd.DataFrame,
    counts: pd.DataFrame,
    manifest: dict,
    control_run_directory: Path | None,
) -> dict[str, str]:
    config_values = manifest["configs"]["values"]
    days = counts.loc[counts["config"].eq(e1_config.reference_config)].set_index("period")["days"]
    commit = manifest["code_version"]["git_commit"][:7]

    setup = {
        "Gerät": e1_config.device_meter_key,
        "Cutover": f"{e1_config.cutover_date}, Tag 0 (alle Tage und Daten in Ortszeit)",
        "Analysierte Tage": (
            f"{comparison['analyzed_day'].min()} bis {comparison['analyzed_day'].max()}, "
            f"{days['before_event']} vor und {days['after_event']} ab Cutover"
        ),
        "Prognosemodell": config_values[e1_config.reference_config]["forecasting_config"]["selected_prophet_variant"]["model_id"],
    }

    for label, values in config_values.items():
        if values["llm_config"]:
            setup[f"LLM {label}"] = f"{values['llm_config']['model']}, Prompt {values['llm_config']['prompt_version']}"

    setup["Kontrolllauf"] = control_run_directory.name if control_run_directory is not None else "keiner"
    setup["Commit"] = commit + (" (mit lokalen Änderungen)" if manifest["code_version"]["git_dirty"] else "")

    return setup


def build_notes(
    reference_comparison: pd.DataFrame,
    counts: pd.DataFrame,
    *,
    reference_config: str,
    has_control: bool,
    decimals: int,
) -> list[str]:
    notes = []

    for row in reference_comparison.to_dict("records"):
        verdict = "Unterschied größer als die Tagesschwankung" if row["exceeds_noise"] else "kein belastbarer Unterschied"
        notes.append(
            f"{SYS_LABELS[row['config']]}: Differenz zu {reference_config} ab Cutover {format_number(row['mean_delta'], decimals)} W "
            f"bei 2 Standardfehlern von {format_number(2 * row['delta_standard_error'], decimals)} W ({row['paired_count']} Tage), {verdict}"
        )

    failed = counts.groupby("config", as_index=False)[["failed_days", "days"]].sum()
    for row in failed.loc[failed["failed_days"] > 0].to_dict("records"):
        notes.append(f"{SYS_LABELS[row['config']]}: {row['failed_days']} von {row['days']} Tagen ohne gültiges Ergebnis")

    if not has_control:
        notes.append("Kein Kontrolllauf gefunden, Geräteeffekt und Vergleich ohne Gerät fehlen")

    return notes


def main() -> None:
    project_config = ProjectConfig()
    local_timezone = project_config.timezone
    decimals = project_config.result_decimals

    run_directory = resolve_run_directory(project_config.e1_output_dir, "e1", sys.argv[1] if len(sys.argv) > 1 else None)
    control_run_directory = _resolve_control_run_directory(project_config.e1_output_dir)

    manifest = read_raw_json(run_directory, "run_manifest")
    e1_config = E1Config(**read_raw_json(run_directory, "run_config")["e1_config"])
    cutover_time = local_midnight_utc(e1_config.cutover_date, local_timezone)

    comparison = _read_comparison(run_directory)
    configs = sorted(comparison.loc[comparison["classification"].notna(), "config"].unique())

    counts = count_days_by_period(comparison, cutover_time, local_timezone)
    events = list_decision_events(comparison, cutover_time, e1_config.target_classification, local_timezone)
    mae_before_after = summarize_mae_before_after(comparison, cutover_time)
    reference_comparison = compare_mae_to_reference(comparison, cutover_time, e1_config.reference_config)

    control_comparison = control_counts = mae_effect = None
    if control_run_directory is not None:
        control_comparison = _read_comparison(control_run_directory)
        control_counts = count_days_by_period(control_comparison, cutover_time, local_timezone)
        mae_effect = compare_mae_before_after_effect(mae_before_after, summarize_mae_before_after(control_comparison, cutover_time))

    tables = {
        "ergebnis_prognose": ("Prognose", build_forecast_table(mae_before_after, reference_comparison, mae_effect, e1_config.reference_config)),
        "ergebnis_erkennung": ("Erkennung und Eingriffe", build_detection_table(
            counts, control_counts, events, target_classification=e1_config.target_classification, configs=configs,
        )),
        "ergebnis_klassifikationen": ("Klassifikationen je Zeitraum [Tage]", build_classification_table(counts, control_counts, configs)),
        "ereignisprotokoll": ("Ereignisprotokoll", build_event_log(events)),
    }

    build_e1_plot(
        comparison, control_comparison, run_directory,
        cutover_time=cutover_time, reference_config=e1_config.reference_config, local_timezone=local_timezone,
    )

    write_result_report(
        run_directory,
        title=f"E1 Neues Gerät, Lauf {run_directory.name}",
        setup=build_setup(e1_config, comparison, counts, manifest, control_run_directory),
        tables=tables,
        notes=build_notes(
            reference_comparison, counts,
            reference_config=e1_config.reference_config, has_control=control_run_directory is not None, decimals=decimals,
        ),
        images=["e1_verlauf.png"],
        decimals=decimals,
    )

    print(f"Ergebnis unter {run_directory / 'ergebnis.md'}")


if __name__ == "__main__":
    main()
