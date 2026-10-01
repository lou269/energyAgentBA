# conda activate forecasting-env
# python -m experiments.k2_detection.k2_report [run_directory]

from collections.abc import Sequence
from pathlib import Path

import pandas as pd

from experiments.common.evaluation import add_days_since_cutover, pair_with_control
from experiments.common.report import (
    format_commit,
    format_number,
    key_figures_table,
    relabel,
    write_result_report,
)
from experiments.common.standard_config import DECIMALS, KIND_LABELS, PROJECT_CONFIG
from experiments.k2_detection.k2_config import (
    CALIBRATION_FILES,
    DETECTOR_VARIANT,
    MODE_LABELS,
    RESULTS_FILE,
    RUN_PREFIX,
    STREAK_THRESHOLD_COLUMNS,
    VARIANT_LABELS,
    K2Config,
)
from experiments.k2_detection.k2_evaluation import (
    PAIR_KEYS,
    CalibrationSummary,
    summarize_calibration,
    summarize_detection,
    summarize_gate_open,
    summarize_quiet_days,
)
from src.pipeline.io import (
    RAW_SUBDIR,
    read_raw_json,
    run_directory_from_argv,
    user_output_directory,
)

KEY_ORDER = {
    "variant": list(VARIANT_LABELS),
    "mode": list(MODE_LABELS),
    "kind": list(KIND_LABELS),
}
KEY_VALUE_LABELS = {
    "variant": VARIANT_LABELS,
    "mode": MODE_LABELS,
    "kind": KIND_LABELS,
}
KEY_HEADERS = {"variant": "Variante", "mode": "Modus", "kind": "Ereignis"}

QUIET_DAY_HEADERS = {
    "gate_open_adaption_pct": "Gate offen mit Reset [%]",
    "alarm_adaption_pct": "davon Einzeltag mit Reset [%]",
    "control_resets": "Resets der Kontrolle je Fenster",
}
DETECTION_HEADERS = {
    "mean": "Mittel erkannter",
    "detected": "erkannt",
    "false_resets": "falsche Resets je Fenster",
    "scales": "Skala bei Erkennung",
}
GATE_HEADERS = {
    "cutover_date": "Cutover",
    "gate_threshold": "Schwelle (Score)",
    "alarm_pct": "Einzeltag-Alarme Kontrolle [%]",
}
SENSITIVITY_HEADERS = {
    "weekday_streak_threshold": "Streak weekday",
    "weekly_streak_threshold": "Streak weekly",
    "long_term_streak_threshold_pct": "Streak long_term [%]",
    "false_new_pattern": "falsche new_pattern je Fenster",
    "detected": "Stufe erkannt",
    "detection_day": "Erkennungstag im Mittel",
    "selected": "gewählt",
}


def _labeled(table: pd.DataFrame, headers: dict[str, str]) -> pd.DataFrame:
    # erst in fester Reihenfolge sortieren, dann übersetzen
    keys = [key for key in KEY_ORDER if key in table]
    ordered = table.copy()

    for key in keys:
        ordered[key] = pd.Categorical(ordered[key], KEY_ORDER[key])
    ordered = ordered.sort_values(keys, kind="stable")

    return relabel(ordered, KEY_HEADERS, KEY_VALUE_LABELS).rename(columns=headers)


def read_calibration(run_directory: Path) -> dict[str, pd.DataFrame]:
    return {
        name: pd.read_csv(
            run_directory / RAW_SUBDIR / f"{file}.csv", dtype={"cutover_date": str}
        )
        for name, file in CALIBRATION_FILES.items()
    }


def format_thresholds(values: Sequence[object]) -> str:
    # Schwellen wie 1,25 würden mit einer Nachkommastelle zu 1,2
    return " / ".join(f"{value:g}".replace(".", ",") for value in values)


def build_setup(
    run_config: dict, k2_config: K2Config, loop_thresholds: str
) -> dict[str, str]:
    standard_config = run_config["standard_config"]

    return {
        "Cutover": ", ".join(standard_config["cutover_dates"]),
        "Zeitraum je Cutover": (
            f"Kaltstart, {standard_config['monitoring_before_cutover_days']} Tage Überwachung vor dem Cutover, {standard_config['margin_after_days']} Tage danach"
        ),
        "Ereignisse ab Cutover": ", ".join(
            KIND_LABELS[kind] for kind in k2_config.kinds if kind != "control"
        )
        + ", jeweils gepaart mit unverändertem Kontrolllauf",
        "Modi": (
            "ohne Reset = nur Detektor, darauf werden Einzeltag-Schwelle und Streak-Empfindlichkeit bestimmt (nur "
            + ", ".join(KIND_LABELS[kind] for kind in k2_config.isolated_kinds)
            + "). Mit Reset = Betrieb mit Regel wie SYS2, alle Ereignisse"
        ),
        "Detektor": "Referenz Rolling 60 vor dem Beobachtungsfenster, Median/MAD für daily und weekday",
        "Schwellen im Lauf (Einzeltag / Streak weekday / weekly / long_term %)": loop_thresholds,
        "Commit": format_commit(run_config["code_version"]),
    }


