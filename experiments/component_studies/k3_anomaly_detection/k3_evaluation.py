from pathlib import Path

import pandas as pd

from src.common.timestamps import local_day_index
from src.numerical_analysis.daily_analysis import DAILY_ANOMALY_SCALES

SCALE_SCORE_COLUMNS = tuple(f"{scale}_score" for scale in DAILY_ANOMALY_SCALES)

RESULT_COLUMNS = [
    "mode", "kind", "cutover_date", "variant", "decision_time", "days_since_cutover",
    "anomaly_level", "anomaly_score", *SCALE_SCORE_COLUMNS, "classification", "alarm", "new_pattern", "reference_reset", "mae_w",
]


def read_scenario_results(
    run_directory: Path,
    *,
    mode: str,
    kind: str,
    cutover_date: str,
    local_timezone: str,
) -> pd.DataFrame:
    # summary hat jeden Tag, anomaly.csv fehlt an Tagen ohne Analyse (z.B. direkt nach einem Reset)
    summary = pd.read_csv(run_directory / "comparison_summary.csv")[["decision_time", "config", "classification", "reference_reset", "mae_w"]]
    anomaly = pd.concat([pd.read_csv(file) for file in sorted(run_directory.glob("*/anomaly.csv"))], ignore_index=True)
    results = summary.merge(anomaly, on=["decision_time", "config"], how="left").rename(columns={"config": "variant"})

    decision_time = pd.DatetimeIndex(pd.to_datetime(results["decision_time"], utc=True))
    target_day = local_day_index(decision_time - pd.Timedelta(hours=1), local_timezone).tz_localize(None)

    results["mode"] = mode
    results["kind"] = kind
    results["cutover_date"] = cutover_date
    results["days_since_cutover"] = (target_day - pd.Timestamp(cutover_date)).days
    results["alarm"] = results["anomaly_level"].notna() & results["anomaly_level"].ne("normal")
    results["new_pattern"] = results["classification"].eq("new_pattern")

    return results[RESULT_COLUMNS]


def summarize_control(results: pd.DataFrame) -> pd.DataFrame:
    """Fehlalarme und Score-Verfügbarkeit ohne Ereignis, getrennt vor/nach Cutover"""
    control = results.loc[results["kind"].eq("control")].copy()
    control["phase"] = control["days_since_cutover"].ge(0).map({False: "before", True: "after"})

    score_columns = ["anomaly_score", *SCALE_SCORE_COLUMNS]
    control[score_columns] = control[score_columns].notna()

    return control.groupby(["variant", "cutover_date", "phase"]).agg(
        days=("alarm", "size"),
        alarm_rate=("alarm", "mean"),
        new_pattern_days=("new_pattern", "sum"),
        **{f"{column}_available_share": (column, "mean") for column in score_columns},
    ).reset_index()


def pair_with_control(results: pd.DataFrame) -> pd.DataFrame:
    """Tageweise Differenz step minus control, geht nur ohne Adaption, sonst laufen die Reihen auseinander"""
    keys = ["variant", "cutover_date", "days_since_cutover"]
    columns = [*keys, "anomaly_score", *SCALE_SCORE_COLUMNS, "alarm", "new_pattern"]

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


def summarize_event_response(paired: pd.DataFrame, unusual_threshold: float) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    after_cutover = paired.loc[paired["days_since_cutover"].ge(0)]

    for (variant, cutover_date), group in after_cutover.groupby(["variant", "cutover_date"]):
        above_threshold = group.loc[group["score_shift"].ge(unusual_threshold), "days_since_cutover"]

        rows.append(
            {
                "variant": variant,
                "cutover_date": cutover_date,
                "days_after_cutover": len(group),
                "excess_alarm_rate": group["alarm"].mean() - group["alarm_control"].mean(),
                "first_event_alarm_day": group.loc[group["event_alarm"], "days_since_cutover"].min(),
                "first_event_new_pattern_day": group.loc[group["event_new_pattern"], "days_since_cutover"].min(),
                "peak_score_shift": group["score_shift"].max(),
                # ab dem Tag danach liegt das Ereignis nicht mehr über der Schwelle, NaN = nie darüber
                "last_day_shift_above_threshold": above_threshold.max(),
            }
        )

    return pd.DataFrame(rows).sort_values(["variant", "cutover_date"]).reset_index(drop=True)


def summarize_closed_loop(results: pd.DataFrame) -> pd.DataFrame:
    keys = ["variant", "cutover_date"]
    after_cutover = results.loc[results["days_since_cutover"].ge(0)]

    loop_control = results.loc[results["mode"].eq("adaption") & results["kind"].eq("control")].groupby(keys)
    loop_step = after_cutover.loc[after_cutover["mode"].eq("adaption") & after_cutover["kind"].eq("step")]
    step_resets = loop_step.loc[loop_step["reference_reset"]]

    summary = pd.DataFrame(
        {
            "control_resets": loop_control["reference_reset"].sum(),
            "control_alarm_rate": loop_control["alarm"].mean(),
            "step_resets_after_cutover": loop_step.groupby(keys)["reference_reset"].sum(),
            "step_first_reset_day": step_resets.groupby(keys)["days_since_cutover"].min(),
        }
    )

    # MAE nach Cutover, jeweils neben denselben Lauf ohne Adaption gestellt
    mae = after_cutover.pivot_table(index=keys, columns=["kind", "mode"], values="mae_w", aggfunc="mean")
    for kind in ("control", "step"):
        summary[f"{kind}_mae_isolated_w"] = mae[(kind, "isolated")]
        summary[f"{kind}_mae_adaption_w"] = mae[(kind, "adaption")]

    return summary.reset_index()


def score_shift_by_week(paired: pd.DataFrame) -> pd.DataFrame:
    weekly = paired.assign(week_since_cutover=paired["days_since_cutover"] // 7)

    return weekly.groupby(["variant", "week_since_cutover"], as_index=False)[["score_shift"]].mean()


def with_mean_over_cutovers(summary: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    means = summary.drop(columns="cutover_date").groupby(keys, as_index=False).mean(numeric_only=True)
    means["cutover_date"] = "mean"

    return pd.concat([summary, means], ignore_index=True)