from dataclasses import dataclass

import pandas as pd

from experiments.common.evaluation import (
    ALL_DAYS,
    FIRST_ANALYZED_DAY,
    add_overall_rows,
    count_notifications,
    days_since_date,
    spread_over_repeats,
)
from experiments.common.standard_config import (
    NOTIFICATION_CLASSIFICATIONS,
    NOTIFICATION_PERIOD_DAYS,
)
from src.config.config_forecasting import NumericalAnalysisConfig
from src.numerical_analysis.daily_analysis import DAILY_ANOMALY_SCALES

SCALE_SCORE_COLUMNS = [f"{scale}_score" for scale in DAILY_ANOMALY_SCALES]

RESULT_COLUMNS = (
    [
        "mode",
        "kind",
        "cutover_date",
        "variant",
        "decision_time",
        "anomaly_level",
        "anomaly_score",
    ]
    + SCALE_SCORE_COLUMNS
    + [
        "sustained_drift",
        "classification",
        "alarm",
        "gate_open",
        "new_pattern",
        "reference_reset",
        "mae_w",
    ]
)


def read_scenario_results(
    summary: pd.DataFrame,
    anomaly: pd.DataFrame,
    *,
    mode: str,
    kind: str,
    cutover_date: str,
) -> pd.DataFrame:
    # summary hat jeden Tag, anomaly.csv fehlt an Tagen ohne Analyse (z.B. direkt nach einem Reset)
    summary = summary[
        ["decision_time", "config", "classification", "reference_reset", "mae_w"]
    ]
    results = summary.merge(anomaly, on=["decision_time", "config"], how="left").rename(
        columns={"config": "variant"}
    )

    results["mode"] = mode
    results["kind"] = kind
    results["cutover_date"] = cutover_date
    results["alarm"] = results["anomaly_level"].notna() & results["anomaly_level"].ne(
        "normal"
    )
    results["gate_open"] = results["alarm"] | results["sustained_drift"].eq(True)
    results["new_pattern"] = results["classification"].eq("new_pattern")

    return results[RESULT_COLUMNS]


def add_days_since_cutover(results: pd.DataFrame) -> pd.DataFrame:
    # Entscheidungstag wie days_since_event, hier mit eigenem Cutover je Zeile
    return results.assign(
        days_since_cutover=days_since_date(
            results["decision_time"], results["cutover_date"]
        )
    )


def summarize_control(results: pd.DataFrame) -> pd.DataFrame:
    """Fehlalarme und Score-Verfügbarkeit ohne Ereignis, vor und ab Cutover und über das ganze Fenster"""
    control = results.loc[results["kind"].eq("control")].copy()
    score_columns = ["anomaly_score"] + SCALE_SCORE_COLUMNS
    control[score_columns] = control[score_columns].notna()

    control["phase"] = (
        control["days_since_cutover"]
        .ge(FIRST_ANALYZED_DAY)
        .map({False: "before_cutover", True: "after_cutover"})
    )
    grouped = add_overall_rows(control, "phase", ALL_DAYS).groupby(
        ["mode", "variant", "cutover_date", "phase"]
    )

    summary = grouped.agg(
        days=("alarm", "size"),
        alarm_rate=("alarm", "mean"),
        gate_open_rate=("gate_open", "mean"),
        new_pattern_days=("new_pattern", "sum"),
    )
    available_share = grouped[score_columns].mean().add_suffix("_available_share")

    return summary.join(available_share).reset_index()


def pair_with_control(results: pd.DataFrame) -> pd.DataFrame:
    """Tageweise Differenz step minus control, geht nur ohne Adaption, sonst laufen die Reihen auseinander"""
    keys = ["variant", "cutover_date", "days_since_cutover"]
    columns = keys + ["anomaly_score"] + SCALE_SCORE_COLUMNS + ["alarm", "new_pattern"]
    results = results.loc[results["mode"].eq("isolated")]

    control = results.loc[results["kind"].eq("control"), columns]
    step = results.loc[results["kind"].eq("step"), columns]

    paired = step.merge(control, on=keys, suffixes=("", "_control"))
    paired["score_shift"] = paired["anomaly_score"] - paired["anomaly_score_control"]
    for column in SCALE_SCORE_COLUMNS:
        paired[f"{column}_shift"] = paired[column] - paired[f"{column}_control"]

    # Alarm bzw. new_pattern, den es ohne Ereignis an diesem Tag nicht gegeben hätte
    paired["event_alarm"] = paired["alarm"] & ~paired["alarm_control"]
    paired["event_new_pattern"] = paired["new_pattern"] & ~paired["new_pattern_control"]

    return paired