def build_key_figures(
    quiet_days: pd.DataFrame,
    detection: pd.DataFrame,
    false_resets: pd.DataFrame,
    calibration: CalibrationSummary,
    *,
    single_day_kinds: tuple[str, ...],
    target_rate_pct: float,
    gate_threshold_decimals: int,
    max_false_new_pattern: float,
) -> pd.DataFrame:
    label = VARIANT_LABELS[DETECTOR_VARIANT]
    quiet = quiet_days.set_index("variant").loc[DETECTOR_VARIANT]
    in_loop = detection.loc[detection["variant"].eq(DETECTOR_VARIANT)]
    selected = calibration.streak_sensitivity.loc[
        calibration.streak_sensitivity["selected"].eq("ja")
    ].iloc[0]

    rows = [
        (
            f"Einzeltag-Schwelle für {format_number(target_rate_pct, 0)} % Alarme in der Kontrolle",
            format_number(calibration.gate_threshold, gate_threshold_decimals),
            "gilt im Lauf mit Reset",
        ),
        (
            "Streak-Schwellen (weekday / weekly / long_term %), Fehlalarm-Budget und früheste Erkennung",
            format_thresholds(list(calibration.streak_selected.values())),
            "gilt im Lauf mit Reset",
        ),
        (
            f"{label}: Gate offen ohne Ereignis, mit Reset [%]",
            quiet["gate_open_adaption_pct"],
            "Einzeltag-Alarme und Drift zusammen",
        ),
        (
            f"{label}: falsche Resets im Betrieb je Fenster, alle Ereignisse",
            false_resets.set_index("variant").loc[DETECTOR_VARIANT, "false_resets"],
            "nur Resets, die der Kontrolllauf in ±Toleranz nicht hat, bei einer Dauerlast ohne die Erkennung",
        ),
        (
            f"{label}: Resets im Kontrolllauf ohne Ereignis, je Fenster",
            quiet["control_resets"],
            f"Grundrate, zählt nicht als falsch. Ohne Reset (gewählter Punkt) {format_number(selected['false_new_pattern'], DECIMALS)}, Budget {format_number(max_false_new_pattern, DECIMALS)}",
        ),
    ]
    for kind, detected, mean_day, scales, resets in zip(
        in_loop["kind"],
        in_loop["detected"],
        in_loop["mean"],
        in_loop["scales"],
        in_loop["false_resets"],
    ):
        reference = ""
        if kind not in single_day_kinds and pd.notna(mean_day):
            reference = f"im Mittel nach {format_number(mean_day, 1)} Tagen, "
        reference += f"Skala {scales or '-'}"
        reference += f", falsche Resets {format_number(resets, DECIMALS)} je Fenster"
        how = "Alarm am Ereignistag" if kind in single_day_kinds else "new_pattern"
        rows.append(
            (f"{label}: {KIND_LABELS[kind]} erkannt ({how})", detected, reference)
        )

    return key_figures_table(rows)


