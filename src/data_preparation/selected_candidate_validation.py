from __future__ import annotations

import pandas as pd

SECONDS_PER_DAY = 86_400.0

CHANNEL_VALIDATION_COLUMNS = [
    "selection_role",
    "candidate_id",
    "meter_key",
    "channel_role",
    "coverage_share",
    "missing_share",
    "longest_missing_run_seconds",
]

CANDIDATE_VALIDATION_COLUMNS = [
    "selection_role",
    "candidate_id",
    "grid_complete",
    "mains_coverage_share",
    "mains_valid_duration_days",
    "validation_passed",
    "rejection_reason",
]

def build_selected_candidate_validation(
    aligned_data: dict[str, pd.DataFrame],
    manifest: pd.DataFrame,
    *,
    sample_period: int,
    min_mains_coverage_share: float,
    min_mains_valid_duration_days: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Validiert Primary und Fallback anhand des Mains-Kanals."""

    _validate_inputs(
        aligned_data,
        manifest,
        sample_period,
        min_mains_coverage_share,
        min_mains_valid_duration_days,
    )

    channel_rows = []
    candidate_rows = []

    for role in ("primary", "fallback"):
        if role not in aligned_data:
            continue

        frame = aligned_data[role]
        selected = manifest.loc[
            manifest["selection_role"].eq(role)
        ]

        if selected.empty or frame.empty:
            continue

        candidate_ids = (
            selected["candidate_id"]
            .dropna()
            .astype(str)
            .unique()
        )

        if len(candidate_ids) != 1:
            raise ValueError(
                f"Expected exactly one candidate for {role}."
            )

        candidate_id = candidate_ids[0]

        missing_columns = (
            set(selected["meter_key"].astype(str))
            - set(frame.columns.astype(str))
        )

        if missing_columns:
            raise ValueError(
                f"Missing aligned channels for {role}: "
                f"{sorted(missing_columns)}"
            )

        grid_complete = _grid_complete(
            frame,
            sample_period,
        )

        mains_keys = (
            selected.loc[
                selected["channel_role"].eq("mains"),
                "meter_key",
            ]
            .astype(str)
            .tolist()
        )

        if not mains_keys:
            raise ValueError(
                f"No mains channels found for {role}."
            )

        mains_frame = frame[mains_keys]

        mains_missing = pd.Series(
            mains_frame.isna().to_numpy().any(axis=1),
            index=mains_frame.index,
        )

        mains_metrics = _availability_metrics(
            mains_missing,
            sample_period,
        )
        
        for channel in selected.itertuples(index=False):
            meter_key = str(channel.meter_key)

            channel_metrics = _availability_metrics(
                frame[meter_key].isna(),
                sample_period,
            )

            channel_rows.append(
                {
                    "selection_role": role,
                    "candidate_id": candidate_id,
                    "meter_key": meter_key,
                    "channel_role": channel.channel_role,
                    **channel_metrics,
                }
            )

        mains_valid_count = int(
            (~mains_missing).sum()
        )

        mains_valid_duration_days = (
            mains_valid_count
            * sample_period
            / SECONDS_PER_DAY
        )

        reasons = []

        if not grid_complete:
            reasons.append("incomplete_grid")

        mains_coverage = mains_metrics["coverage_share"]

        if (
            mains_coverage is None
            or mains_coverage
            < min_mains_coverage_share
        ):
            reasons.append("mains_coverage")

        if (
            mains_valid_duration_days
            < min_mains_valid_duration_days
        ):
            reasons.append("mains_valid_duration")

        candidate_rows.append(
            {
                "selection_role": role,
                "candidate_id": candidate_id,
                "grid_complete": grid_complete,
                "mains_coverage_share": mains_coverage,
                "mains_valid_duration_days": (
                    mains_valid_duration_days
                ),
                "validation_passed": not reasons,
                "rejection_reason": ";".join(reasons),
            }
        )

    channel_validation = pd.DataFrame(
        channel_rows,
        columns=CHANNEL_VALIDATION_COLUMNS,
    )

    candidate_validation = pd.DataFrame(
        candidate_rows,
        columns=CANDIDATE_VALIDATION_COLUMNS,
    )

    return (
        channel_validation,
        candidate_validation,
    )

def select_candidate_role(
    candidate_validation: pd.DataFrame,
) -> str | None:
    for role in ("primary", "fallback"):
        row = candidate_validation.loc[
            candidate_validation["selection_role"].eq(role)
        ]

        if not row.empty and bool(row["validation_passed"].iloc[0]):
            return role

    return None

def _grid_complete(
    frame: pd.DataFrame,
    sample_period: int,
) -> bool:
    if frame.empty:
        return False

    expected = pd.date_range(
        start=frame.index[0],
        end=frame.index[-1],
        freq=f"{sample_period}s",
    )

    return bool(frame.index.equals(expected))


def _availability_metrics(
    missing: pd.Series,
    sample_period: int,
) -> dict:
    total = len(missing)
    missing_count = int(missing.sum())

    return {
        "coverage_share": (
            (total - missing_count) / total
            if total
            else None
        ),
        "missing_share": (
            missing_count / total
            if total
            else None
        ),
        "longest_missing_run_seconds": (
            _longest_run(missing) * sample_period
            if total
            else None
        ),
    }



def _longest_run(
    mask: pd.Series,
) -> int:
    groups = mask.ne(
        mask.shift(fill_value=False)
    ).cumsum()

    runs = (
        mask[mask]
        .groupby(groups[mask])
        .size()
    )

    return int(runs.max()) if not runs.empty else 0


def _select_role(
    candidate_validation: pd.DataFrame,
) -> str | None:
    for role in ("primary", "fallback"):
        row = candidate_validation.loc[
            candidate_validation["selection_role"].eq(role)
        ]

        if (
            not row.empty
            and bool(row["validation_passed"].iloc[0])
        ):
            return role

    return None


def _validate_inputs(
    aligned_data: dict[str, pd.DataFrame],
    manifest: pd.DataFrame,
    sample_period: int,
    min_mains_coverage_share: float,
    min_mains_valid_duration_days: float,
) -> None:
    required_columns = {
        "selection_role",
        "candidate_id",
        "meter_instance",
        "meter_key",
        "channel_role",
    }

    missing = required_columns.difference(
        manifest.columns
    )

    if missing:
        raise ValueError(
            "manifest is missing required columns: "
            + ", ".join(sorted(missing))
        )

    if sample_period <= 0:
        raise ValueError(
            "sample_period must be greater than zero."
        )

    if not 0.0 <= min_mains_coverage_share <= 1.0:
        raise ValueError(
            "min_mains_coverage_share must be "
            "between 0 and 1."
        )

    if min_mains_valid_duration_days <= 0:
        raise ValueError(
            "min_mains_valid_duration_days "
            "must be greater than zero."
        )

    if "primary" not in aligned_data:
        raise ValueError(
            "aligned_data must contain "
            "a primary candidate."
        )