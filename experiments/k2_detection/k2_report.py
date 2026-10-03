# conda activate forecasting-env
# python -m experiments.k2_detection.k2_report [run_directory]

from pathlib import Path

import pandas as pd

from experiments.common.report import (
    KIND_LABELS,
    format_commit,
    format_number,
    write_result_report,
)
from experiments.common.standard_config import (
    DECIMALS,
    PROJECT_CONFIG,
    STANDARD_CONFIG,
)
from experiments.k2_detection.k2_config import (
    DIAGNOSIS_FILE,
    EVENT_HITS_FILE,
    GRID_FILE,
    RUN_PREFIX,
    STREAK_THRESHOLD_COLUMNS,
)
from experiments.k2_detection.k2_evaluation import (
    Headline,
    summarize_diagnosis,
    summarize_headline,
)
from src.pipeline.io import (
    RAW_SUBDIR,
    df_to_csv,
    read_raw_json,
    run_directory_from_argv,
    user_output_directory,
)


def _change_label(prefix: str, factor: float) -> str:
    # ×1,3 als +30 %, ×0,7 als −30 %
    return f"{prefix} {(factor - 1) * 100:+.0f} %".replace("-", "−")


# Beschriftung der Änderungen im K2-Report, Spitzen stehen in KIND_LABELS
CHANGE_LABELS: dict[str, str] = {
    "scaled": _change_label("Sprung", STANDARD_CONFIG.scale_factor),
    "scaled_down": _change_label("Sprung", STANDARD_CONFIG.scale_factor_down),
    "ramp_28": _change_label("Rampe über 28 Tage", STANDARD_CONFIG.scale_factor),
    "ramp_28_down": _change_label(
        "Rampe über 28 Tage", STANDARD_CONFIG.scale_factor_down
    ),
    "ramp_56": _change_label("Rampe über 56 Tage", STANDARD_CONFIG.scale_factor),
    "ramp_56_down": _change_label(
        "Rampe über 56 Tage", STANDARD_CONFIG.scale_factor_down
    ),
}

EXPECTATION_LABELS: dict[str, str] = {
    "positive": "erkennen",
    "negative": "nicht feuern",
    "single_day": "Alarm am Ereignistag",
}

CONFIG_LABELS: dict[str, str] = {"chosen": "gewählt", "current": "aktuelle Config"}

SCENARIO_LABELS = KIND_LABELS | CHANGE_LABELS

RESULT_HEADERS = {
    "config": "Einstellung",
    "thresholds": "weekday / weekly / long_term %",
    "detected": "echte Trends erkannt",
    "mean_delay": "Tage bis Erkennung (Mittel)",
    "resets": "Resets gesamt",
    "false_per_year": "falsche Resets je Jahr",
    "limit": "Grenze",
}
EVENT_HEADERS = {
    "start": "Beginn",
    "change_pct": "Änderung [%]",
    "chosen_reset": "gewählt: Reset am",
    "chosen_delay": "gewählt: Tage seit Beginn",
    "current_reset": "aktuelle Config: Reset am",
    "current_delay": "aktuelle Config: Tage seit Beginn",
}
DIAGNOSIS_HEADERS = {
    "kind": "Szenario",
    "expectation": "Sollverhalten",
    "chosen_detected": "gewählt: erkannt bzw. feuert (n von N Fenstern)",
    "chosen_day": "gewählt: Tage (Mittel)",
    "current_detected": "aktuelle Config: erkannt bzw. feuert (n von N Fenstern)",
    "current_day": "aktuelle Config: Tage (Mittel)",
}
GRID_HEADERS = {
    "weekday_streak_threshold": "weekday",
    "weekly_streak_threshold": "weekly",
    "long_term_streak_threshold_pct": "long_term [%]",
    "detected": "echte Trends erkannt",
    "mean_delay": "Tage bis Erkennung (Mittel)",
    "false_per_year": "falsche Resets je Jahr",
    "selected": "gewählt",
    "current": "aktuelle Config",
}


