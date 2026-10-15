# conda activate forecasting-env
# python -m experiments.e3_system_compare.e3_report [run_directory]

from pathlib import Path

import pandas as pd

from docs.plots.plot_e3_system_compare import build_e3_week_plot
from experiments.common.harness import read_llm_outputs, read_run_meta
from experiments.common.report import (
    KIND_LABELS,
    NOISE_RULE_NOTE,
    YES_NO,
    criteria_table,
    build_setup,
    format_llm,
    format_difference,
    format_number,
    stichtag_labels,
    write_result_report,
)
from experiments.common.standard_config import (
    NOTIFICATION_CLASSIFICATIONS,
    PROJECT_CONFIG,
    STANDARD_CONFIG,
)
from experiments.e3_system_compare.e3_config import (
    E3Config,
    RESULTS_FILE,
    RUN_PREFIX,
)
from experiments.e3_system_compare.e3_evaluation import E3Summary, summarize_e3
from src.pipeline.io import (
    RAW_SUBDIR,
    read_raw_json,
    run_directory_from_argv,
    user_output_directory,
)


def series_labels(event_series: dict[str, list]) -> dict[str, str]:
    return {"control": KIND_LABELS["control"]} | {
        series: KIND_LABELS[events[0][1]] for series, events in event_series.items()
    }


OVERVIEW_ROWS = (
    ("Fälle mit Zurücksetzen", "triggered_cases", "cases"),
    ("Tagesfehler [W]", "day_error_w", "number"),
    ("Differenz [W]", "day_error_delta_w", "number"),
    ("2 Standardfehler [W]", "day_error_delta_two_se_w", "number"),
    ("gepaarte Tage", "paired_days", "count"),
    ("Differenz belastbar", "day_error_reliable", "yes_no"),
    ("Meldungstage", "notification_days", "count"),
    ("Meldungen je 30 Tage", "notifications_per_period", "number"),
    ("Differenz Meldungen", "notification_delta", "number"),
    ("Zurücksetzen im Kontrolllauf", "control_resets", "count"),
)


def build_criteria(summary: E3Summary, *, reference: str, llm: str) -> pd.DataFrame:
    criteria = {row["criterion"]: row for row in summary.criteria.to_dict("records")}
    day_error = criteria["day_error"]
    notifications = criteria["notifications"]
    decimals = STANDARD_CONFIG.decimals

    return criteria_table(
        [
            (
                f"Tagesfehler {llm} minus {reference}",
                "< 0, belastbar",
                format_difference(
                    day_error["value"],
                    day_error["two_se"],
                    bool(day_error["reliable"]),
                    decimals,
                ),
                day_error["fulfilled"],
            ),
            (
                f"Meldungen {llm} minus {reference}",
                "< 0 je 30 Tage",
                format_number(float(notifications["value"]), decimals),
                notifications["fulfilled"],
            ),
        ]
    )


def build_overview_table(
    overall: pd.DataFrame, *, reference: str, llm: str
) -> pd.DataFrame:
    systems = {row["config"]: row for row in overall.to_dict("records")}

    def cell(config: str, column: str, kind: str) -> object:
        value = systems[config][column]
        if pd.isna(value):
            return "-"
        if kind == "yes_no":
            return YES_NO[bool(value)]
        if kind == "count":
            return int(value)
        if kind == "cases":
            return f"{int(value)} von {int(systems[config]['cases'])}"
        return float(value)

    rows: dict[str, list[object]] = {
        "Kennzahl": [label for label, _, _ in OVERVIEW_ROWS]
    }
    for config in systems:
        rows[config] = [cell(config, column, kind) for _, column, kind in OVERVIEW_ROWS]

    return pd.DataFrame(rows, dtype=object)


def build_week_table(
    weeks: pd.DataFrame,
    notifications: pd.DataFrame,
    *,
    reference: str,
    llm: str,
    labels: dict[str, str] | None = None,
) -> pd.DataFrame:
    keys = ["week"] if labels is None else ["series", "week"]
    days = notifications.pivot(
        index=keys, columns="config", values="notification_days"
    ).reindex(pd.MultiIndex.from_frame(weeks[keys]) if len(keys) > 1 else weeks["week"])
    table = pd.DataFrame(
        {
            "Woche": weeks["week"],
            "Fälle": weeks["cases"],
            f"Tagesfehler {llm} [W]": weeks["llm_day_error_w"],
            f"Tagesfehler {reference} [W]": weeks["reference_day_error_w"],
            "Differenz [W]": weeks["day_error_delta_w"],
            f"Meldungstage {reference}": days[reference].to_numpy(),
            f"Meldungstage {llm}": days[llm].to_numpy(),
        }
    )
    if labels is not None:
        table.insert(0, "Szenario", weeks["series"].map(labels))

    return table.astype(
        {f"Meldungstage {reference}": "Int64", f"Meldungstage {llm}": "Int64"}
    )


