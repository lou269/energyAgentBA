# conda activate forecasting-env
# python -m experiments.k3_detection.k3_report [run_directory]

from pathlib import Path

import pandas as pd

from docs.plots.plot_k3_reference_window import build_k3_plot
from experiments.common.report import (
    format_commit,
    format_number,
    key_figures_table,
    relabel,
    write_result_report,
)
from experiments.common.standard_config import (
    DECIMALS,
    NOTIFICATION_CLASSIFICATIONS,
    NOTIFICATION_PERIOD_DAYS,
    PROJECT_CONFIG,
)
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
    CalibrationSummary,
    add_days_since_cutover,
    pair_with_control,
    production_variant,
    summarize_calibration,
    summarize_closed_loop,
    summarize_control,
    summarize_detection,
    summarize_event_response,
    summarize_gate_open,
    summarize_notifications,
    summarize_quiet_days,
)
from src.config.config_forecasting import NumericalAnalysisConfig
from src.pipeline.io import (
    RAW_SUBDIR,
    read_raw_json,
    run_directory_from_argv,
    user_output_directory,
)

KEY_ORDER = {"variant": list(REFERENCE_WINDOW_LABELS), "mode": list(MODE_LABELS)}
KEY_VALUE_LABELS = {"variant": REFERENCE_WINDOW_LABELS, "mode": MODE_LABELS}
KEY_HEADERS = {"variant": "Referenzfenster", "mode": "Modus"}

