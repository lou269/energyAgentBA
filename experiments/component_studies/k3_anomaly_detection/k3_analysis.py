# conda activate forecasting-env
# python -m experiments.component_studies.k3_anomaly_detection.k3_analysis [run_directory]

import sys
from pathlib import Path

import pandas as pd

from docs.plots.plot_k3_reference_window import build_k3_plot
from experiments.component_studies.k3_anomaly_detection.k3_calibration import CALIBRATION_FILES, threshold_columns
from experiments.component_studies.k3_anomaly_detection.k3_config import (
    K3_MODE_LABELS,
    REFERENCE_WINDOW_LABELS,
    REFERENCE_WINDOWS,
    K3CalibrationConfig,
)
from experiments.component_studies.k3_anomaly_detection.k3_evaluation import (
    pair_with_control,
    summarize_closed_loop,
    summarize_control,
    summarize_event_response,
)
from experiments.proposal_experiments.e_config import NOTIFICATION_CLASSIFICATIONS, NOTIFICATION_PERIOD_DAYS
from experiments.shared_analysis import ALL_DAYS, SPREAD_LABELS, count_notifications, spread_over_repeats
from src.common.result_report import format_commit, format_number, key_figures_table, write_result_report
from src.config.config_forecasting import NumericalAnalysisConfig
from src.config.project_config import ProjectConfig
from src.pipeline.io import RAW_SUBDIR, read_raw_json, resolve_run_directory, user_output_directory

KEY_ORDER = {"variant": list(REFERENCE_WINDOW_LABELS), "mode": list(K3_MODE_LABELS)}
KEY_VALUE_LABELS = {"variant": REFERENCE_WINDOW_LABELS, "mode": K3_MODE_LABELS}
KEY_HEADERS = {"variant": "Referenzfenster", "mode": "Modus"}

QUIET_DAY_HEADERS = {
    "gate_open_isolated_pct": "Gate offen ohne Reset [%]",
    "gate_open_adaption_pct": "Gate offen mit Reset [%]",
    "alarm_adaption_pct": "davon Einzeltag mit Reset [%]",
    "control_resets": "Resets je Fenster",
    "mae_isolated_w": "MAE ohne Reset [W]",
    "mae_adaption_w": "MAE mit Reset [W]",
}
DETECTION_HEADERS = {"mean": "Mittel erkannter", "detected": "erkannt", "step_mae_w": "MAE nach Cutover [W]"}
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


def _production_variant(numerical_analysis_config: NumericalAnalysisConfig) -> str:
    # das Referenzfenster, mit dem die Pipeline gerade läuft
    for variant, window in REFERENCE_WINDOWS.items():
        if all(getattr(numerical_analysis_config, key) == value for key, value in window.items()):
            return variant

    raise ValueError("NumericalAnalysisConfig matches none of the K3 reference windows.")


def _labeled(table: pd.DataFrame, headers: dict[str, str]) -> pd.DataFrame:
    keys = [key for key in KEY_ORDER if key in table]
    labeled = table.copy()

    for key in keys:
        labeled[key] = pd.Categorical(labeled[key], KEY_ORDER[key])
    labeled = labeled.sort_values(keys, kind="stable")

    for key in keys:
        labeled[key] = labeled[key].map(KEY_VALUE_LABELS[key])

    return labeled.rename(columns={**KEY_HEADERS, **headers})


def summarize_gate_open(control_summary: pd.DataFrame) -> pd.DataFrame:
    overall = control_summary.loc[control_summary["phase"].eq(ALL_DAYS)]
    rates = overall.groupby(["variant", "mode"], as_index=False)[["gate_open_rate", "alarm_rate"]].mean()

    return rates.assign(gate_open_pct=rates["gate_open_rate"] * 100, alarm_pct=rates["alarm_rate"] * 100)


def summarize_quiet_days(gate_open: pd.DataFrame, closed_loop: pd.DataFrame) -> pd.DataFrame:
    rates = gate_open.set_index(["variant", "mode"])
    loop = closed_loop.groupby("variant")[["control_resets", "control_mae_isolated_w", "control_mae_adaption_w"]].mean()

    return pd.DataFrame(
        {
            "gate_open_isolated_pct": rates.xs("isolated", level="mode")["gate_open_pct"],
            "gate_open_adaption_pct": rates.xs("adaption", level="mode")["gate_open_pct"],
            "alarm_adaption_pct": rates.xs("adaption", level="mode")["alarm_pct"],
            "control_resets": loop["control_resets"],
            "mae_isolated_w": loop["control_mae_isolated_w"],
            "mae_adaption_w": loop["control_mae_adaption_w"],
        }
    ).rename_axis("variant").reset_index()