def build_case_table(
    cases: pd.DataFrame,
    *,
    reference: str,
    llm: str,
    labels: dict[str, str],
    stichtage: dict[str, str],
) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Stichtag": cases["cutover_date"].map(stichtage),
            "Szenario": cases["series"].map(labels),
            "Zurücksetzen an Tag": cases["reset_day"],
            "gepaarte Tage": cases["paired_days"].astype("Int64"),
            "Differenz Tagesfehler [W]": cases["day_error_delta_w"],
            "belastbar": cases["day_error_reliable"].map(YES_NO),
            "Differenz Meldungen je 30 Tage": cases["notification_delta"],
        }
    ).sort_values(["Stichtag"], kind="stable")


def build_control_table(
    control: pd.DataFrame, stichtage: dict[str, str]
) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Stichtag": control["cutover_date"].map(stichtage),
            "System": control["config"],
            "Tage": control["days"],
            "Meldungstage": control["notification_days"],
            "Zurücksetzen": control["resets"],
        }
    ).sort_values(["Stichtag"], kind="stable")


def build_latency_table(
    summary: E3Summary,
    *,
    reference: str,
    labels: dict[str, str],
    stichtage: dict[str, str],
) -> pd.DataFrame:
    latency = summary.latency.sort_values(["cutover_date"], kind="stable")
    total = summary.latency_total.iloc[0]
    table = pd.DataFrame(
        {
            "Stichtag": latency["cutover_date"].map(stichtage),
            "Szenario": latency["series"].map(labels),
            "Aufrufe": latency["llm_calls"],
            "Ausfalltage": latency["failed_days"],
            "Mehrlaufzeit [s]": latency["extra_seconds"],
            "je Aufruf [s]": latency["extra_seconds_per_call"],
        }
    )
    total_row = pd.DataFrame(
        {
            "Stichtag": ["alle"],
            "Szenario": ["alle"],
            "Aufrufe": [total["llm_calls"]],
            "Ausfalltage": [total["failed_days"]],
            "Mehrlaufzeit [s]": [total["extra_seconds"]],
            "je Aufruf [s]": [total["extra_seconds_per_call"]],
        }
    )

    return pd.concat([table, total_row], ignore_index=True).astype(
        {"Aufrufe": "Int64", "Ausfalltage": "Int64"}
    )


def build_study_setup(
    e3_config: dict,
    standard_config: dict,
    llm_config: dict,
    run_name: str,
    code_version: dict,
) -> dict[str, str]:
    return build_setup(
        run_name,
        standard_config,
        e3_config["cutovers"][standard_config["split"]],
        code_version,
        scenarios=", ".join(
            events[0][1] for events in e3_config["event_series"].values()
        )
        + ", jeweils ab dem Stichtag, dazu der Kontrolllauf",
        systems=", ".join(e3_config[key] for key in ("reference_system", "llm_system")),
        llm=format_llm(llm_config, "ohne Kalender (CTX0)"),
        details={
            "Fenster": f"{standard_config['monitoring_before_cutover_days']} Tage vor und "
            f"{standard_config['margin_after_days']} Tage ab dem Stichtag"
        },
    )


