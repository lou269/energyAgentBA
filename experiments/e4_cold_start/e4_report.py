# conda activate forecasting-env
# python -m experiments.e4_cold_start.e4_report [run_directory]

import pandas as pd

from docs.plots.plot_e4_cold_start import build_e4_forecast_plot, build_e4_system_plot
from experiments.common.report import (
    KIND_LABELS,
    NOISE_RULE_NOTE,
    format_commit,
    format_number,
    key_figures_table,
    paired_difference_columns,
    relabel,
    write_result_report,
)
from experiments.common.standard_config import DECIMALS, PROJECT_CONFIG
from experiments.e4_cold_start.e4_config import (
    CLEAN_SCENARIO,
    FORECAST_METRICS_FILE,
    RUN_PREFIX,
    SYSTEM_RESULTS_FILE,
)
from experiments.e4_cold_start.e4_evaluation import (
    ALL_SCALES,
    GATE_SCALE,
    E4Summary,
    summarize_e4,
)
from src.config.config_forecasting import SYS_LABELS
from src.pipeline.io import (
    RAW_SUBDIR,
    read_raw_json,
    run_directory_from_argv,
    user_output_directory,
)
from src.structured_state.structured_state_schema import SCALE_NAMES

SCENARIO_LABELS = {CLEAN_SCENARIO: "ohne Injektion"} | KIND_LABELS

CRITERION_LABELS = {
    "no_malfunction": "keine Fehlfunktion",
    "usable_from_start": "von Anfang an nutzbar",
    "adapts": "passt sich an",
    "adaptive_vs_static": "adaptiv gegen statisch",
}

CHECK_LABELS = {
    "resets_in_settling": "Resets, solange nicht alle Skalen einen Score haben",
    "forecast_skill_first_window_pct": "Skill der Prognose gegenüber der Baseline in Woche 1 [%]",
    "first_gate_scale_day": "erster Tag mit Gate-Skala, spätester Termin",
    "forecast_settling_day": "Einschwingtag Prognose",
    "notification_settling_day": "Einschwingtag Meldungen, spätester Termin",
    "detection_settling_day": "Einschwingtag Erkennung, spätester Termin und Art",
    "classification_settling_day": "Einschwingtag Einordnung, spätester Termin und Art",
    "static_worse_share": "Anteil der Fenster ab Woche 2, in denen statisch an jedem Termin schlechter ist",
}

# Kennzahl und Bezug, {total} ist die Bezugsgröße aus summarize_price
PRICE_LABELS = {
    "mae_gap_w": ("Zusatz-MAE der Prognose [W]", "bei {total} W mit langem Kaltstart"),
    "only_shortest": (
        "Meldetage nur mit kurzem Kaltstart",
        "von {total} sauberen Tagen",
    ),
    "only_longest": (
        "Meldetage nur mit langem Kaltstart",
        "von {total} sauberen Tagen",
    ),
    "unknown": ("unknown-Tage", "von {total} sauberen Tagen"),
    "missed": ("verpasste Injektionen", "von {total}, die der lange Kaltstart meldet"),
    "class_other": (
        "Injektionen mit anderer Klasse",
        "von {total}, die der lange Kaltstart meldet",
    ),
    "class_unknown": (
        "Injektionen mit unknown statt Klasse",
        "von {total}, die der lange Kaltstart meldet",
    ),
}

KEY_HEADERS = {
    "start_date": "Starttermin",
    "coldstart_days": "Kaltstart [Tage]",
    "model_id": "Modell",
    "window": "Tage seit Start",
    "scenario": "Szenario",
    "injection_day": "Injektionstag",
    "scale": "Skala",
}
VALUE_LABELS = {
    "scenario": SCENARIO_LABELS,
    "scale": {scale: scale for scale in SCALE_NAMES}
    | {GATE_SCALE: "erste Gate-Skala", ALL_SCALES: "alle vier (Einschwingzeit)"},
}
# Tage ohne Nachkommastellen, leer bleibt leer
DAY_COLUMNS = [
    "settling_day",
    "detection_settling_day",
    "classification_settling_day",
    "latest_day",
    "latest_history_days",
    "injection_day",
    "day_since_start",
]