def summarize_event_response(
    paired: pd.DataFrame, unusual_threshold: float
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    after_cutover = paired.loc[paired["days_since_cutover"].ge(FIRST_ANALYZED_DAY)]

    for (variant, cutover_date), group in after_cutover.groupby(
        ["variant", "cutover_date"]
    ):
        above_threshold = group.loc[
            group["score_shift"].ge(unusual_threshold), "days_since_cutover"
        ]

        rows.append(
            {
                "variant": variant,
                "cutover_date": cutover_date,
                "days_after_cutover": len(group),
                "excess_alarm_rate": group["alarm"].mean()
                - group["alarm_control"].mean(),
                "first_event_alarm_day": group.loc[
                    group["event_alarm"], "days_since_cutover"
                ].min(),
                "first_event_new_pattern_day": group.loc[
                    group["event_new_pattern"], "days_since_cutover"
                ].min(),
                "peak_score_shift": group["score_shift"].max(),
                # ab dem Tag danach liegt das Ereignis nicht mehr über der Schwelle, NaN = nie darüber
                "last_day_shift_above_threshold": above_threshold.max(),
            }
        )

    return (
        pd.DataFrame(rows)
        .sort_values(["variant", "cutover_date"])
        .reset_index(drop=True)
    )


def summarize_closed_loop(results: pd.DataFrame) -> pd.DataFrame:
    keys = ["variant", "cutover_date"]
    after_cutover = results.loc[results["days_since_cutover"].ge(FIRST_ANALYZED_DAY)]

    loop_control = results.loc[
        results["mode"].eq("adaption") & results["kind"].eq("control")
    ].groupby(keys)
    loop_step = after_cutover.loc[
        after_cutover["mode"].eq("adaption") & after_cutover["kind"].eq("step")
    ]
    step_resets = loop_step.loc[loop_step["reference_reset"]]

    summary = pd.DataFrame(
        {
            "control_resets": loop_control["reference_reset"].sum(),
            "step_resets_after_cutover": loop_step.groupby(keys)[
                "reference_reset"
            ].sum(),
            "step_first_reset_day": step_resets.groupby(keys)[
                "days_since_cutover"
            ].min(),
        }
    )

    # MAE nach Cutover, jeweils neben denselben Lauf ohne Adaption gestellt
    mae = after_cutover.pivot_table(
        index=keys, columns=["kind", "mode"], values="mae_w", aggfunc="mean"
    )
    for kind in ("control", "step"):
        summary[f"{kind}_mae_isolated_w"] = mae[(kind, "isolated")]
        summary[f"{kind}_mae_adaption_w"] = mae[(kind, "adaption")]

    return summary.reset_index()


def summarize_gate_open(control_summary: pd.DataFrame) -> pd.DataFrame:
    overall = control_summary.loc[control_summary["phase"].eq(ALL_DAYS)]
    rates = overall.groupby(["variant", "mode"], as_index=False)[
        ["gate_open_rate", "alarm_rate"]
    ].mean()

    return rates.assign(
        gate_open_pct=rates["gate_open_rate"] * 100, alarm_pct=rates["alarm_rate"] * 100
    )


def summarize_quiet_days(
    gate_open: pd.DataFrame, closed_loop: pd.DataFrame
) -> pd.DataFrame:
    rates = gate_open.set_index(["variant", "mode"])
    loop = closed_loop.groupby("variant")[
        ["control_resets", "control_mae_isolated_w", "control_mae_adaption_w"]
    ].mean()

    return (
        pd.DataFrame(
            {
                "gate_open_isolated_pct": rates.xs("isolated", level="mode")[
                    "gate_open_pct"
                ],
                "gate_open_adaption_pct": rates.xs("adaption", level="mode")[
                    "gate_open_pct"
                ],
                "alarm_adaption_pct": rates.xs("adaption", level="mode")["alarm_pct"],
                "control_resets": loop["control_resets"],
                "mae_isolated_w": loop["control_mae_isolated_w"],
                "mae_adaption_w": loop["control_mae_adaption_w"],
            }
        )
        .rename_axis("variant")
        .reset_index()
    )


def summarize_detection(
    event_response: pd.DataFrame, closed_loop: pd.DataFrame
) -> pd.DataFrame:
    # ohne Reset: erstes new_pattern, das der Kontrolllauf am selben Tag nicht hat, mit Reset: erster Reset nach dem Cutover
    days = pd.concat(
        [
            event_response.assign(
                mode="isolated", day=event_response["first_event_new_pattern_day"]
            ),
            closed_loop.assign(
                mode="adaption", day=closed_loop["step_first_reset_day"]
            ),
        ],
        ignore_index=True,
    )
    keys = ["variant", "mode"]
    table = spread_over_repeats(days, keys, "day")
    cutovers = sorted(days["cutover_date"].unique())
    table[cutovers] = table[cutovers].astype("Int64")

    detected = days.groupby(keys, as_index=False).agg(
        detected=("day", lambda day: f"{day.notna().sum()}/{len(day)}")
    )
    step_mae = (
        closed_loop.groupby("variant", as_index=False)[
            ["step_mae_isolated_w", "step_mae_adaption_w"]
        ]
        .mean()
        .rename(
            columns={
                "step_mae_isolated_w": "isolated",
                "step_mae_adaption_w": "adaption",
            }
        )
        .melt(id_vars="variant", var_name="mode", value_name="step_mae_w")
    )

    return table.merge(detected, on=keys).merge(step_mae, on=keys)


def summarize_notifications(
    results: pd.DataFrame, control_summary: pd.DataFrame
) -> pd.DataFrame:
    keys = ["variant", "mode"]
    counts = count_notifications(
        results,
        keys + ["kind"],
        notification_classes=NOTIFICATION_CLASSIFICATIONS,
        period_days=NOTIFICATION_PERIOD_DAYS,
    ).pivot(index=keys, columns="kind")
    overall = control_summary.loc[control_summary["phase"].eq(ALL_DAYS)]

    return pd.DataFrame(
        {
            "notifications_control": counts[("notifications_per_period", "control")],
            "unknown_control": counts[("unknown_per_period", "control")],
            "notifications_step": counts[("notifications_per_period", "step")],
            "unknown_step": counts[("unknown_per_period", "step")],
            "extra_notifications": counts[("notification_days", "step")]
            - counts[("notification_days", "control")],
            "control_new_pattern_days": overall.groupby(keys)[
                "new_pattern_days"
            ].mean(),
        }
    ).reset_index()


def production_variant(
    numerical_analysis_config: NumericalAnalysisConfig,
    reference_windows: dict[str, tuple[int | None, int | None]],
) -> str:
    # das Referenzfenster, mit dem die Pipeline gerade läuft
    window = (
        numerical_analysis_config.max_reference_window_growth_days,
        numerical_analysis_config.reference_window_rolling_days,
    )
    for variant, reference_window in reference_windows.items():
        if reference_window == window:
            return variant

    raise ValueError(
        "NumericalAnalysisConfig matches none of the K3 reference windows."
    )


@dataclass(frozen=True)
class CalibrationSummary:
    operating_points: pd.DataFrame
    by_cutover: pd.DataFrame
    loco: pd.DataFrame
    best_variant: str
    best_gate_threshold: float
    loco_wins: int
    loco_folds: int


def summarize_calibration(
    calibration: dict[str, pd.DataFrame], cutover_count: int
) -> CalibrationSummary:
    """Arbeitspunkte, je Cutover und Leave-one-out für den Report, dazu das beste Referenzfenster"""
    operating_points = calibration["operating_points"].sort_values("rank")
    by_cutover = calibration["by_cutover"]
    # je zurückgehaltenem Cutover das Referenzfenster, das auf den anderen drei gewonnen hat, und wie es sich auf dem vierten schlägt
    loco_winners = calibration["loco"].loc[calibration["loco"]["rank"].eq(1)]
    best = operating_points.iloc[0]

    return CalibrationSummary(
        operating_points=operating_points.assign(
            alarm_pct=operating_points["alarm_rate"] * 100,
            detected=operating_points["detected"].astype(str) + f"/{cutover_count}",
        ),
        by_cutover=by_cutover.assign(
            alarm_pct=by_cutover["alarm_rate"] * 100,
            first_event_new_pattern_day=by_cutover[
                "first_event_new_pattern_day"
            ].astype("Int64"),
        ),
        loco=loco_winners.assign(
            alarm_held_out_pct=loco_winners["alarm_rate_held_out"] * 100,
            first_event_new_pattern_day=loco_winners[
                "first_event_new_pattern_day"
            ].astype("Int64"),
        ),
        best_variant=best["variant"],
        best_gate_threshold=best["gate_threshold"],
        loco_wins=int(loco_winners["variant"].eq(best["variant"]).sum()),
        loco_folds=len(loco_winners),
    )