def summarize_detection(event_response: pd.DataFrame, closed_loop: pd.DataFrame) -> pd.DataFrame:
    # ohne Reset: erstes new_pattern, das der Kontrolllauf am selben Tag nicht hat, mit Reset: erster Reset nach dem Cutover
    days = pd.concat(
        [
            event_response.assign(mode="isolated", day=event_response["first_event_new_pattern_day"]),
            closed_loop.assign(mode="adaption", day=closed_loop["step_first_reset_day"]),
        ],
        ignore_index=True,
    )
    keys = ["variant", "mode"]
    table = spread_over_repeats(days, keys, "day")
    cutovers = sorted(days["cutover_date"].unique())
    table[cutovers] = table[cutovers].astype("Int64")

    detected = days.groupby(keys, as_index=False).agg(detected=("day", lambda day: f"{day.notna().sum()}/{len(day)}"))
    step_mae = (
        closed_loop.groupby("variant", as_index=False)[["step_mae_isolated_w", "step_mae_adaption_w"]].mean()
        .rename(columns={"step_mae_isolated_w": "isolated", "step_mae_adaption_w": "adaption"})
        .melt(id_vars="variant", var_name="mode", value_name="step_mae_w")
    )

    return table.merge(detected, on=keys).merge(step_mae, on=keys)


def summarize_notifications(results: pd.DataFrame, control_summary: pd.DataFrame) -> pd.DataFrame:
    keys = ["variant", "mode"]
    counts = count_notifications(
        results, [*keys, "kind"], notification_classes=NOTIFICATION_CLASSIFICATIONS, period_days=NOTIFICATION_PERIOD_DAYS,
    ).pivot(index=keys, columns="kind")
    overall = control_summary.loc[control_summary["phase"].eq(ALL_DAYS)]

    return pd.DataFrame(
        {
            "notifications_control": counts[("notifications_per_period", "control")],
            "unknown_control": counts[("unknown_per_period", "control")],
            "notifications_step": counts[("notifications_per_period", "step")],
            "unknown_step": counts[("unknown_per_period", "step")],
            "extra_notifications": counts[("notification_days", "step")] - counts[("notification_days", "control")],
            "control_new_pattern_days": overall.groupby(keys)["new_pattern_days"].mean(),
        }
    ).reset_index()


def read_calibration(run_directory: Path) -> dict[str, pd.DataFrame] | None:
    # die Kalibrierung ist ein eigener, langsamer Schritt (k3_calibration_runner), ohne ihn fehlt nur dieser Abschnitt
    paths = {name: run_directory / RAW_SUBDIR / f"{file}.csv" for name, file in CALIBRATION_FILES.items() if name != "grid"}
    if not paths["operating_points"].exists():
        return None

    return {name: pd.read_csv(path, dtype={"cutover_date": str}) for name, path in paths.items()}


def _threshold_text(table: pd.DataFrame, slow_scales: tuple[str, ...]) -> pd.DataFrame:
    # Schwellen wie 1,25 würden mit einer Nachkommastelle zu 1,2
    columns = threshold_columns(slow_scales)
    return table.assign(**{column: table[column].map(lambda value: f"{value:g}".replace(".", ",")) for column in columns})


def summarize_calibration(operating_points: pd.DataFrame, *, slow_scales: tuple[str, ...], cutover_count: int) -> pd.DataFrame:
    table = operating_points.assign(
        alarm_pct=operating_points["alarm_rate"] * 100,
        detected=operating_points["detected"].astype(str) + f"/{cutover_count}",
    )
    columns = ["rank", "variant", *threshold_columns(slow_scales), "alarm_pct", "false_new_pattern", "detected", "detection_day"]

    return _threshold_text(table[columns], slow_scales)


def summarize_calibration_by_cutover(by_cutover: pd.DataFrame, slow_scales: tuple[str, ...]) -> pd.DataFrame:
    table = by_cutover.assign(
        alarm_pct=by_cutover["alarm_rate"] * 100,
        first_event_new_pattern_day=by_cutover["first_event_new_pattern_day"].astype("Int64"),
    )
    columns = ["variant", "rank", *threshold_columns(slow_scales), "cutover_date", "alarm_pct", "false_new_pattern", "first_event_new_pattern_day"]

    return _threshold_text(table[columns], slow_scales)