QUIET_DAY_HEADERS = {
    "gate_open_isolated_pct": "Gate offen ohne Reset [%]",
    "gate_open_adaption_pct": "Gate offen mit Reset [%]",
    "alarm_adaption_pct": "davon Einzeltag mit Reset [%]",
    "control_resets": "Resets je Fenster",
    "mae_isolated_w": "MAE ohne Reset [W]",
    "mae_adaption_w": "MAE mit Reset [W]",
}
DETECTION_HEADERS = {
    "mean": "Mittel erkannter",
    "detected": "erkannt",
    "step_mae_w": "MAE nach Cutover [W]",
}
NOTIFICATION_HEADERS = {
    "notifications_control": f"ohne Ereignis je {NOTIFICATION_PERIOD_DAYS} Tage",
    "unknown_control": "unknown ohne Ereignis",
    "notifications_step": f"mit Stufe je {NOTIFICATION_PERIOD_DAYS} Tage",
    "unknown_step": "unknown mit Stufe",
    "extra_notifications": "zusätzlich durch die Stufe, alle Cutover",
    "control_new_pattern_days": "new_pattern ohne Ereignis je Fenster",
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


def read_calibration(run_directory: Path) -> dict[str, pd.DataFrame] | None:
    # Läufe vor dem Umbau haben keine Kalibrierung, dann fehlt nur dieser Abschnitt
    paths = {
        name: run_directory / RAW_SUBDIR / f"{file}.csv"
        for name, file in CALIBRATION_FILES.items()
        if name != "grid"
    }
    if not paths["operating_points"].exists():
        return None

    return {
        name: pd.read_csv(path, dtype={"cutover_date": str})
        for name, path in paths.items()
    }


def build_calibration_table(
    table: pd.DataFrame,
    key_columns: list[str],
    value_columns: list[str],
    slow_scales: tuple[str, ...],
) -> pd.DataFrame:
    # Schwellen wie 1,25 würden mit einer Nachkommastelle zu 1,2
    thresholds = threshold_columns(slow_scales)
    text = table[key_columns + thresholds + value_columns].copy()

    for column in thresholds:
        text[column] = text[column].map(lambda value: f"{value:g}".replace(".", ","))

    return text


def build_setup(run_config: dict, variant: str) -> dict[str, str]:
    standard_config = run_config["standard_config"]

    return {
        "Cutover": ", ".join(standard_config["cutover_dates"]),
        "Zeitraum je Cutover": (
            f"Kaltstart, {standard_config['monitoring_before_cutover_days']} Tage Überwachung vor dem Cutover, {standard_config['margin_after_days']} Tage danach"
        ),
        "Ereignis": f"Dauerlast +{format_number(standard_config['step_injection_w'], 0)} W ab Cutover, gepaart mit unverändertem Kontrolllauf",
        "Modi": "ohne Reset = nur Detektor, mit Reset = Kreislauf mit Regel wie SYS2",
        "Produktiv-Referenzfenster": REFERENCE_WINDOW_LABELS[variant],
        "Commit": format_commit(run_config["code_version"]),
    }


def build_key_figures(
    quiet_days: pd.DataFrame,
    detection: pd.DataFrame,
    notifications: pd.DataFrame,
    calibration: CalibrationSummary | None,
    *,
    variant: str,
    target_rate_pct: float,
) -> pd.DataFrame:
    label = REFERENCE_WINDOW_LABELS[variant]
    quiet = quiet_days.set_index("variant").loc[variant]
    detected = detection.set_index(["variant", "mode"])["detected"]
    extra = notifications.set_index(["variant", "mode"])["extra_notifications"]

    rows = [
        (
            f"{label}: Gate offen ohne Ereignis, mit Reset [%]",
            quiet["gate_open_adaption_pct"],
            f"ohne Reset {format_number(quiet['gate_open_isolated_pct'], DECIMALS)} %, Ziel {format_number(target_rate_pct, 0)} %",
        ),
        (
            f"{label}: Stufe erkannt mit Reset",
            detected[(variant, "adaption")],
            f"ohne Reset {detected[(variant, 'isolated')]}",
        ),
        (
            f"{label}: zusätzliche Meldungen durch die Stufe, mit Reset",
            extra[(variant, "adaption")],
            f"ohne Reset {extra[(variant, 'isolated')]}",
        ),
    ]

    if calibration is not None:
        rows.append(
            (
                f"Kalibrierung: bestes Referenzfenster bei höchstens {format_number(target_rate_pct, 0)} % Einzeltag-Alarmen",
                REFERENCE_WINDOW_LABELS[calibration.best_variant],
                f"Gate-Schwelle {calibration.best_gate_threshold:g}, im Leave-one-out "
                f"{calibration.loco_wins}/{calibration.loco_folds} Durchgänge vorn".replace(
                    ".", ","
                ),
            )
        )

    return key_figures_table(rows)


def main() -> None:
    # Schwellen und Referenzfenster aus der aktuellen Config, ältere Läufe haben sie nicht in run_config
    k3_config = K3Config()
    target_rate_pct = k3_config.target_alarm_rate * 100
    variant = production_variant(NumericalAnalysisConfig(), k3_config.reference_windows)

    run_directory = run_directory_from_argv(PROJECT_CONFIG.k3_output_dir, RUN_PREFIX)
    run_config = read_raw_json(run_directory, "run_config")
    results = add_days_since_cutover(
        pd.read_csv(
            run_directory / RAW_SUBDIR / f"{RESULTS_FILE}.csv",
            dtype={"cutover_date": str},
        )
    )

    calibration_tables = read_calibration(run_directory)
    calibration = None
    if calibration_tables is not None:
        calibration = summarize_calibration(
            calibration_tables, len(run_config["standard_config"]["cutover_dates"])
        )
    slow_scales = k3_config.slow_scales

    control_summary = summarize_control(results)
    closed_loop = summarize_closed_loop(results)
    event_response = summarize_event_response(
        pair_with_control(results),
        NumericalAnalysisConfig().unusual_threshold,
    )

    gate_open = summarize_gate_open(control_summary)
    quiet_days = summarize_quiet_days(gate_open, closed_loop)
    detection = summarize_detection(event_response, closed_loop)
    notifications = summarize_notifications(results, control_summary)

    tables = {
        "key_figures": (
            "Kennzahlen",
            build_key_figures(
                quiet_days,
                detection,
                notifications,
                calibration,
                variant=variant,
                target_rate_pct=target_rate_pct,
            ),
        ),
        "result_quiet_days": (
            "Ohne Ereignis: Kontrolllauf über das ganze Fenster, Mittel über Cutover",
            _labeled(quiet_days, QUIET_DAY_HEADERS),
        ),
        "result_detection": (
            "Erkennung der Stufe, Tag seit Cutover je Cutover",
            _labeled(detection, DETECTION_HEADERS),
        ),
        "result_notifications": (
            "Meldungen an den Nutzer",
            _labeled(notifications, NOTIFICATION_HEADERS),
        ),
    }
    appendix = {}
    notes = [
        "Tag seit Cutover = Entscheidungstag: an Tag n meldet das System, eingeordnet ist dabei Tag n-1. Ab Cutover zählt deshalb erst ab Tag 1",
        f"Meldung = Tag mit {', '.join(NOTIFICATION_CLASSIFICATIONS)}, in SYS3 jeweils ein LLM-Aufruf. unknown getrennt, dort reicht die Referenz nicht",
        "mit Reset: ein Reset am Cutover-Tag kann auch im Kontrolllauf auftreten und ist dann kein Treffer, Kontrolllauf-Resets stehen in der ersten Tabelle",
    ]

    if calibration is None:
        notes.append(
            "Kalibrierung für diesen Lauf nicht gerechnet, sie läuft erst seit dem Umbau am Ende von k3_runner mit"
        )
    else:
        headers = dict(CALIBRATION_HEADERS)
        for scale in slow_scales:
            headers[f"{scale}_threshold"] = f"Streak-Schwelle {scale}"
        loco_headers = dict(headers)
        loco_headers.update(LOCO_HEADERS)

        tables["result_calibration"] = (
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
        )
        tables["result_calibration_loco"] = (
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
        )
        appendix["result_calibration_by_cutover"] = (
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
        notes.append(
            f"Kalibrierung: je Referenzfenster die niedrigste Gate-Schwelle mit höchstens {format_number(target_rate_pct, 0)} % Einzeltag-Alarmen "
            f"im Kontrolllauf, dann die Streak-Schwellen mit höchstens {format_number(k3_config.max_false_new_pattern, 0)} "
            "falschen new_pattern je Fenster und möglichst vielen, frühen Erkennungen"
        )

    output_directory = user_output_directory(run_directory)
    build_k3_plot(
        gate_open,
        notifications,
        output_directory,
        target_rate_pct=target_rate_pct,
    )

    write_result_report(
        output_directory,
        title=f"K3 Referenzfenster der Anomalieerkennung, Lauf {run_directory.name}",
        setup=build_setup(run_config, variant),
        tables=tables,
        notes=notes,
        images=["k3_closed_loop.png"],
        decimals=DECIMALS,
        appendix=appendix,
    )

    print(f"Result written to {output_directory / 'ergebnis.md'}")


if __name__ == "__main__":
    main()
