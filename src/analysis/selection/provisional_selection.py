from __future__ import annotations

import pandas as pd


SELECTION_COLUMNS = [
    "selection_role",
    "candidate_id",
]

DECISION_COLUMNS = [
    "candidate_id",
    "eligible_for_selection",
    "selection_rank",
    "selection_role",
    "decision_reason",
    "min_longest_segment_days",
    "longest_segment_days",
    "window_start",
    "window_end",
]

REQUIRED_PROFILE_COLUMNS = {
    "candidate_id",
    "house",
    "longest_segment_days",
    "longest_segment_start",
    "longest_segment_end",
    "total_coverage_days",
    "sampling_share",
}


def build_candidate_selection_outputs(
    candidate_profiles: pd.DataFrame,
    min_longest_segment_days: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    missing = REQUIRED_PROFILE_COLUMNS.difference(candidate_profiles.columns)

    if missing:
        raise ValueError("candidate_profiles is missing required columns: " + ", ".join(sorted(missing)))

    if min_longest_segment_days <= 0:
        raise ValueError("min_longest_segment_days must be greater than 0.")

    ranked = candidate_profiles.copy()
    ranked["longest_segment_days"] = pd.to_numeric(
        ranked["longest_segment_days"],
        errors="coerce",
    )

    ranked = ranked.sort_values(
        by=[
            "longest_segment_days",
            "total_coverage_days",
            "sampling_share",
            "candidate_id",
        ],
        ascending=[
            False,
            False,
            False,
            True,
        ],
        na_position="last",
        kind="mergesort",
    ).reset_index(drop=True)

    ranked["selection_rank"] = range(1, len(ranked) + 1)
    ranked["eligible_for_selection"] = ranked["longest_segment_days"] >= min_longest_segment_days

    ranked["selection_role"] = "not_selected"
    ranked["decision_reason"] = "longest_segment_below_threshold"

    eligible = ranked.loc[ranked["eligible_for_selection"]]

    ranked.loc[
        ranked["eligible_for_selection"],
        "decision_reason",
    ] = "not_selected_lower_rank"

    rows = []

    if not eligible.empty:
        primary = eligible.iloc[0]

        rows.append(
            {
                "selection_role": "primary",
                "candidate_id": primary["candidate_id"],
            }
        )

        primary_mask = ranked["candidate_id"].eq(primary["candidate_id"])
        
        ranked.loc[
            primary_mask,
            "selection_role",
        ] = "primary"
        ranked.loc[
            primary_mask,
            "decision_reason",
        ] = "highest_ranked_eligible_candidate"

        same_house_mask = (
            ranked["eligible_for_selection"]
            & ranked["house"].eq(primary["house"])
            & ~primary_mask
        )
        ranked.loc[
            same_house_mask,
            "decision_reason",
        ] = "same_house_as_primary"

        fallback_candidates = eligible.loc[eligible["house"].ne(primary["house"])]

        if not fallback_candidates.empty:
            fallback = fallback_candidates.iloc[0]

            rows.append(
                {
                    "selection_role": "fallback",
                    "candidate_id": fallback["candidate_id"],
                }
            )

            fallback_mask = ranked["candidate_id"].eq(fallback["candidate_id"])
            
            ranked.loc[
                fallback_mask,
                "selection_role",
            ] = "fallback"
            ranked.loc[
                fallback_mask,
                "decision_reason",
            ] = "highest_ranked_candidate_from_different_house"

    provisional_selection = pd.DataFrame(
        rows,
        columns=SELECTION_COLUMNS,
    )

    candidate_selection_decisions = (
        ranked.assign(
            min_longest_segment_days=min_longest_segment_days,
            window_start=ranked["longest_segment_start"],
            window_end=ranked["longest_segment_end"],
        )[DECISION_COLUMNS]
    )

    return provisional_selection, candidate_selection_decisions,