def main() -> None:
    k2_config = K2Config()

    run_directory = run_directory_from_argv(PROJECT_CONFIG.k2_output_dir, RUN_PREFIX)
    run_config = read_raw_json(run_directory, "run_config")
    numerical_analysis_config = run_config["numerical_analysis_config"]
    streak_thresholds = [
        numerical_analysis_config[column]
        for column in STREAK_THRESHOLD_COLUMNS.values()
    ]
    loop_thresholds = format_thresholds(
        [numerical_analysis_config["unusual_threshold"]] + streak_thresholds
    )

    results = add_days_since_cutover(
        pd.read_csv(
            run_directory / RAW_SUBDIR / f"{RESULTS_FILE}.csv",
            dtype={"cutover_date": str},
        )
    )
    calibration = summarize_calibration(
        read_calibration(run_directory),
        k2_config.uncounted_cutovers,
        k2_config.max_false_new_pattern,
    )

    gate_open = summarize_gate_open(results)
    quiet_days = summarize_quiet_days(gate_open)
    detection_summary = summarize_detection(
        pair_with_control(results, PAIR_KEYS),
        k2_config.single_day_kinds,
        control_reset_tolerance_days=k2_config.control_reset_tolerance_days,
        uncounted_cutovers=k2_config.uncounted_cutovers,
    )
    detection = detection_summary.table
    detection_headers = dict(DETECTION_HEADERS)
    for cutover_date in k2_config.uncounted_cutovers:
        detection_headers[cutover_date] = f"{cutover_date} (Dauerlast nicht gezählt)"

    # Schwellen wie 0,75 als Text, weil sonst Rundung
    sensitivity = calibration.streak_sensitivity[list(SENSITIVITY_HEADERS)].copy()
    for column in STREAK_THRESHOLD_COLUMNS.values():
        sensitivity[column] = sensitivity[column].map(
            lambda value: format_thresholds([value])
        )

    tables = {
        "key_figures": (
            "Kennzahlen",
            build_key_figures(
                quiet_days,
                detection,
                detection_summary.false_resets,
                calibration,
                single_day_kinds=k2_config.single_day_kinds,
                target_rate_pct=k2_config.target_alarm_pct,
                gate_threshold_decimals=k2_config.gate_threshold_decimals,
                max_false_new_pattern=k2_config.max_false_new_pattern,
            ),
        ),
        "result_quiet_days": (
            "Ohne Ereignis: Kontrolllauf über das ganze Fenster, Mittel über Cutover",
            _labeled(quiet_days, QUIET_DAY_HEADERS),
        ),
        "result_gate_threshold": (
            "Einzeltag-Schwelle: ein Wert für daily und weekday, Alarmrate der Kontrolle je Cutover, ohne Reset",
            calibration.alarm_by_window[list(GATE_HEADERS)].rename(
                columns=GATE_HEADERS
            ),
        ),
        "result_streak_sensitivity": (
            "Streak-Schwellen: Raster und gewählter Punkt, ohne Reset, Mittel über Cutover",
            sensitivity.rename(columns=SENSITIVITY_HEADERS),
        ),
        "result_detection": (
            "Erkennung je Ereignis im Betrieb mit Reset, Tag seit Cutover je Cutover",
            _labeled(detection, detection_headers),
        ),
    }
    notes = [
        "Tag seit Cutover = Entscheidungstag: an Tag n meldet das System, eingeordnet ist dabei Tag n-1. Ab Cutover zählt deshalb erst ab Tag 1",
        f"Einzeltag-Schwelle: das {format_number(100 - k2_config.target_alarm_pct, 0)}-%-Quantil des größten Scores von daily und weekday an den Kontrolltagen, ein Wert für beide. "
        "Streak-Schwellen: Raster, gewählt wird nach dem Fehlalarm-Budget (max_false_new_pattern) und dann nach früher Erkennung in allen gezählten Fenstern. Beides offline auf den Läufen ohne Reset, Einzeltag-Schwelle und falsche new_pattern über alle Cutover, die Erkennung der Stufe ohne die nicht gezählten",
        "Stufe erkannt (ohne Reset): erster Tag, an dem bei der Stufe ein new_pattern beginnt und bei der Kontrolle "
        f"{k2_config.control_reset_tolerance_days} Tage davor und danach keins, also wie im Betrieb mit Reset",
        "Der Lauf mit Reset nutzt die gewählten Schwellen (Einzeltag und Streak), aus demselben Lauf. In NumericalAnalysisConfig übernehmen, gerundet",
        "erkannt, im Betrieb mit Reset: dauerhafte Änderung = erster eigener Reset (new_pattern) nach dem Cutover, der Kontrolllauf "
        f"hat {k2_config.control_reset_tolerance_days} Tage davor und danach keinen. Einzeltag-Spitze = Alarm am Ereignistag, "
        "den der Kontrolllauf nicht hat",
        "nicht gezählt: "
        + ", ".join(k2_config.uncounted_cutovers)
        + ", Beginn der Heizperiode. Die Kontrolle liegt dort knapp unter der Streak-Bedingung, jede Störung löst new_pattern aus. "
        "Mittel, erkannt und Skala der Dauerlasten ohne diese Cutover, die Einzeltag-Spitzen zählen dort mit",
        "Resets der Kontrolle: Resets des Kontrolllaufs ohne Änderung, im Betrieb mit Reset, Mittel über alle Cutover. Die Grundrate (vor allem Jahreszeit), Vergleichsbasis für die falschen Resets und vergleichbar mit den falschen new_pattern ohne Reset, die ebenfalls an der Kontrolle gezählt werden",
        "falsche Resets: eigene Resets nach dem Cutover, für die die Kontrolle in ±Toleranz keinen Reset hat. Bei einer Dauerlast ist der erste Reset die Erkennung und zählt nicht, bei einer Spitze zählt jeder",
        "Skala bei Erkennung: bei new_pattern die Skalen mit Streak, bei der Spitze die Einzeltag-Skala mit dem höchsten Score",
    ]

    output_directory = user_output_directory(run_directory)

    write_result_report(
        output_directory,
        title=f"K2 Schwellen der Anomalieerkennung, Lauf {run_directory.name}",
        setup=build_setup(run_config, k2_config, loop_thresholds),
        tables=tables,
        notes=notes,
        images=[],
        decimals=DECIMALS,
    )

    print(f"Result written to {output_directory / 'ergebnis.md'}")


if __name__ == "__main__":
    main()
