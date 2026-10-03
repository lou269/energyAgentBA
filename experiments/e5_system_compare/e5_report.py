# conda activate forecasting-env
# python -m experiments.e5_system_compare.e5_report [run_directory]

from pathlib import Path

import pandas as pd

from docs.plots.plot_e5_system_compare import build_e5_plot
from experiments.common.harness import read_llm_outputs, read_run_meta
from experiments.common.report import (
    KIND_LABELS,
    NOISE_RULE_NOTE,
    YES_NO,
    answer_bullets,
    format_commit,
    format_number,
    key_figures_table,
    paired_difference_columns,
    write_explanation_rating_template,
    write_result_report,
)
from experiments.common.standard_config import DECIMALS, PROJECT_CONFIG
from experiments.e5_system_compare.e5_config import (
    RESULTS_FILE,
    RUN_PREFIX,
)
from experiments.e5_system_compare.e5_evaluation import (
    ALL_EVENTS,
    E5Summary,
    summarize_e5,
)
from src.config.config_forecasting import SYS_LABELS
from src.pipeline.io import (
    RAW_SUBDIR,
    read_raw_json,
    run_directory_from_argv,
    user_output_directory,
)

SERIES_LABELS = {"control": "Kontrolllauf", "events": "Ereignislauf"}

SIGHT_LABELS = {True: "sehend", False: "blind"}


def event_labels(events: list) -> dict[int, str]:
    return {
        number: f"{number}: {KIND_LABELS[kind]}, Tag {day}"
        for number, (day, kind) in enumerate(events, start=1)
    }


def build_criteria_table(criteria: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "System": criteria["config"].map(SYS_LABELS),
            "erwartet": criteria["expected"].replace(ALL_EVENTS, "alle Ereignisse"),
            "erkannt (TF2)": [
                f"{detected}/{events}"
                for detected, events in zip(
                    criteria["prefilter_detected"], criteria["prefilter_events"]
                )
            ],
            "erkannt [%]": criteria["detection_pct"],
            "richtig eingeordnet (TF3)": [
                f"{correct}/{detected}"
                for correct, detected in zip(criteria["correct"], criteria["detected"])
            ],
            "richtig [%]": criteria["correct_pct"],
        }
    )


def build_event_table(events: pd.DataFrame, labels: dict[int, str]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Cutover": events["cutover_date"],
            "Ereignis": events["event"].map(labels),
            "System": events["config"].map(SYS_LABELS),
            "erwartet": events["expected"],
            "bewertet an Tag": events["judged_day"],
            "Klasse": events["classification"],
            "richtig": events["correct"].map(YES_NO),
            "Skala": events["trigger_scale"],
            "Meldungen davor": events["lead_notification_days"],
            "Reset an Tag": events["reset_day"],
            "Aktion passend": events["correct_action"].map(YES_NO),
            "nach Trennung": events["after_separation"].map(YES_NO),
        }
    )


def build_forecast_table(forecast: pd.DataFrame, reference: str) -> pd.DataFrame:
    table = pd.DataFrame(
        {
            "Cutover": forecast["cutover_date"],
            "Zeitraum": [
                f"{SERIES_LABELS[series]} ab Tag {day}"
                for series, day in zip(forecast["series"], forecast["from_day"])
            ],
            "System": forecast["config"].map(SYS_LABELS),
            "MAE [W]": forecast["mean_mae_w"],
            "MAPE [%]": forecast["mean_mape_pct"],
        }
    )
    table = table.join(paired_difference_columns(forecast, "Tage"))
    table[f"MAPE-Differenz zu {reference} [%-Punkte]"] = forecast["mape_delta_pct"]

    return table


def build_notification_table(notifications: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Cutover": notifications["cutover_date"],
            "System": notifications["config"].map(SYS_LABELS),
            "Tage": notifications["sighted"].map(SIGHT_LABELS),
            "Anzahl": notifications["days"],
            "Meldungen": notifications["notification_days"],
            "unknown": notifications["unknown_days"],
        }
    )


def build_control_table(control: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Cutover": control["cutover_date"],
            "System": control["config"].map(SYS_LABELS),
            "Tage": control["days"],
            "Meldungen": control["notification_days"],
            "unknown": control["unknown_days"],
            "Resets": control["resets"],
        }
    )


def build_deviation_table(
    deviations: pd.DataFrame, labels: dict[int, str], *, rule: str, llm: str
) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Cutover": deviations["cutover_date"],
            "Reihe": deviations["series"].map(SERIES_LABELS),
            "Tag": deviations["days_since_cutover"],
            "Datum": deviations["analyzed_day"],
            "Ereignis": deviations["event"].map(labels),
            f"Klasse {rule}": deviations["classification_rule"],
            f"Klasse {llm}": deviations["classification_llm"],
            f"Aktion {rule}": deviations["adaption_action_rule"],
            f"Aktion {llm}": deviations["adaption_action_llm"],
            "LLM-Ausfall": deviations["llm_failed"].map(YES_NO),
        }
    )