def format_threshold(value: float) -> str:
    # Schwellen wie 1,25 würden mit einer Nachkommastelle zu 1,2
    return f"{value:g}".replace(".", ",")


def format_thresholds(values: list[float]) -> str:
    return " / ".join(format_threshold(value) for value in values)


def _date_text(dates: pd.Series) -> pd.Series:
    return dates.dt.strftime("%d.%m.%Y").fillna("nicht erkannt")


def _ratio(hits: pd.Series, total: pd.Series) -> list[str]:
    return [f"{int(hit)}/{int(count)}" for hit, count in zip(hits, total)]


def _grid_table(ranked: pd.DataFrame) -> pd.DataFrame:
    table = ranked.assign(detected=_ratio(ranked["hits"], ranked["events"]))[
        list(GRID_HEADERS)
    ].copy()
    table["selected"] = ranked["selected"].map({True: "ja", False: ""})
    table["current"] = ranked["current"].map(
        {True: CONFIG_LABELS["current"], False: ""}
    )
    for column in STREAK_THRESHOLD_COLUMNS.values():
        table[column] = table[column].map(format_threshold)

    return table.rename(columns=GRID_HEADERS)


def _expectation(kind: str, k2_config: dict) -> str:
    if kind in k2_config["positive_kinds"]:
        return EXPECTATION_LABELS["positive"]
    if kind in k2_config["negative_kinds"]:
        return EXPECTATION_LABELS["negative"]

    return EXPECTATION_LABELS["single_day"]


def verdict(met: bool) -> str:
    return "erreicht" if met else "nicht erreicht"


def build_setup(run_config: dict, k2_config: dict) -> dict[str, str]:
    analysis = run_config["analysis"]
    detector = run_config["numerical_analysis_config"]

    return {
        "Zeitraum": (
            f"bewertet {analysis['first_day']} bis {analysis['last_day']} ({analysis['days']} Tage), davor der Kaltstart. "
            "Kalibriert wird nur auf dem Train-Split"
        ),
        "Echte Trends": (
            f"{analysis['events']} im Zeitraum: Niveau ändert sich um mindestens {format_number(k2_config['event_min_change_pct'], 0)} % "
            f"gegen die {k2_config['event_reference_days']} Tage davor, der Übergang ist nach {k2_config['event_transition_days']} Tagen abgeschlossen "
            f"und das neue Niveau hält mindestens {k2_config['event_min_duration_days']} Tage"
        ),
        "Treffer": (
            f"ein Reset von {k2_config['hit_days_before']} Tagen vor bis {analysis['hit_days_after']} Tage nach dem Beginn eines echten Trends. "
            "Jeder andere Reset ist falsch"
        ),
        "Modus": "mit Reset: schlanke Kette (Analyse, Streak, Einordnung nach Regel, Reset) über die ganze Reihe, ohne Prognose und ohne LLM",
        "Detektor": (
            f"Referenz Rolling {detector['reference_window_rolling_days']} vor dem Beobachtungsfenster, "
            f"Median/MAD für {' und '.join(detector['single_day_scales'])}"
        ),
        "Commit": format_commit(run_config["code_version"]),
    }


