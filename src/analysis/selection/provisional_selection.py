from __future__ import annotations

import pandas as pd


SELECTION_COLUMNS = [
    "selection_role",
    "candidate_id",
]

REQUIRED_PROFILE_COLUMNS = {
    "candidate_id",
    "house",
    "longest_segment_days",
    "total_coverage_days",
    "sampling_share",
}


def build_provisional_selection(
    candidate_profiles: pd.DataFrame,
    min_longest_segment_days: float,
) -> pd.DataFrame:
    """Wählt Primary und Fallback aus den geeigneten Candidate-Profilen."""
    
    missing = REQUIRED_PROFILE_COLUMNS.difference(candidate_profiles.columns)
    

    if missing:
        raise ValueError(
            "candidate_profiles is missing required columns: "
            + ", ".join(sorted(missing))
        )

    if min_longest_segment_days <= 0:
        raise ValueError(
            "min_longest_segment_days must be greater than 0."
        )

    eligible = candidate_profiles.loc[
        pd.to_numeric(
            candidate_profiles["longest_segment_days"],
            errors="coerce",
        )
        >= min_longest_segment_days
    ].copy()

    if eligible.empty:
        return pd.DataFrame(columns=SELECTION_COLUMNS)

    ranked = eligible.sort_values(
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
    )

    primary = ranked.iloc[0]

    rows = [
        {
            "selection_role": "primary",
            "candidate_id": primary["candidate_id"],
        }
    ]

    fallback_candidates = ranked.loc[
        ranked["house"].ne(primary["house"])
    ]

    if not fallback_candidates.empty:
        fallback = fallback_candidates.iloc[0]

        rows.append(
            {
                "selection_role": "fallback",
                "candidate_id": fallback["candidate_id"],
            }
        )

    return pd.DataFrame(
        rows,
        columns=SELECTION_COLUMNS,
    )