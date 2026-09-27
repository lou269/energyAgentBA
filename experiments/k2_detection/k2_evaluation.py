from dataclasses import dataclass

import pandas as pd

from experiments.common.evaluation import (
    FIRST_ANALYZED_DAY,
    merge_cycle_days,
    spread_over_repeats,
)
from src.config.config_forecasting import NumericalAnalysisConfig
from src.numerical_analysis.daily_analysis import DAILY_ANOMALY_SCALES

SCALE_SCORE_COLUMNS = [f"{scale}_score" for scale in DAILY_ANOMALY_SCALES]
SCALE_SUSTAINED_COLUMNS = [f"{scale}_sustained" for scale in DAILY_ANOMALY_SCALES]

# gepaart wird je Modus, Referenzfenster und Cutover Tag für Tag
PAIR_KEYS = ["mode", "variant", "cutover_date", "days_since_cutover"]

RESULT_COLUMNS = (
    [
        "mode",
        "kind",
        "cutover_date",
        "variant",
        "decision_time",
        "anomaly_level",
        "anomaly_score",
        "dominant_scale",
    ]
    + SCALE_SCORE_COLUMNS
    + SCALE_SUSTAINED_COLUMNS
    + [
        "sustained_drift",
        "classification",
        "alarm",
        "gate_open",
        "new_pattern",
        "reference_reset",
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
    results = (
        merge_cycle_days(summary, anomaly)
        .rename(columns={"config": "variant"})
        .assign(mode=mode, kind=kind, cutover_date=cutover_date)
    )

    return results[RESULT_COLUMNS]


def summarize_gate_open(results: pd.DataFrame) -> pd.DataFrame:
    """Fehlalarme und Resets ohne Ereignis über das ganze Fenster, erst je Cutover, dann gemittelt"""
    control = results.loc[results["kind"].eq("control")]
    by_cutover = control.groupby(["mode", "variant", "cutover_date"]).agg(
        alarm_rate=("alarm", "mean"),
        gate_open_rate=("gate_open", "mean"),
        resets=("reference_reset", "sum"),
    )
    rates = by_cutover.groupby(["variant", "mode"]).mean().reset_index()

    return rates.assign(
        gate_open_pct=rates["gate_open_rate"] * 100, alarm_pct=rates["alarm_rate"] * 100
    )


def summarize_quiet_days(gate_open: pd.DataFrame) -> pd.DataFrame:
    rates = gate_open.set_index(["variant", "mode"])
    adaption = rates.xs("adaption", level="mode")

    return (
        pd.DataFrame(
            {
                "gate_open_isolated_pct": rates.xs("isolated", level="mode")[
                    "gate_open_pct"
                ],
                "gate_open_adaption_pct": adaption["gate_open_pct"],
                "alarm_adaption_pct": adaption["alarm_pct"],
                "control_resets": adaption["resets"],
            }
        )
        .rename_axis("variant")
        .reset_index()
    )


def summarize_detection(
    paired: pd.DataFrame,
    single_day_kinds: tuple[str, ...],
    *,
    control_reset_tolerance_days: int,
    uncounted_cutovers: tuple[str, ...],
) -> pd.DataFrame:
    """Erkennung je Art im Betrieb mit Reset: dauerhafte Änderungen am ersten eigenen Reset (der Kontrolllauf hat
    control_reset_tolerance_days davor und danach keinen), Einzeltag-Ereignisse am Alarm des Ereignistags.
    Dazu die Skalen, die dabei angeschlagen haben, und bei Einzeltag-Ereignissen die Cutover mit eigenem Reset danach.
    uncounted_cutovers stehen mit in der Tabelle, zählen aber nicht in Mittel, erkannt und Skala
    """
    keys = ["variant", "kind"]
    adaption = paired.loc[paired["mode"].eq("adaption")]
    own_reset = adaption["event_new_pattern"] & ~_near_control_reset(
        adaption, control_reset_tolerance_days
    )
    after_cutover = adaption.assign(own_reset=own_reset).loc[
        adaption["days_since_cutover"].ge(FIRST_ANALYZED_DAY)
    ]
    single_day = after_cutover["kind"].isin(single_day_kinds)

    hit = after_cutover["own_reset"].where(
        ~single_day,
        after_cutover["event_alarm"]
        & after_cutover["days_since_cutover"].eq(FIRST_ANALYZED_DAY),
    )
    first_hits = (
        after_cutover.loc[hit]
        .sort_values("days_since_cutover")
        .groupby(keys + ["cutover_date"])
        .head(1)
    )
    first_hits = first_hits.assign(
        day=first_hits["days_since_cutover"],
        scales=_detection_scales(first_hits, single_day_kinds),
    )

    days = (
        after_cutover[keys + ["cutover_date"]]
        .drop_duplicates()
        .merge(
            first_hits[keys + ["cutover_date", "day", "scales"]],
            on=keys + ["cutover_date"],
            how="left",
        )
    )
    uncounted = days["cutover_date"].isin(uncounted_cutovers)
    counted_days = days.loc[~uncounted]
    table = spread_over_repeats(counted_days, keys, "day", count_detected=True)
    uncounted_days = (
        days.loc[uncounted]
        .pivot(index=keys, columns="cutover_date", values="day")
        .rename_axis(columns=None)
        .reset_index()
    )

    scales = counted_days.groupby(keys, as_index=False).agg(
        scales=("scales", lambda scales: ", ".join(sorted(scales.dropna().unique())))
    )
    # über alle Cutover, auch die nicht gezählten, gerade dort tritt es auf
    reset_by_cutover = (
        after_cutover.loc[single_day]
        .groupby(keys + ["cutover_date"])["own_reset"]
        .any()
    )
    single_day_resets = (
        reset_by_cutover.groupby(keys)
        .agg(lambda resets: f"{resets.sum()}/{len(resets)}")
        .rename("single_day_resets")
        .reset_index()
    )

    cutovers = sorted(days["cutover_date"].unique())
    table = (
        table.merge(uncounted_days, on=keys, how="left")
        .merge(scales, on=keys)
        .merge(single_day_resets, on=keys, how="left")
    )
    table[cutovers] = table[cutovers].astype("Int64")

    return table[keys + cutovers + ["mean", "detected", "single_day_resets", "scales"]]


def _near_control_reset(paired: pd.DataFrame, tolerance_days: int) -> pd.Series:
    # ein Reset kurz vor oder nach dem der Kontrolle ist derselbe natürliche Niveauwechsel, nur verschoben
    window = ["mode", "variant", "kind", "cutover_date"]
    control_resets = paired.loc[
        paired["new_pattern_control"], window + ["days_since_cutover"]
    ].rename(columns={"days_since_cutover": "control_reset_day"})
    candidates = (
        paired[window + ["days_since_cutover"]]
        .reset_index()
        .merge(control_resets, on=window)
    )
    near = (
        (candidates["days_since_cutover"] - candidates["control_reset_day"])
        .abs()
        .le(tolerance_days)
    )

    return pd.Series(
        paired.index.isin(candidates.loc[near, "index"]), index=paired.index
    )


def _detection_scales(
    hits: pd.DataFrame, single_day_kinds: tuple[str, ...]
) -> pd.Series:
    # Einzeltag: die Skala mit dem höchsten Score, new_pattern: alle Skalen mit Streak
    sustained = hits[SCALE_SUSTAINED_COLUMNS].eq(True)
    streak_scales = sustained.apply(
        lambda row: "+".join(
            scale for scale, on in zip(DAILY_ANOMALY_SCALES, row) if on
        ),
        axis=1,
    )

    return hits["dominant_scale"].where(
        hits["kind"].isin(single_day_kinds), streak_scales
    )


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
        "NumericalAnalysisConfig matches none of the K2 reference windows."
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