def summarize_leave_one_out(loco: pd.DataFrame, slow_scales: tuple[str, ...]) -> pd.DataFrame:
    # je zurückgehaltenem Cutover das Referenzfenster, das auf den anderen drei gewonnen hat, und wie es sich auf dem vierten schlägt
    winners = loco.loc[loco["rank"].eq(1)]
    table = winners.assign(
        alarm_held_out_pct=winners["alarm_rate_held_out"] * 100,
        first_event_new_pattern_day=winners["first_event_new_pattern_day"].astype("Int64"),
    )
    columns = [
        "cutover_date", "variant", *threshold_columns(slow_scales),
        "alarm_held_out_pct", "false_new_pattern_held_out", "first_event_new_pattern_day",
    ]

    return _threshold_text(table[columns], slow_scales)


def _calibration_headers(slow_scales: tuple[str, ...]) -> dict[str, str]:
    return {**CALIBRATION_HEADERS, **{f"{scale}_threshold": f"Streak-Schwelle {scale}" for scale in slow_scales}}


def by_mode(table: pd.DataFrame, value: str) -> pd.DataFrame:
    """Zeilen = Referenzfenster, Spalten = Modus, so erwartet es der K3-Plot"""
    wide = table.pivot(index="variant", columns="mode", values=value)
    wide = wide.reindex([variant for variant in KEY_ORDER["variant"] if variant in wide.index])[KEY_ORDER["mode"]]

    return wide.rename(index=REFERENCE_WINDOW_LABELS)


def build_setup(run_config: dict, production_variant: str) -> dict[str, str]:
    k3_config = run_config["k3_config"]

    return {
        "Cutover": ", ".join(k3_config["cutover_dates"]),
        "Zeitraum je Cutover": (
            f"Kaltstart, {k3_config['monitoring_before_cutover_days']} Tage Überwachung vor dem Cutover, {k3_config['margin_after_days']} Tage danach"
        ),
        "Ereignis": f"Dauerlast +{format_number(k3_config['step_injection_w'], 0)} W ab Cutover, gepaart mit unverändertem Kontrolllauf",
        "Modi": "ohne Reset = nur Detektor, mit Reset = Kreislauf mit Regel wie SYS2",
        "Produktiv-Referenzfenster": REFERENCE_WINDOW_LABELS[production_variant],
        "Commit": format_commit(run_config["code_version"]),
    }


def build_key_figures(
    quiet_days: pd.DataFrame,
    detection: pd.DataFrame,
    notifications: pd.DataFrame,
    calibration: dict[str, pd.DataFrame] | None,
    *,
    variant: str,
    target_rate_pct: float,
    decimals: int,
) -> pd.DataFrame:
    label = REFERENCE_WINDOW_LABELS[variant]
    quiet = quiet_days.set_index("variant").loc[variant]
    detected = detection.set_index(["variant", "mode"])["detected"]
    extra = notifications.set_index(["variant", "mode"])["extra_notifications"]

    rows = [
        (
            f"{label}: Gate offen ohne Ereignis, mit Reset [%]", quiet["gate_open_adaption_pct"],
            f"ohne Reset {format_number(quiet['gate_open_isolated_pct'], decimals)} %, Ziel {format_number(target_rate_pct, 0)} %",
        ),
        (f"{label}: Stufe erkannt mit Reset", detected[(variant, "adaption")], f"ohne Reset {detected[(variant, 'isolated')]}"),
        (f"{label}: zusätzliche Meldungen durch die Stufe, mit Reset", extra[(variant, "adaption")], f"ohne Reset {extra[(variant, 'isolated')]}"),
    ]

    if calibration is not None:
        best = calibration["operating_points"].sort_values("rank").iloc[0]
        loco_winners = calibration["loco"].loc[calibration["loco"]["rank"].eq(1), "variant"]
        rows.append(
            (
                f"Kalibrierung: bestes Referenzfenster bei höchstens {format_number(target_rate_pct, 0)} % Einzeltag-Alarmen",
                REFERENCE_WINDOW_LABELS[best["variant"]],
                f"Gate-Schwelle {best['gate_threshold']:g}, im Leave-one-out {loco_winners.eq(best['variant']).sum()}/{len(loco_winners)} Durchgänge vorn".replace(".", ","),
            )
        )

    return key_figures_table(rows)


