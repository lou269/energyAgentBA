# conda activate forecasting-env
# python -m experiments.k3_detection.k3_report [run_directory]

from collections.abc import Sequence
from pathlib import Path

import pandas as pd

from docs.plots.plot_k3_reference_window import build_k3_plot
from experiments.common.evaluation import add_days_since_cutover, pair_with_control
from experiments.common.report import (
    format_commit,
    format_number,
    key_figures_table,
    relabel,
    write_result_report,
)
from experiments.common.standard_config import DECIMALS, KIND_LABELS, PROJECT_CONFIG
from experiments.k3_detection.k3_calibration import threshold_columns
from experiments.k3_detection.k3_config import (
    CALIBRATION_FILES,
    MODE_LABELS,
    REFERENCE_WINDOW_LABELS,
    RESULTS_FILE,
    RUN_PREFIX,
    K3Config,
)
from experiments.k3_detection.k3_evaluation import (
    PAIR_KEYS,
    CalibrationSummary,
    production_variant,
    summarize_calibration,
    summarize_detection,
    summarize_gate_open,
    summarize_quiet_days,
)
from src.config.config_forecasting import NumericalAnalysisConfig
from src.pipeline.io import (
    RAW_SUBDIR,
    read_raw_json,
    run_directory_from_argv,
    user_output_directory,
)

KEY_ORDER = {
    "variant": list(REFERENCE_WINDOW_LABELS),
    "mode": list(MODE_LABELS),
    "kind": list(KIND_LABELS),
}
KEY_VALUE_LABELS = {
    "variant": REFERENCE_WINDOW_LABELS,
    "mode": MODE_LABELS,
    "kind": KIND_LABELS,
}
KEY_HEADERS = {"variant": "Referenzfenster", "mode": "Modus", "kind": "Ereignis"}

QUIET_DAY_HEADERS = {
    "gate_open_isolated_pct": "Gate offen ohne Reset [%]",
    "gate_open_adaption_pct": "Gate offen mit Reset [%]",
    "alarm_adaption_pct": "davon Einzeltag mit Reset [%]",
    "control_resets": "Resets je Fenster",
}
DETECTION_HEADERS = {
    "mean": "Mittel erkannter",
    "detected": "erkannt",
    "single_day_resets": "Einzeltag mit eigenem Reset",
    "scales": "Skala bei Erkennung",
}
CALIBRATION_HEADERS = {
    "rank": "Rang",
    "gate_threshold": "Gate-Schwelle",
    "alarm_pct": "Einzeltag-Alarme Kontrolle [%]",
    "false_new_pattern": "falsche new_pattern je Fenster",
    "detected": "Stufe erkannt",
    "detection_day": "Erkennungstag im Mittel",
    "cutover_date": "Cutover",
    "first_event_new_pattern_day": "Erkennungstag",
}
LOCO_HEADERS = {
    "cutover_date": "zurückgehaltener Cutover",
    "alarm_held_out_pct": "Einzeltag-Alarme zurückgehalten [%]",
    "false_new_pattern_held_out": "falsche new_pattern zurückgehalten",
    "first_event_new_pattern_day": "Erkennungstag zurückgehalten",
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
        if name != "grid"
    }


def build_calibration_table(
    table: pd.DataFrame,
    key_columns: list[str],
    value_columns: list[str],
    slow_scales: tuple[str, ...],
) -> pd.DataFrame:
    thresholds = threshold_columns(slow_scales)
    text = table[key_columns + thresholds + value_columns].copy()

    for column in thresholds:
        text[column] = text[column].map(lambda value: format_thresholds([value]))

    return text


def format_thresholds(values: Sequence[object]) -> str:
    # Schwellen wie 1,25 würden mit einer Nachkommastelle zu 1,2
    return " / ".join(f"{value:g}".replace(".", ",") for value in values)


def build_setup(
    run_config: dict, k3_config: K3Config, variant: str, loop_thresholds: str
) -> dict[str, str]:
    standard_config = run_config["standard_config"]

    return {
        "Cutover": ", ".join(standard_config["cutover_dates"]),
        "Zeitraum je Cutover": (
            f"Kaltstart, {standard_config['monitoring_before_cutover_days']} Tage Überwachung vor dem Cutover, {standard_config['margin_after_days']} Tage danach"
        ),
        "Ereignisse ab Cutover": ", ".join(
            KIND_LABELS[kind] for kind in k3_config.kinds if kind != "control"
        )
        + ", jeweils gepaart mit unverändertem Kontrolllauf",
        "Modi": (
            "ohne Reset = nur Detektor, darauf wird kalibriert (nur "
            + ", ".join(KIND_LABELS[kind] for kind in k3_config.isolated_kinds)
            + "). Mit Reset = Betrieb mit Regel wie SYS2, alle Ereignisse"
        ),
        "Schwellen im Lauf (Gate / weekly / long_term)": loop_thresholds,
        "Produktiv-Referenzfenster": REFERENCE_WINDOW_LABELS[variant],
        "Commit": format_commit(run_config["code_version"]),
    }


