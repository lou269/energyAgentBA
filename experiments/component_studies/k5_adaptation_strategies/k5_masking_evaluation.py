from pathlib import Path

import numpy as np
import pandas as pd


def read_sys2_decisions(run_directory: Path, *, kind: str, cutover_date: str) -> pd.DataFrame:
    summary = pd.read_csv(run_directory / "comparison_summary.csv")
    summary["decision_time"] = pd.to_datetime(summary["decision_time"], utc=True)

    return summary[["decision_time", "classification", "adaption_action", "mae_w"]].rename(
        columns={"mae_w": "mae_sys2_w"}
    ).assign(kind=kind, cutover_date=cutover_date)


def pair_masking(results: pd.DataFrame, decisions: pd.DataFrame, masked_classifications: tuple[str, ...]) -> pd.DataFrame:
    """replay und mask tageweise nebeneinander, dazu die SYS2-Entscheidung desselben Tages"""
    keys = ["kind", "cutover_date", "decision_time"]

    paired = (
        results.pivot(index=[*keys, "days_since_cutover"], columns="strategy", values="mae_w")
        .rename(columns={"replay": "mae_replay_w", "mask": "mae_mask_w"})
        .reset_index()
        .merge(decisions[[*keys, "classification", "mae_sys2_w"]], on=keys)
    )

    paired["mae_delta_w"] = paired["mae_mask_w"] - paired["mae_replay_w"]
    # replay muss SYS2 exakt nachbilden, sonst ist das Nachspielen falsch
    paired["replay_matches_sys2"] = np.isclose(paired["mae_replay_w"], paired["mae_sys2_w"], equal_nan=True)
    paired["masked_day"] = paired["classification"].isin(masked_classifications)

    return paired


def summarize_masking(paired: pd.DataFrame, early_days: int) -> pd.DataFrame:
    # control: Nutzen bei echten Ausreißern, step: Kosten, wenn der Beginn einer echten Änderung erst als peak ausgeblendet wird
    phase = pd.cut(
        paired["days_since_cutover"],
        [-np.inf, -1, early_days - 1, np.inf],
        labels=["before", f"days_0_{early_days - 1}", f"days_{early_days}_plus"],
    )

    return paired.assign(phase=phase.astype(str)).groupby(["kind", "cutover_date", "phase"], as_index=False).agg(
        days=("mae_delta_w", "count"),
        masked_days=("masked_day", "sum"),
        mae_replay_w=("mae_replay_w", "mean"),
        mae_mask_w=("mae_mask_w", "mean"),
        mae_delta_w=("mae_delta_w", "mean"),
        replay_matches_sys2=("replay_matches_sys2", "mean"),
    )