def _labeled(table: pd.DataFrame, headers: dict[str, str]) -> pd.DataFrame:
    days = [column for column in DAY_COLUMNS if column in table]
    return relabel(
        table.astype({column: "Int64" for column in days}),
        KEY_HEADERS | headers,
        VALUE_LABELS,
    )


def build_criteria_table(criteria: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Kriterium": criteria["criterion"].map(CRITERION_LABELS),
            "Prüfung": criteria["check"].map(CHECK_LABELS),
            "erfüllt": criteria["fulfilled"].map({True: "ja", False: "nein"}),
            "Wert": criteria["value"],
        }
    )


def build_setup(run_config: dict) -> dict[str, str]:
    e4_config = run_config["e4_config"]
    system_config = run_config["system_config"]
    llm_config = system_config["llm_config"]

    return {
        "Starttermine": f"{', '.join(e4_config['start_dates'])} ({e4_config['split']})",
        "Kaltstart": (
            f"E4a {', '.join(map(str, e4_config['forecast_coldstart_days']))} Tage, "
            f"E4b {', '.join(map(str, e4_config['system_coldstart_days']))} Tage, "
            "jeweils alle Tage am ersten Entscheidungstag, der erste eingeordnete Tag zählt mit"
        ),
        "Auswertung": (
            f"{e4_config['evaluation_days']} Tage ab Start, je Starttermin dieselben Kalendertage für alle Kaltstart-Längen"
        ),
        "Prognose (E4a)": (
            f"{run_config['prophet_variant']['model_id']} täglich nachtrainiert, "
            f"{e4_config['static_variant']['model_id']} nur auf den Starttagen, "
            f"Baseline {run_config['reference_baseline']}, Seed {run_config['seed']}"
        ),
        "Kreislauf (E4b)": (
            f"{SYS_LABELS[e4_config['system']]}, {llm_config['model']}, Prompt {llm_config['prompt_version']}, "
            f"Temperatur {llm_config['temperature']:g}, Adaption an"
        ),
        "Injektionen": (
            f"{', '.join(SCENARIO_LABELS[kind] for kind in e4_config['injection_kinds'])}, "
            f"je Lauf eine, an Tag {', '.join(map(str, e4_config['injection_days']))}, eingeordnet am Tag danach"
        ),
        "Commit": format_commit(run_config["code_version"]),
    }