def main() -> None:
    project_config = ProjectConfig()
    decimals = project_config.result_decimals
    calibration_config = K3CalibrationConfig()
    target_rate_pct = calibration_config.target_alarm_rate * 100
    production_variant = _production_variant(NumericalAnalysisConfig())

    run_directory = resolve_run_directory(project_config.k3_output_dir, "k3", sys.argv[1] if len(sys.argv) > 1 else None)
    run_config = read_raw_json(run_directory, "run_config")
    results = pd.read_csv(run_directory / RAW_SUBDIR / "k3_results.csv", dtype={"cutover_date": str})

    calibration = read_calibration(run_directory)
    slow_scales = calibration_config.slow_scales

    control_summary = summarize_control(results)
    closed_loop = summarize_closed_loop(results)
    event_response = summarize_event_response(
        pair_with_control(results.loc[results["mode"].eq("isolated")]), NumericalAnalysisConfig().unusual_threshold,
    )

    gate_open = summarize_gate_open(control_summary)
    quiet_days = summarize_quiet_days(gate_open, closed_loop)
    detection = summarize_detection(event_response, closed_loop)
    notifications = summarize_notifications(results, control_summary)

    tables = {
        "key_figures": (
            "Kennzahlen",
            build_key_figures(
                quiet_days, detection, notifications, calibration,
                variant=production_variant, target_rate_pct=target_rate_pct, decimals=decimals,
            ),
        ),
        "result_quiet_days": (
            "Ohne Ereignis: Kontrolllauf über das ganze Fenster, Mittel über Cutover", _labeled(quiet_days, QUIET_DAY_HEADERS),
        ),
        "result_detection": (
            "Erkennung der Stufe, Tag seit Cutover je Cutover", _labeled(detection, {**SPREAD_LABELS, **DETECTION_HEADERS}),
        ),
        "result_notifications": ("Meldungen an den Nutzer", _labeled(notifications, NOTIFICATION_HEADERS)),
    }
    appendix = {}
    notes = [
        "Tag seit Cutover zählt den ausgewerteten Tag, nicht den prognostizierten (anders als in K5)",
        f"Meldung = Tag mit {', '.join(NOTIFICATION_CLASSIFICATIONS)}, in SYS3 jeweils ein LLM-Aufruf. unknown getrennt, dort reicht die Referenz nicht",
        "mit Reset: ein Reset am Cutover-Tag kann auch im Kontrolllauf auftreten und ist dann kein Treffer, Kontrolllauf-Resets stehen in der ersten Tabelle",
    ]

    if calibration is None:
        notes.append("Kalibrierung für diesen Lauf nicht gerechnet, dafür vorher k3_calibration_runner ausführen")
    else:
        headers = _calibration_headers(slow_scales)
        cutover_count = results["cutover_date"].nunique()
        tables["result_calibration"] = (
            "Kalibrierung: Arbeitspunkt je Referenzfenster bei gleicher Fehlalarmrate, ohne Reset",
            _labeled(summarize_calibration(calibration["operating_points"], slow_scales=slow_scales, cutover_count=cutover_count), headers),
        )
        tables["result_calibration_loco"] = (
            "Kalibrierung: Leave-one-cutover-out, auf den übrigen Cutovern gewählt und auf dem zurückgehaltenen geprüft",
            _labeled(summarize_leave_one_out(calibration["loco"], slow_scales), {**headers, **LOCO_HEADERS}),
        )
        appendix["result_calibration_by_cutover"] = (
            "Kalibrierung: Arbeitspunkte je Cutover",
            _labeled(summarize_calibration_by_cutover(calibration["by_cutover"], slow_scales), headers),
        )
        notes.append(
            f"Kalibrierung: je Referenzfenster die niedrigste Gate-Schwelle mit höchstens {format_number(target_rate_pct, 0)} % Einzeltag-Alarmen "
            f"im Kontrolllauf, dann die Streak-Schwellen mit höchstens {format_number(calibration_config.max_false_new_pattern, 0)} "
            "falschen new_pattern je Fenster und möglichst vielen, frühen Erkennungen"
        )

    output_directory = user_output_directory(run_directory)
    build_k3_plot(
        by_mode(gate_open, "gate_open_pct"),
        by_mode(notifications, "extra_notifications"),
        output_directory,
        mode_labels=K3_MODE_LABELS,
        target_rate_pct=target_rate_pct,
    )

    write_result_report(
        output_directory,
        title=f"K3 Referenzfenster der Anomalieerkennung, Lauf {run_directory.name}",
        setup=build_setup(run_config, production_variant),
        tables=tables,
        notes=notes,
        images=["k3_closed_loop.png"],
        decimals=decimals,
        appendix=appendix,
    )

    print(f"Result written to {output_directory / 'ergebnis.md'}")


if __name__ == "__main__":
    main()