def build_summary(
    headline: Headline,
    selected: pd.Series,
    current: pd.Series,
    thresholds: dict[str, str],
    k2_config: dict,
) -> list[str]:
    target = format_number(k2_config["target_detected_share"] * 100, 0)
    slow_target = format_number(k2_config["max_slow_fired_share"] * 100, 0)
    limit = format_number(k2_config["max_false_resets_per_year"], DECIMALS)

    return [
        f"Gewählt: weekday / weekly / long_term % = {thresholds['chosen']} (aktuelle Config {thresholds['current']})",
        f"Echte Trends mit Reset: {selected['hits']} von {selected['events']} erkannt, im Mittel nach {format_number(selected['mean_delay'], 1)} Tagen. Ziel mindestens {target} %: {verdict(headline.detection_met)}. Aktuelle Config: {current['hits']} von {current['events']}",
        f"Falsche Resets: {format_number(selected['false_per_year'], DECIMALS)} je Jahr (Grenze {limit}: {verdict(headline.false_met)}), aktuelle Config {format_number(current['false_per_year'], DECIMALS)}",
        f"Diagnose mit Eingriffen: Sprung und Rampe 28 Tage erkannt in {headline.diagnosis_hits} von {headline.diagnosis_windows} Fällen, langsame Rampen feuern in {headline.slow_fired} von {headline.slow_windows} (Ziel höchstens {slow_target} %: {verdict(headline.slow_met)})",
    ]


def build_result_table(
    selected: pd.Series,
    current: pd.Series,
    thresholds: dict[str, str],
    limit: float,
) -> pd.DataFrame:
    rows = pd.DataFrame([selected, current]).reset_index(drop=True)

    return pd.DataFrame(
        {
            "config": [CONFIG_LABELS["chosen"], CONFIG_LABELS["current"]],
            "thresholds": [thresholds["chosen"], thresholds["current"]],
            "detected": _ratio(rows["hits"], rows["events"]),
            "mean_delay": rows["mean_delay"],
            "resets": rows["resets"],
            "false_per_year": rows["false_per_year"],
            "limit": limit,
        }
    )


def build_event_table(event_hits: pd.DataFrame) -> pd.DataFrame:
    return event_hits.assign(
        start=event_hits["start"].dt.strftime("%d.%m.%Y"),
        chosen_reset=_date_text(event_hits["chosen_reset"]),
        current_reset=_date_text(event_hits["current_reset"]),
    )


def build_diagnosis_table(
    diagnosis: pd.DataFrame, kinds: list[str], k2_config: dict
) -> pd.DataFrame:
    chosen = (
        diagnosis.loc[diagnosis["config"].eq("chosen")].set_index("kind").loc[kinds]
    )
    current = (
        diagnosis.loc[diagnosis["config"].eq("current")].set_index("kind").loc[kinds]
    )

    return pd.DataFrame(
        {
            "kind": [SCENARIO_LABELS[kind] for kind in kinds],
            "expectation": [_expectation(kind, k2_config) for kind in kinds],
            "chosen_detected": _ratio(chosen["hits"], chosen["windows"]),
            "chosen_day": chosen["mean_day"].to_numpy(),
            "current_detected": _ratio(current["hits"], current["windows"]),
            "current_day": current["mean_day"].to_numpy(),
        }
    )


def build_notes(run_config: dict, k2_config: dict) -> list[str]:
    limit = format_number(k2_config["max_false_resets_per_year"], DECIMALS)
    blind_days = run_config["numerical_analysis_config"]["long_term_window_days"]

    return [
        f"Gewählt wird unter der Grenze für falsche Resets je Jahr ({limit}) der Punkt mit den meisten erkannten echten Trends, dann dem kürzesten mittleren Verzug. Das Raster steht vollständig in result_streak_sensitivity.csv",
        f"Ein Reset im Trefferfenster eines Trends zählt als Treffer, auch wenn ein Reset zwei nahe Ereignisse trifft. Nach einem Reset fehlen weekday und long_term etwa {blind_days} Tage, das ist im Lauf enthalten",
        f"Diagnose: positive Art = erster Reset in Tag 1 bis {run_config['analysis']['hit_days_after']} nach dem Cutover. Langsame Rampe = erster Reset außerhalb der Trefferfenster echter Trends (soll nie vorkommen). Spitze = Alarm am Ereignistag. Beginne des natürlichen Hintergrunds zählen mit",
        "Grenzen: wenige echte Trends in einem Haushalt, ein Treffer mehr oder weniger sind mehrere Prozentpunkte. Der Unterschied zwischen benachbarten Rasterpunkten ist nicht belastbar. Mindeständerung, Übergangs- und Haltedauer, Trefferfenster und die Grenze für falsche Resets sind Setzungen",
        "Die gewählten Schwellen sind in NumericalAnalysisConfig zu übernehmen, gerundet",
    ]