def build_price_table(price: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for row in price.to_dict("records"):
        label, reference = PRICE_LABELS[row["price"]]
        parts = [label]
        if row["window"] is not None:
            parts.append(f"Tag {row['window']}")
        if row["scenario"] is not None:
            parts.append(SCENARIO_LABELS[row["scenario"]])
        total = format_number(row["total"], DECIMALS)
        share = format_number(row["share_pct"], DECIMALS)
        rows.append(
            (
                ", ".join(parts),
                row["value"],
                f"{reference.format(total=total)} ({share} %)",
            )
        )

    return key_figures_table(rows)


def build_tables(
    summary: E4Summary, shortest: int, longest: int
) -> dict[str, tuple[str, pd.DataFrame]]:
    return {
        "result_criteria": (
            f"Antwort auf TF1: funktioniert mit {shortest} Tagen: {'ja' if summary.works else 'nein'} "
            "(keine Fehlfunktion, von Anfang an nutzbar, passt sich an)",
            build_criteria_table(summary.criteria),
        ),
        "result_resets": (
            "Resets in der Einschwingzeit",
            _labeled(
                summary.system.resets,
                {
                    "analyzed_day": "eingeordneter Tag",
                    "day_since_start": "Tag seit Start",
                    "classification": "Klasse",
                    "available_scales": "Skalen mit Score",
                    "sustained_scales": "anhaltend auffällige Skalen",
                },
            ),
        ),
        "result_price": (
            f"Preis bis zum Einschwingen: {shortest} gegenüber {longest} Tagen Kaltstart, alle Termine",
            build_price_table(summary.price),
        ),
    }


def build_appendix(
    summary: E4Summary, shortest: int, longest: int
) -> dict[str, tuple[str, pd.DataFrame]]:
    forecast = summary.forecast
    system = summary.system

    return {
        "result_forecast_settling": (
            f"Einschwingen Prognose: erster Tag des Fensters, ab dem der Abstand zu {longest} Tagen im Rauschen liegt",
            _labeled(forecast.settling, {"settling_day": "Einschwingtag"}),
        ),
        "result_gate_deviations": (
            f"Einschwingen Meldungen je Termin: saubere Tage mit Gate offen nur bei {shortest} bzw. nur bei {longest} Tagen",
            _labeled(
                system.gate_deviations,
                {
                    "only_shortest": f"nur bei {shortest} Tagen",
                    "only_longest": f"nur bei {longest} Tagen",
                    "settling_day": "Einschwingtag",
                },
            ),
        ),
        "result_injection_settling": (
            "Einschwingen Erkennung und Einordnung je Termin: erster Injektionstag, ab dem alle späteren wie beim langen Kaltstart sind",
            _labeled(
                system.injection_settling,
                {
                    "detection_settling_day": "Erkennung",
                    "classification_settling_day": "Einordnung",
                },
            ),
        ),
        "result_forecast_gap": (
            f"MAE-Abstand zu {longest} Tagen je Modell, gepaart über Termin und Tag, positiv = schlechter",
            pd.concat(
                [
                    _labeled(
                        forecast.gap[["model_id", "coldstart_days", "window"]], {}
                    ),
                    paired_difference_columns(forecast.gap, "Tage"),
                ],
                axis=1,
            ),
        ),
        "result_notifications": (
            "Meldetage und unknown an sauberen Tagen je Fenster",
            _labeled(
                system.notifications,
                {
                    "days": "Tage",
                    "notification_days": "Meldetage",
                    "unknown_days": "unknown",
                    "notifications_per_period": "Meldungen je 30 Tage",
                    "unknown_per_period": "unknown je 30 Tage",
                },
            ),
        ),
        "result_static": (
            "Adaptiv gegen statisch: MAE statisch minus adaptiv je Termin [W], positiv = adaptiv besser",
            _labeled(
                forecast.static_minus_adaptive,
                {"mean": "Mittel", "same_direction": "gleiche Richtung"},
            ),
        ),
        "result_forecast_windows": (
            "Prognose je Fenster: MAE, MAPE und Skill gegenüber der Baseline, Mittel über Termine",
            _labeled(
                forecast.windows,
                {
                    "mae_w": "MAE [W]",
                    "mape_pct": "MAPE [%]",
                    "mae_w_reference": "MAE Baseline [W]",
                    "mae_skill_pct": "Skill [%]",
                },
            ),
        ),
        "result_scales": (
            f"Kontrolle: erster Tag mit Score je Skala bei {shortest} Tagen, saubere Läufe, Historie = Kaltstart + Tag",
            _labeled(
                system.scale_days.loc[system.scale_days["coldstart_days"].eq(shortest)],
                {
                    "starts": "Termine",
                    "latest_day": "spätester Tag",
                    "latest_history_days": "Historie am spätesten Tag",
                },
            ),
        ),
    }


def build_notes(
    summary: E4Summary, *, adaptive_model_id: str, shortest: int
) -> list[str]:
    windows = summary.forecast.windows
    last_window = windows["window"].cat.categories[-1]
    mape = windows.loc[
        windows["model_id"].eq(adaptive_model_id)
        & windows["coldstart_days"].eq(shortest)
        & windows["window"].eq(last_window),
        "mape_pct",
    ].iloc[0]
    cycle = ", ".join(
        f"{row['coldstart_days']} Tage {format_number(row['max_mae_difference_w'], DECIMALS)} W"
        for row in summary.cycle_forecast.to_dict("records")
    )

    return [
        "Tag 0 = erster prognostizierter Tag, eingeordnet wird an ihm der letzte Tag der Start-Historie. Ein Injektionstag k wird am Tag k + 1 eingeordnet",
        "Einschwingtag leer: im letzten Fenster, am letzten Tag bzw. am letzten Injektionstag noch abweichend, also nicht eingeschwungen",
        "Einschwingtage Erkennung und Einordnung nur so fein wie die Injektionstage",
        f"MAPE {adaptive_model_id} mit {shortest} Tagen in Tag {last_window}: {format_number(mape, DECIMALS)} % (Proposal-Kriterium 10 %, hier kein Maßstab)",
        f"Kontrolle Prognose im Kreislauf gegen Walk-Forward bis zum ersten Reset, soll 0 sein: größte Abweichung {cycle}",
        NOISE_RULE_NOTE,
        "Einschränkungen: ein Haushalt, wenige Termine, aufeinanderfolgende Tage sind nicht unabhängig (Standardfehler eher zu klein), "
        "LLM mit Temperatur 0 als deterministisch angenommen (Ollama auf GPU nicht garantiert bitgenau)",
    ]


def main() -> None:
    run_directory = run_directory_from_argv(PROJECT_CONFIG.e4_output_dir, RUN_PREFIX)
    run_config = read_raw_json(run_directory, "run_config")
    e4_config = run_config["e4_config"]
    adaptive_model_id = run_config["prophet_variant"]["model_id"]
    static_model_id = e4_config["static_variant"]["model_id"]
    shortest = min(e4_config["system_coldstart_days"])
    longest = max(e4_config["system_coldstart_days"])

    summary = summarize_e4(
        pd.read_csv(
            run_directory / RAW_SUBDIR / f"{FORECAST_METRICS_FILE}.csv",
            dtype={"start_date": str},
        ),
        pd.read_csv(
            run_directory / RAW_SUBDIR / f"{SYSTEM_RESULTS_FILE}.csv",
            dtype={"start_date": str},
        ),
        adaptive_model_id=adaptive_model_id,
        static_model_id=static_model_id,
        reference_model_id=run_config["reference_baseline"],
        single_day_scales=tuple(
            run_config["system_config"]["numerical_analysis_config"][
                "single_day_scales"
            ]
        ),
        injection_days=tuple(e4_config["injection_days"]),
        window_edges_days=tuple(e4_config["window_edges_days"]),
        smoothing_days=e4_config["smoothing_days"],
    )

    output_directory = user_output_directory(run_directory)
    build_e4_forecast_plot(
        summary.forecast.gap_curve,
        summary.forecast.settling,
        output_directory,
        adaptive_model_id=adaptive_model_id,
        static_model_id=static_model_id,
        smoothing_days=e4_config["smoothing_days"],
    )
    build_e4_system_plot(
        summary.system,
        summary.criteria,
        output_directory,
        shortest=shortest,
        longest=longest,
        evaluation_days=e4_config["evaluation_days"],
        scenario_labels=SCENARIO_LABELS,
    )

    write_result_report(
        output_directory,
        title=f"E4 Kaltstart, Lauf {run_directory.name}",
        setup=build_setup(run_config),
        tables=build_tables(summary, shortest, longest),
        notes=build_notes(
            summary, adaptive_model_id=adaptive_model_id, shortest=shortest
        ),
        images=["e4_forecast_gap.png", "e4_system.png"],
        decimals=DECIMALS,
        appendix=build_appendix(summary, shortest, longest),
    )

    print(f"Result written to {output_directory / 'ergebnis.md'}")


if __name__ == "__main__":
    main()