def build_key_figures(
    quiet_days: pd.DataFrame,
    detection: pd.DataFrame,
    calibration: CalibrationSummary,
    *,
    variant: str,
    loop_thresholds: str,
    slow_scales: tuple[str, ...],
    target_rate_pct: float,
) -> pd.DataFrame:
    label = REFERENCE_WINDOW_LABELS[variant]
    quiet = quiet_days.set_index("variant").loc[variant]
    points = calibration.operating_points
    calibrated = points.loc[
        points["variant"].eq(variant), threshold_columns(slow_scales)
    ].iloc[0]
    in_loop = detection.loc[detection["variant"].eq(variant)]

    rows = [
        (
            f"Kalibrierung: bestes Referenzfenster bei höchstens {format_number(target_rate_pct, 0)} % Einzeltag-Alarmen",
            REFERENCE_WINDOW_LABELS[calibration.best_variant],
            f"Gate-Schwelle {calibration.best_gate_threshold:g}, im Leave-one-out "
            f"{calibration.loco_wins}/{calibration.loco_folds} Durchgänge vorn".replace(
                ".", ","
            ),
        ),
        (
            f"{label}: kalibrierte Schwellen (Gate / weekly / long_term)",
            format_thresholds(calibrated.tolist()),
            f"im Lauf {loop_thresholds}",
        ),
        (
            f"{label}: Gate offen ohne Ereignis, mit Reset [%]",
            quiet["gate_open_adaption_pct"],
            f"ohne Reset {format_number(quiet['gate_open_isolated_pct'], DECIMALS)} %, Ziel {format_number(target_rate_pct, 0)} %",
        ),
    ]
    for kind, detected, scales, resets in zip(
        in_loop["kind"],
        in_loop["detected"],
        in_loop["scales"],
        in_loop["single_day_resets"],
    ):
        reference = f"Skala {scales or '-'}"
        if pd.notna(resets):
            reference += f", eigener Reset danach {resets}"
        rows.append(
            (f"{label}: {KIND_LABELS[kind]} erkannt, mit Reset", detected, reference)
        )

    return key_figures_table(rows)