def write_report(run_directory: Path) -> Path:
    run_config = read_raw_json(run_directory, "run_config")
    k2_config = run_config["k2_config"]
    chosen = run_config["numerical_analysis_config"]
    thresholds = {
        "chosen": format_thresholds(
            [chosen[column] for column in STREAK_THRESHOLD_COLUMNS.values()]
        ),
        "current": format_thresholds(
            list(run_config["analysis"]["current_thresholds"].values())
        ),
    }

    raw = run_directory / RAW_SUBDIR
    ranked = pd.read_csv(raw / f"{GRID_FILE}.csv")
    event_hits = pd.read_csv(
        raw / f"{EVENT_HITS_FILE}.csv",
        parse_dates=["start", "chosen_reset", "current_reset"],
    )
    cases = pd.read_csv(raw / f"{DIAGNOSIS_FILE}.csv", dtype={"cutover_date": str})
    diagnosis = summarize_diagnosis(cases)

    selected = ranked.loc[ranked["selected"]].iloc[0]
    current = ranked.loc[ranked["current"]].iloc[0]
    headline = summarize_headline(
        selected,
        diagnosis,
        positive_kinds=tuple(k2_config["positive_kinds"]),
        negative_kinds=tuple(k2_config["negative_kinds"]),
        target_detected_share=k2_config["target_detected_share"],
        max_false_per_year=k2_config["max_false_resets_per_year"],
        max_slow_fired_share=k2_config["max_slow_fired_share"],
    )
    excerpt = pd.concat(
        [ranked.head(k2_config["report_grid_rows"]), ranked.loc[ranked["current"]]]
    ).drop_duplicates(subset=list(STREAK_THRESHOLD_COLUMNS.values()))

    tables = {
        "result_thresholds": (
            "Ergebnis auf den echten Daten: gewählte Schwellen gegen aktuelle Config",
            build_result_table(
                selected, current, thresholds, k2_config["max_false_resets_per_year"]
            ).rename(columns=RESULT_HEADERS),
        ),
        "result_events": (
            "Echte Trends: wann meldet der Detektor (mit Reset)?",
            build_event_table(event_hits).rename(columns=EVENT_HEADERS),
        ),
        "result_diagnosis": (
            "Diagnose mit Eingriffen: ab welcher Änderung erkennt er? (Cutover-Fenster, mit Reset)",
            build_diagnosis_table(
                diagnosis, run_config["analysis"]["diagnosis_kinds"], k2_config
            ).rename(columns=DIAGNOSIS_HEADERS),
        ),
        "result_grid_excerpt": (
            f"Raster der Schwellen nach Rang (die besten {k2_config['report_grid_rows']} und die aktuelle Config)",
            _grid_table(excerpt),
        ),
    }

    output_directory = user_output_directory(run_directory)

    write_result_report(
        output_directory,
        title=f"K2 Schwellen der Anomalieerkennung, Lauf {run_directory.name}",
        summary=build_summary(headline, selected, current, thresholds, k2_config),
        setup=build_setup(run_config, k2_config),
        tables=tables,
        notes=build_notes(run_config, k2_config),
        images=[],
        decimals=DECIMALS,
    )
    df_to_csv(_grid_table(ranked), output_directory, "result_streak_sensitivity")

    return output_directory


def main() -> None:
    output_directory = write_report(
        run_directory_from_argv(PROJECT_CONFIG.k2_output_dir, RUN_PREFIX)
    )

    print(f"Result written to {output_directory / 'ergebnis.md'}")


if __name__ == "__main__":
    main()