def build_notes(
    summary: E3Summary, *, reference: str, llm: str, labels: dict[str, str]
) -> list[str]:
    notes = [
        "Tag = Entscheidungstag seit dem Stichtag, an Tag n wird Tag n−1 eingeordnet",
        f"Fall = Stichtag × Szenario. Ein Fall geht in die Auswertung ein, wenn {llm} die Historie zurücksetzt. Erkennung und Einordnung prüfen E1 und E2",
        f"Tagesfehler: ab dem Tag des Zurücksetzens, denn die Prognose desselben Tages enthält es schon. {reference} wird auf denselben Tagen gepaart und setzt nie zurück",
        f"Meldungen: Tage nach dem Zurücksetzen, bei beiden Systemvarianten auf denselben Tagen. Als Meldung zählen {', '.join(NOTIFICATION_CLASSIFICATIONS)}",
        "Woche ab dem Zurücksetzen: Fälle mit spätem Zurücksetzen haben weniger Tage im Fenster und fallen in späteren Wochen heraus, die Spalte Fälle zeigt das",
        "Kontrolllauf über das ganze Fenster, jede Meldung dort ist unbegründet, jedes Zurücksetzen unnötig",
        "Das Kriterium zur Abwesenheit (Tagesfehler nach der Rückkehr) stammt aus den Läufen von E2",
        "Mehrlaufzeit: Laufzeit von SYS3 minus SYS1 je Szenario, geteilt durch die Aufrufe des Sprachmodells. Grobe Schätzung, die Zeit eines Aufrufs wird nicht einzeln gemessen",
        NOISE_RULE_NOTE,
    ]

    for row in summary.separations.loc[
        ~summary.separations["forecast_identical_before"]
    ].to_dict("records"):
        notes.append(
            f"Plausibilitätsprüfung verletzt: bei {labels[row['series']]} {row['cutover_date']} "
            "unterscheiden sich die Prognosen schon vor der ersten abweichenden Aktion"
        )
    if summary.interrupted:
        notes.append(
            "Mindestens eine Systemvariante wurde abgebrochen, der Lauf ist nicht auswertbar"
        )

    return notes


def write_report(run_directory: Path) -> Path:
    raw_directory = run_directory / RAW_SUBDIR
    run_config = read_raw_json(run_directory, "run_config")
    e3_config = run_config["e3_config"]
    standard_config = run_config["standard_config"]
    reference = e3_config["reference_system"]
    llm = e3_config["llm_system"]
    labels = series_labels(e3_config["event_series"])
    stichtage = stichtag_labels(standard_config)

    results = pd.read_csv(
        raw_directory / f"{RESULTS_FILE}.csv", dtype={"cutover_date": str}
    )
    summary = summarize_e3(
        results,
        read_run_meta(raw_directory),
        read_llm_outputs(raw_directory),
        event_series=e3_config["event_series"],
        reference_system=reference,
        llm_system=llm,
        week_days=e3_config["week_days"],
        smoothing_days=E3Config().smoothing_days,
        min_curve_cases=E3Config().min_curve_cases,
    )
    tables = {
        "result_criteria": (
            "Kriterien der Teilfrage 3 aus E3",
            build_criteria(summary, reference=reference, llm=llm),
        ),
        "result_overview": (
            f"Kennzahlen ab dem Zurücksetzen, {llm} gegen {reference}",
            build_overview_table(summary.overall, reference=reference, llm=llm),
        ),
        "result_forecast_weeks": (
            "Tagesfehler und Meldungstage je Woche ab dem Zurücksetzen, alle Fälle",
            build_week_table(
                summary.forecast_weeks,
                summary.notifications_weeks_pooled,
                reference=reference,
                llm=llm,
            ),
        ),
    }
    appendix = {
        "result_forecast_weeks_by_series": (
            "Tagesfehler und Meldungstage je Woche ab dem Zurücksetzen, je Szenario",
            build_week_table(
                summary.forecast_weeks_by_series,
                summary.notifications_weeks_by_series,
                reference=reference,
                llm=llm,
                labels=labels,
            ),
        ),
        "result_cases": (
            "Fälle je Stichtag und Szenario",
            build_case_table(
                summary.cases,
                reference=reference,
                llm=llm,
                labels=labels,
                stichtage=stichtage,
            ),
        ),
        "result_control": (
            "Kontrolllauf: Meldungen und Zurücksetzen ohne Anlass",
            build_control_table(summary.control, stichtage),
        ),
        "result_latency": (
            "Laufzeit des Sprachmodells",
            build_latency_table(
                summary, reference=reference, labels=labels, stichtage=stichtage
            ),
        ),
    }

    output_directory = user_output_directory(run_directory)
    build_e3_week_plot(
        summary.forecast_curve,
        summary.notifications_weeks_pooled,
        output_directory,
        reference=reference,
        llm=llm,
    )

    write_result_report(
        output_directory,
        title="E3: Nutzen der Adaption",
        setup=build_study_setup(
            e3_config,
            standard_config,
            run_config["llm_config"],
            run_directory.name,
            run_config["code_version"],
        ),
        tables=tables,
        notes=build_notes(summary, reference=reference, llm=llm, labels=labels),
        images=["e3_weeks.png"],
        decimals=STANDARD_CONFIG.decimals,
        appendix=appendix,
    )

    return output_directory


def main() -> None:
    output_directory = write_report(
        run_directory_from_argv(PROJECT_CONFIG.e3_output_dir, RUN_PREFIX)
    )

    print(f"Result written to {output_directory / 'ergebnis.md'}")


if __name__ == "__main__":
    main()