def main() -> None:
    k3_config = K3Config()
    target_rate_pct = k3_config.target_alarm_rate * 100
    slow_scales = k3_config.slow_scales

    run_directory = run_directory_from_argv(PROJECT_CONFIG.k3_output_dir, RUN_PREFIX)
    run_config = read_raw_json(run_directory, "run_config")
    numerical_analysis_config = run_config["numerical_analysis_config"]
    variant = production_variant(
        NumericalAnalysisConfig(
            max_reference_window_growth_days=numerical_analysis_config[
                "max_reference_window_growth_days"
            ],
            reference_window_rolling_days=numerical_analysis_config[
                "reference_window_rolling_days"
            ],
        ),
        k3_config.reference_windows,
    )
    loop_thresholds = format_thresholds(
        [numerical_analysis_config["unusual_threshold"]]
        + [
            numerical_analysis_config[f"{scale}_streak_threshold"]
            for scale in slow_scales
        ]
    )

    results = add_days_since_cutover(
        pd.read_csv(
            run_directory / RAW_SUBDIR / f"{RESULTS_FILE}.csv",
            dtype={"cutover_date": str},
        )
    )
    calibration = summarize_calibration(
        read_calibration(run_directory),
        len(run_config["standard_config"]["cutover_dates"]),
    )

    gate_open = summarize_gate_open(results)
    quiet_days = summarize_quiet_days(gate_open)
    detection = summarize_detection(
        pair_with_control(results, PAIR_KEYS),
        k3_config.single_day_kinds,
        control_reset_tolerance_days=k3_config.control_reset_tolerance_days,
        uncounted_cutovers=k3_config.uncounted_cutovers,
    )
    detection_headers = dict(DETECTION_HEADERS)
    for cutover_date in k3_config.uncounted_cutovers:
        detection_headers[cutover_date] = f"{cutover_date} (nicht gezählt)"

    headers = dict(CALIBRATION_HEADERS)
    for scale in slow_scales:
        headers[f"{scale}_threshold"] = f"Streak-Schwelle {scale}"
    loco_headers = dict(headers)
    loco_headers.update(LOCO_HEADERS)

    tables = {
        "key_figures": (
            "Kennzahlen",
            build_key_figures(
                quiet_days,
                detection,
                calibration,
                variant=variant,
                loop_thresholds=loop_thresholds,
                slow_scales=slow_scales,
                target_rate_pct=target_rate_pct,
            ),
        ),
        "result_quiet_days": (
            "Ohne Ereignis: Kontrolllauf über das ganze Fenster, Mittel über Cutover",
            _labeled(quiet_days, QUIET_DAY_HEADERS),
        ),
        "result_calibration": (
            "Kalibrierung: Arbeitspunkt je Referenzfenster bei gleicher Fehlalarmrate, ohne Reset",
            _labeled(
                build_calibration_table(
                    calibration.operating_points,
                    ["rank", "variant"],
                    ["alarm_pct", "false_new_pattern", "detected", "detection_day"],
                    slow_scales,
                ),
                headers,
            ),
        ),
        "result_calibration_loco": (
            "Kalibrierung: Leave-one-cutover-out, auf den übrigen Cutovern gewählt und auf dem zurückgehaltenen geprüft",
            _labeled(
                build_calibration_table(
                    calibration.loco,
                    ["cutover_date", "variant"],
                    [
                        "alarm_held_out_pct",
                        "false_new_pattern_held_out",
                        "first_event_new_pattern_day",
                    ],
                    slow_scales,
                ),
                loco_headers,
            ),
        ),
        "result_detection": (
            "Erkennung je Ereignis im Betrieb mit Reset, Tag seit Cutover je Cutover",
            _labeled(detection, detection_headers),
        ),
    }
    appendix = {
        "result_calibration_by_cutover": (
            "Kalibrierung: Arbeitspunkte je Cutover",
            _labeled(
                build_calibration_table(
                    calibration.by_cutover,
                    ["variant", "rank"],
                    [
                        "cutover_date",
                        "alarm_pct",
                        "false_new_pattern",
                        "first_event_new_pattern_day",
                    ],
                    slow_scales,
                ),
                headers,
            ),
        )
    }
    notes = [
        "Tag seit Cutover = Entscheidungstag: an Tag n meldet das System, eingeordnet ist dabei Tag n-1. Ab Cutover zählt deshalb erst ab Tag 1",
        f"Kalibrierung: je Referenzfenster die niedrigste Gate-Schwelle mit höchstens {format_number(target_rate_pct, 0)} % Einzeltag-Alarmen "
        f"im Kontrolllauf, dann die Streak-Schwellen mit höchstens {format_number(k3_config.max_false_new_pattern, 0)} "
        "falschen new_pattern je Fenster und möglichst vielen, frühen Erkennungen. Offline auf den Läufen ohne Reset, "
        "im Kreislauf hinge jeder Reset selbst an den Schwellen",
        "mit Reset läuft mit den Schwellen im Lauf (Aufbau). Weichen die kalibrierten Schwellen des Produktivfensters davon ab, "
        "Config anpassen und K3 neu laufen lassen, erst dann zeigt der Kreislauf die kalibrierten Schwellen",
        "erkannt, im Betrieb mit Reset: dauerhafte Änderung = erster eigener Reset (new_pattern) nach dem Cutover, der Kontrolllauf "
        f"hat {k3_config.control_reset_tolerance_days} Tage davor und danach keinen. Einzeltag-Spitze = Alarm am Ereignistag, "
        "den der Kontrolllauf nicht hat. Ohne Reset steht die Erkennung der Stufe in der Kalibrierung",
        "nicht gezählt: "
        + ", ".join(k3_config.uncounted_cutovers)
        + ", Beginn der Heizperiode. Die Kontrolle liegt dort knapp unter der Streak-Bedingung, jede Störung löst new_pattern aus. "
        "Mittel, erkannt und Skala ohne diese Cutover",
        "Einzeltag mit eigenem Reset: Cutover, in denen nach der Spitze ein eigener Reset folgt, über alle Cutover. Eine Spitze soll keinen auslösen",
        "Skala bei Erkennung: bei new_pattern die Skalen mit Streak, bei der Spitze die Gate-Skala mit dem höchsten Score",
    ]

    output_directory = user_output_directory(run_directory)
    build_k3_plot(gate_open, output_directory, target_rate_pct=target_rate_pct)

    write_result_report(
        output_directory,
        title=f"K3 Referenzfenster und Schwellen der Anomalieerkennung, Lauf {run_directory.name}",
        setup=build_setup(run_config, k3_config, variant, loop_thresholds),
        tables=tables,
        notes=notes,
        images=["k3_gate_open.png"],
        decimals=DECIMALS,
        appendix=appendix,
    )

    print(f"Result written to {output_directory / 'ergebnis.md'}")


if __name__ == "__main__":
    main()
