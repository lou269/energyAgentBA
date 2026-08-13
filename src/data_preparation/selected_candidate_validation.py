from __future__ import annotations

import numpy as np
import pandas as pd

SECONDS_PER_DAY = 86_400.0

CHANNEL_VALIDATION_COLUMNS = [
    "selection_role",
    "candidate_id",
    "meter_key",
    "channel_role",
    "balance",
    "coverage_share",
    "missing_share",
    "longest_missing_run_seconds",
]

CANDIDATE_VALIDATION_COLUMNS = [
    "selection_role",
    "candidate_id",
    "grid_complete",
    "mains_coverage_share",
    "min_balance_channel_coverage_share",
    "simultaneous_coverage_share",
    "simultaneous_valid_duration_days",
    "longest_simultaneous_missing_run_seconds",
    "valid_energy_interval_count",
    "mean_residual_power_w",
    "explained_power_share",
    "negative_residual_share",
    "residual_energy_share",
    "energy_closure_share",
    "duplicate_counting",
    "validation_passed",
    "rejection_reason",
]


def build_selected_candidate_validation(
    aligned_data: dict[str, pd.DataFrame],
    manifest: pd.DataFrame,
    *,
    sample_period: int,
    min_mains_coverage_share: float,
    min_balance_channel_coverage_share: float,
    min_simultaneous_valid_duration_days: float,
) -> tuple[pd.DataFrame, pd.DataFrame, str | None]:
    """Validiert Primary und Fallback nach dem zeitlichen Alignment."""
    
    _validate_inputs(
        aligned_data,
        manifest,
        sample_period,
        min_mains_coverage_share,
        min_balance_channel_coverage_share,
        min_simultaneous_valid_duration_days,
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

        candidate_ids = selected["candidate_id"].dropna().astype(str).unique()

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

        channel_metrics = {}

        for row in selected.to_dict(orient="records"):
            key = str(row["meter_key"])

            metrics = _availability_metrics(
                frame[key].isna(),
                sample_period,
            )

            channel_metrics[key] = metrics

            channel_rows.append(
                {
                    "selection_role": role,
                    "candidate_id": candidate_id,
                    "meter_key": key,
                    "channel_role": row["channel_role"],
                    "balance": bool(row["balance"]),
                    **metrics,
                }
            )
            
        grid_complete = _grid_complete(frame, sample_period)

        mains_keys = (
            selected.loc[
                selected["channel_role"].eq("mains"),
                "meter_key",
            ]
            .astype(str)
            .tolist()
        )

        balance_keys = (
            selected.loc[
                selected["balance"].eq(True),
                "meter_key",
            ]
            .astype(str)
            .tolist()
        )

        balance_coverages = [
            channel_metrics[key]["coverage_share"]
            for key in balance_keys
            if channel_metrics[key]["coverage_share"] is not None
        ]

        min_balance_channel_coverage = (
            min(balance_coverages)
            if len(balance_coverages) == len(balance_keys)
            and balance_coverages
            else None
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

        if balance_keys:
            simultaneous_keys = list(
                dict.fromkeys(mains_keys + balance_keys)
            )

            simultaneous_frame = frame[simultaneous_keys]

            simultaneous_missing = pd.Series(
                simultaneous_frame
                .isna()
                .to_numpy()
                .any(axis=1),
                index=simultaneous_frame.index,
            )

            simultaneous_metrics = _availability_metrics(
                simultaneous_missing,
                sample_period,
            )

            simultaneous_valid_count = int(
                (~simultaneous_missing).sum()
            )

            simultaneous_valid_duration_days = (
                simultaneous_valid_count
                * sample_period
                / SECONDS_PER_DAY
            )
        else:
            simultaneous_metrics = {
                "coverage_share": None,
                "missing_share": None,
                "longest_missing_run_seconds": None,
            }
            simultaneous_valid_duration_days = None

        duplicate_counting = bool(
            selected["meter_instance"].duplicated().any()
            or selected["meter_key"].astype(str).duplicated().any()
            or bool(set(mains_keys) & set(balance_keys))
        )

        energy = _energy_metrics(
            frame,
            mains_keys,
            balance_keys,
        )

        reasons = []

        if not grid_complete:
            reasons.append("incomplete_grid")

        mains_coverage = mains_metrics["coverage_share"]

        if (
            mains_coverage is None
            or mains_coverage < min_mains_coverage_share
        ):
            reasons.append("mains_coverage")


        if not balance_keys:
            reasons.append("no_balance_channels")

        elif (
            min_balance_channel_coverage is None
            or min_balance_channel_coverage
            < min_balance_channel_coverage_share
        ):
            reasons.append("balance_channel_coverage")

        if (
            balance_keys
            and (
                simultaneous_valid_duration_days is None
                or simultaneous_valid_duration_days
                < min_simultaneous_valid_duration_days
            )
        ):
            reasons.append("simultaneous_duration")

        if duplicate_counting:
            reasons.append("duplicate_counting")

        if energy["valid_energy_interval_count"] == 0:
            reasons.append("no_valid_energy_intervals")



        candidate_rows.append(
            {
                "selection_role": role,
                "candidate_id": candidate_id,
                "grid_complete": grid_complete,
                "mains_coverage_share": (
                    mains_metrics["coverage_share"]
                ),
                "min_balance_channel_coverage_share": (
                    min_balance_channel_coverage
                ),
                "simultaneous_coverage_share": (
                    simultaneous_metrics["coverage_share"]
                ),
                "simultaneous_valid_duration_days": (
                    simultaneous_valid_duration_days
                ),
                "longest_simultaneous_missing_run_seconds": (
                    simultaneous_metrics[
                        "longest_missing_run_seconds"
                    ]
                ),
                **energy,
                "duplicate_counting": duplicate_counting,
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

    selected_role = _select_role(
        candidate_validation
    )

    return (
        channel_validation,
        candidate_validation,
        selected_role,
    )


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


def _energy_metrics(
    frame: pd.DataFrame,
    mains_keys: list[str],
    balance_keys: list[str],
) -> dict:
    empty = {
        "valid_energy_interval_count": 0,
        "mean_residual_power_w": None,
        "explained_power_share": None,
        "negative_residual_share": None,
        "residual_energy_share": None,
        "energy_closure_share": None,
    }

    if not balance_keys:
        return empty

    keys = list(
        dict.fromkeys(mains_keys + balance_keys)
    )

    values = frame[keys].apply(
        pd.to_numeric,
        errors="coerce",
    )

    values = values.replace(
        [np.inf, -np.inf],
        np.nan,
    )

    valid = values.notna().all(axis=1)
    
    if not valid.any():
        return empty

    values = values.loc[valid]

    mains_power = values[mains_keys].sum(axis=1)
    appliance_power = values[balance_keys].sum(axis=1)

    residual = mains_power - appliance_power

    mains_energy = float(mains_power.abs().sum())

    if mains_energy <= 0:
        return empty

    explained_power_share = float(
        appliance_power.clip(lower=0).sum() / mains_energy
    )

    residual_energy_share = float(
        residual.clip(lower=0).sum() / mains_energy
    )

    energy_closure_share = float(
        1.0 - residual.abs().sum() / mains_energy
    )

    return {
        "valid_energy_interval_count": int(len(residual)),
        "mean_residual_power_w": float(residual.mean()),
        "explained_power_share": explained_power_share,
        "negative_residual_share": float(residual.lt(0).mean()),
        "residual_energy_share": residual_energy_share,
        "energy_closure_share": energy_closure_share,
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
    min_balance_channel_coverage_share: float,
    min_simultaneous_valid_duration_days: float,
) -> None:
    required_columns = {
        "selection_role",
        "candidate_id",
        "meter_instance",
        "meter_key",
        "channel_role",
        "balance",
    }

    missing = required_columns.difference(manifest.columns)

    if missing:
        raise ValueError(
            "manifest is missing required columns: "
            + ", ".join(sorted(missing))
        )

    if sample_period <= 0:
        raise ValueError(
            "sample_period must be greater than zero."
        )

    thresholds = {
        "min_mains_coverage_share": min_mains_coverage_share,
        "min_balance_channel_coverage_share": (
            min_balance_channel_coverage_share
        ),
    }

    for name, value in thresholds.items():
        if not 0.0 <= value <= 1.0:
            raise ValueError(
                f"{name} must be between 0 and 1."
            )

    if min_simultaneous_valid_duration_days <= 0:
        raise ValueError(
            "min_simultaneous_valid_duration_days "
            "must be greater than zero."
        )

    if "primary" not in aligned_data:
        raise ValueError(
            "aligned_data must contain a primary candidate."
        )