def build_latency_table(latency: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Cutover": latency["cutover_date"],
            "Reihe": latency["series"].map(SERIES_LABELS),
            "Tage": latency["days"],
            "Regel je Tag [s]": latency["rule_seconds_per_day"],
            "LLM-Aufrufe": latency["llm_calls"],
            "Ausfalltage": latency["failed_days"],
            "Mehrlaufzeit gegen Regel [s]": latency["extra_seconds"],
            "je Aufruf [s]": latency["extra_seconds_per_call"],
        }
    )


def answer_lines(answers: pd.DataFrame, labels: dict[int, str]) -> list[str]:
    lines: list[str] = []
    for (cutover_date, series), group in answers.groupby(
        ["cutover_date", "series"], sort=False
    ):
        lines += [f"**{SERIES_LABELS[str(series)]}, Cutover {cutover_date}**", ""]
        for _, row in group.iterrows():
            event = (
                ""
                if pd.isna(row["event"])
                else f", Ereignis {labels[int(row['event'])]}"
            )
            lines += [
                f"{row['analyzed_day']} (Entscheidungstag {row['days_since_cutover']}{event}): "
                f"{row['config']} {row['classification']}, Regel {row['rule_classification']}, "
                f"Aktion {row['adaption_action']}",
                "",
            ] + answer_bullets(
                row["explanation"], row["user_recommendation"], row["uncertainty"]
            )
            lines.append("")

    return lines


def build_key_figures(
    summary: E5Summary, *, reference: str, rule: str, llm: str
) -> pd.DataFrame:
    rows = []
    pooled = summary.criteria.loc[summary.criteria["expected"].eq(ALL_EVENTS)]
    for row in pooled.to_dict("records"):
        system = SYS_LABELS[row["config"]]
        rows += [
            (
                f"{system}: erkannt (TF2, ≥ 90 %)",
                f"{row['prefilter_detected']}/{row['prefilter_events']}",
                f"{format_number(row['detection_pct'], DECIMALS)} %",
            ),
            (
                f"{system}: richtig eingeordnet (TF3, ≥ 80 %)",
                f"{row['correct']}/{row['detected']}",
                f"{format_number(row['correct_pct'], DECIMALS)} % der erkannten",
            ),
        ]
    for row in summary.decisions.to_dict("records"):
        rows += [
            (
                f"{row['cutover_date']}: {rule} besser als {reference}",
                YES_NO[row["rule_better"]],
                f"MAE gegen {reference} ab Dauerlast "
                f"{format_number(row['rule_mae_delta_w'], DECIMALS)} W, "
                f"{row['rule_single_day_resets']} Resets bei Einzeltag-Ereignissen, "
                f"{row['rule_control_resets']} im Kontrolllauf",
            ),
            (
                f"{row['cutover_date']}: {llm} gleichwertig zu {rule}",
                YES_NO[row["llm_equivalent"]],
                f"{row['rule_only_correct']} Ereignisse nur {rule} richtig, "
                f"{row['llm_extra_control_resets']} Resets mehr im Kontrolllauf",
            ),
            (
                f"{row['cutover_date']}: {llm} besser als {rule}",
                YES_NO[row["llm_better"]],
                f"{row['llm_only_correct']} Ereignisse nur {llm} richtig",
            ),
        ]

    return key_figures_table(rows)


def build_setup(
    e5_config: dict, llm_config: dict, labels: dict[int, str], code_version: dict
) -> dict[str, str]:

    return {
        "Cutover": ", ".join(e5_config["cutover_dates"])
        + " (Tag 0, alle Tage und Daten in Ortszeit)",
        "Fenster": f"{e5_config['margin_before_days']} Tage vor und "
        f"{e5_config['margin_after_days']} Tage ab Cutover",
        "Ereignislauf": "; ".join(labels.values()),
        "Systeme": ", ".join(
            SYS_LABELS[e5_config[key]]
            for key in ("reference_system", "rule_system", "llm_system")
        ),
        f"LLM {e5_config['llm_system']}": f"{llm_config['model']}, Prompt {llm_config['prompt_version']}",
        "Kalender": "keiner, wie CTX0",
        "Commit": format_commit(code_version),
    }


