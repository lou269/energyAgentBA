from __future__ import annotations

from collections.abc import Sequence

import pandas as pd

from src.common.channel_tables import mains_channels

SELECTION_COLUMNS = [
    "candidate_id",
    "window",
    "window_start",
    "window_end",
]

DECISION_COLUMNS = [
    "candidate_id",
    "house",
    "meter_key",
    "eligible_for_selection",
    "selection_rank",
    "selected",
    "window",
    "decision_reason",
    "length_days",
    "coverage_share",
    "window_start",
    "window_end",
]

REQUIRED_AVAILABILITY_COLUMNS = {
    "meter_key",
    "start",
    "end",
    "length_days",
    "coverage_share",
}
REQUIRED_REGISTRY_COLUMNS = {"house", "meter_instance", "meter_key", "meter_type"}


def build_candidate_selection(
    availability: pd.DataFrame,
    channel_registry: pd.DataFrame,
    min_valid_duration_days: float,
    min_coverage_share: float,
    windows: Sequence[str],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    _validate_inputs(
        availability, channel_registry, min_valid_duration_days, min_coverage_share
    )

    candidates = availability.merge(
        mains_channels(channel_registry), on="meter_key", how="inner"
    )

    if candidates.empty:
        return (
            pd.DataFrame(columns=SELECTION_COLUMNS),
            pd.DataFrame(columns=DECISION_COLUMNS),
        )

    candidates = candidates.sort_values(
        by=["house", "meter_instance", "start"],
        kind="mergesort",
    ).reset_index(drop=True)

    span_index_within_channel = (
        candidates.groupby(["house", "meter_instance"]).cumcount() + 1
    )
    candidates["candidate_id"] = (
        "H"
        + candidates["house"].astype(str)
        + "-M"
        + candidates["meter_instance"].astype(str)
        + "-S"
        + span_index_within_channel.astype(str)
    )

    duration_ok = candidates["length_days"] >= min_valid_duration_days
    coverage_ok = candidates["coverage_share"] >= min_coverage_share

    rejection_reason = pd.Series("", index=candidates.index)
    rejection_reason = rejection_reason.where(
        duration_ok, rejection_reason + "length_below_threshold;"
    )
    rejection_reason = rejection_reason.where(
        coverage_ok, rejection_reason + "coverage_below_threshold;"
    )

    candidates["eligible_for_selection"] = duration_ok & coverage_ok
    candidates["rejection_reason"] = rejection_reason.str.rstrip(";")

    ranked = candidates.sort_values(
        by=["length_days", "coverage_share", "candidate_id"],
        ascending=[False, False, True],
        na_position="last",
        kind="mergesort",
    ).reset_index(drop=True)

    ranked["selection_rank"] = range(1, len(ranked) + 1)
    ranked["selected"] = False
    ranked["decision_reason"] = ranked["rejection_reason"].where(
        ranked["rejection_reason"].ne(""),
        "not_selected_lower_rank",
    )

    # die längste zulässige Spanne bekommt das erste Fenster, die nächstlängste das zweite
    chosen = ranked.index[ranked["eligible_for_selection"]][: len(windows)]
    ranked["window"] = ""
    ranked.loc[chosen, "window"] = list(windows[: len(chosen)])
    ranked.loc[chosen, "selected"] = True
    ranked.loc[chosen, "decision_reason"] = "selected_for_window"

    decisions = ranked.rename(columns={"start": "window_start", "end": "window_end"})
    selection = decisions.loc[chosen, SELECTION_COLUMNS]
    decisions = decisions[DECISION_COLUMNS]

    # jedes Fenster beginnt nach dem Ende des vorigen, sonst sähe die Entwicklung Testdaten
    starts = pd.to_datetime(selection["window_start"], utc=True).to_numpy()[1:]
    ends = pd.to_datetime(selection["window_end"], utc=True).to_numpy()[:-1]

    if (starts <= ends).any():
        raise ValueError("Each window must start after the previous window ends.")

    return selection, decisions


def _validate_inputs(
    availability: pd.DataFrame,
    channel_registry: pd.DataFrame,
    min_valid_duration_days: float,
    min_coverage_share: float,
) -> None:
    missing_availability = REQUIRED_AVAILABILITY_COLUMNS.difference(
        availability.columns
    )

    if missing_availability:
        raise ValueError(
            "availability is missing columns: "
            + ", ".join(sorted(missing_availability))
        )

    missing_registry = REQUIRED_REGISTRY_COLUMNS.difference(channel_registry.columns)

    if missing_registry:
        raise ValueError(
            "channel_registry is missing columns: "
            + ", ".join(sorted(missing_registry))
        )

    if min_valid_duration_days <= 0:
        raise ValueError("min_valid_duration_days must be greater than 0.")

    if not 0.0 <= min_coverage_share <= 1.0:
        raise ValueError("min_coverage_share must be between 0 and 1.")