def build_notes(summary: E5Summary, single_day_scales: list[str]) -> list[str]:
    notes = [
        "Tag = Entscheidungstag seit Cutover: an Tag n wird Tag n-1 eingeordnet, ein Ereignis an Tag s also ab Tag s+1",
        "bewertet an Tag: bei einer Spitze und beim Festhänger der eingeordnete Ereignistag, falls das Gate dort offen ist, bei der Dauerlast der "
        "erste Tag mit Drift oder new_pattern. Meldungen davor zählen als Meldungen, nicht als Einordnungsfehler. "
        "Ohne Bewertungstag gilt das Ereignis als nicht erkannt (TF2) und zählt nicht in TF3. Der Festhänger zählt nicht in TF2, das Flag öffnet das Gate per Aufbau",
        "nach Trennung: vor Beginn des Ereignisses hat schon ein System anders gehandelt (Reset), die Systeme entscheiden dann nicht mehr über denselben Zustand",
        f"sehend = alle Einzeltag-Skalen ({', '.join(single_day_scales)}) haben einen Score, sonst blind",
        "Kontrolllauf über das ganze Fenster, auch die Tage vor dem Cutover. Jede Meldung dort ist ein Fehlalarm, jeder Reset unnötig",
        NOISE_RULE_NOTE,
    ]

    for row in summary.separations.loc[
        ~summary.separations["forecast_identical_before"]
    ].to_dict("records"):
        notes.append(
            f"Plausibilitätsprüfung verletzt: im {SERIES_LABELS[row['series']]} {row['cutover_date']} "
            "unterscheiden sich die Prognosen schon vor der ersten abweichenden Aktion"
        )
    if summary.interrupted:
        notes.append(
            "Mindestens ein System wurde abgebrochen, der Lauf ist nicht auswertbar"
        )

    return notes


def write_report(run_directory: Path) -> Path:
    raw_directory = run_directory / RAW_SUBDIR
    run_config = read_raw_json(run_directory, "run_config")
    e5_config = run_config["e5_config"]
    single_day_scales = list(
        run_config["numerical_analysis_config"]["single_day_scales"]
    )
    reference = e5_config["reference_system"]
    rule = e5_config["rule_system"]
    llm = e5_config["llm_system"]
    labels = event_labels(e5_config["events"])

    results = pd.read_csv(
        raw_directory / f"{RESULTS_FILE}.csv", dtype={"cutover_date": str}
    )
    llm_outputs = read_llm_outputs(raw_directory)
    summary = summarize_e5(
        results,
        read_run_meta(raw_directory),
        llm_outputs,
        events=e5_config["events"],
        reference_system=reference,
        rule_system=rule,
        llm_system=llm,
        single_day_scales=single_day_scales,
    )
    tables = {
        "key_figures": (
            "Kennzahlen",
            build_key_figures(summary, reference=reference, rule=rule, llm=llm),
        ),
        "result_criteria": (
            "Erkennung (TF2) und erste Einordnung (TF3), gepoolt über Cutover und Ereignisse",
            build_criteria_table(summary.criteria),
        ),
        "result_events": (
            "Erste Einordnung je Ereignis",
            build_event_table(summary.events, labels),
        ),
        "result_forecast": (
            f"Prognose ab Dauerlast und im Kontrolllauf, gepaart gegen {reference}",
            build_forecast_table(summary.forecast, reference),
        ),
        "result_notifications": (
            "Meldungen nach der Erkennung der Dauerlast, sehend und blind",
            build_notification_table(summary.notifications),
        ),
        "result_control": (
            "Kontrolllauf: Fehlalarme und unnötige Resets",
            build_control_table(summary.control),
        ),
        "result_deviations": (
            f"Abweichungstage {rule} gegen {llm}",
            build_deviation_table(summary.deviations, labels, rule=rule, llm=llm),
        ),
    }
    appendix = {
        "result_latency": (
            f"Laufzeit und Kosten {llm}, nur beschreibend",
            build_latency_table(summary.latency),
        ),
    }

    output_directory = user_output_directory(run_directory)
    build_e5_plot(
        results,
        output_directory,
        event_days=[day for day, _ in e5_config["events"]],
    )
    write_explanation_rating_template(llm_outputs, output_directory)

    write_result_report(
        output_directory,
        title=f"E5 Dreiervergleich {reference}/{rule}/{llm}, Lauf {run_directory.name}",
        setup=build_setup(
            e5_config, run_config["llm_config"], labels, run_config["code_version"]
        ),
        tables=tables,
        notes=build_notes(summary, single_day_scales),
        images=["e5_timeline.png"],
        decimals=DECIMALS,
        appendix=appendix,
        appendix_text=[("Antworten des LLM", answer_lines(summary.answers, labels))],
    )

    return output_directory


def main() -> None:
    output_directory = write_report(
        run_directory_from_argv(PROJECT_CONFIG.e5_output_dir, RUN_PREFIX)
    )

    print(f"Result written to {output_directory / 'ergebnis.md'}")


if __name__ == "__main__":
    main()
