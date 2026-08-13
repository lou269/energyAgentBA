from __future__ import annotations

import pandas as pd
from nilmtk import DataSet, TimeFrame


MANIFEST_COLUMNS = [
    "selection_role",
    "candidate_id",
    "house",
    "meter_instance",
    "meter_key",
    "channel_role",
    "appliance",
    "balance",
    "explanation",
    "experiment",
    "window_start",
    "window_end",
]

REQUIRED_COLUMNS = {
    "candidate_profiles": {
        "candidate_id",
        "house",
        "mains_instance",
        "longest_segment_start",
        "longest_segment_end",
    },
    "provisional_selection": {"selection_role", "candidate_id"},
    "auxiliary_selection": {
        "selection_role",
        "candidate_id",
        "house",
        "meter_instance",
        "meter_key",
        "appliance",
        "balance",
        "explanation",
        "experiment",
    },
    "channel_registry": {
        "house",
        "meter_instance",
        "meter_key",
        "meter_type",
    },
}



def build_selected_data(
    dataset: DataSet,
    candidate_profiles: pd.DataFrame,
    provisional_selection: pd.DataFrame,
    auxiliary_selection: pd.DataFrame,
    channel_registry: pd.DataFrame,
    *,
    sample_period: int = 6,
    canonical_ac_type: str,
    include_fallback: bool,
    chunksize: int | None = None,
) -> tuple[dict, pd.DataFrame]:
    """Lädt und aligniert die ausgewählten Kanäle auf einem gemeinsamen Raster."""
    _validate_inputs(
        candidate_profiles,
        provisional_selection,
        auxiliary_selection,
        channel_registry,
        sample_period,
    )

    roles = ["primary", "fallback"] if include_fallback else ["primary"]

    candidates = (
        provisional_selection.loc[
            provisional_selection["selection_role"].isin(roles)
        ]
        .merge(
            candidate_profiles[
                [
                    "candidate_id",
                    "house",
                    "mains_instance",
                    "longest_segment_start",
                    "longest_segment_end",
                ]
            ],
            on="candidate_id",
            how="inner",
            validate="one_to_one",
        )
    )

    manifest = _build_manifest(
        candidates,
        auxiliary_selection,
        channel_registry,
    )

    aligned_data: dict = {}

    for role, selected in manifest.groupby("selection_role", sort=False):
        start = pd.to_datetime(selected["window_start"].iloc[0], utc=True)
        end = pd.to_datetime(selected["window_end"].iloc[0], utc=True)

        channel_data = {}

        for row in selected.to_dict(orient="records"):
            house = int(row["house"])
            meter_instance = int(row["meter_instance"])

            meter = dataset.buildings[house].elec[meter_instance]

            kwargs = {
                "sections": [TimeFrame(start=start, end=end)],
                "ac_type": canonical_ac_type,
                "sample_period": sample_period,
                "resample": True,
                "resample_kwargs": {
                    "how": "mean",
                    "fill_method": None,
                },
            }

            if chunksize is not None:
                kwargs["chunksize"] = chunksize

            loaded = meter.power_series_all_data(**kwargs)

            if loaded is None:
                loaded = pd.Series(dtype="float64")
            else:
                loaded = loaded.copy()
                loaded.index = loaded.index.tz_convert("UTC")

            channel_data[str(row["meter_key"])] = loaded

        freq = f"{sample_period}s"

        grid = pd.date_range(
            start=start.ceil(freq),
            end=end - pd.Timedelta("1ns"),
            freq=freq,
        )

        frame = pd.DataFrame(channel_data).reindex(grid)
        frame.index.name = "timestamp"
        aligned_data[str(role)] = frame

    return aligned_data, manifest


def _build_manifest(
    candidates: pd.DataFrame,
    auxiliary_selection: pd.DataFrame,
    channel_registry: pd.DataFrame,
) -> pd.DataFrame:
    rows = []

    selected_auxiliary = auxiliary_selection.loc[
        auxiliary_selection[
            ["balance", "explanation", "experiment"]
        ].eq(True).any(axis=1)
    ]

    for candidate in candidates.to_dict(orient="records"):
        start = pd.to_datetime(
            str(candidate["longest_segment_start"]),
            utc=True,
        )
        end = pd.to_datetime(
            str(candidate["longest_segment_end"]),
            utc=True,
        )

        house = int(candidate["house"])
        mains_instance = int(candidate["mains_instance"])


        if end <= start:
            raise ValueError(
                f"Invalid extraction window for {candidate['candidate_id']}."
            )

        base = {
            "selection_role": candidate["selection_role"],
            "candidate_id": candidate["candidate_id"],
            "house": house,
            "window_start": start,
            "window_end": end,
        }

        mains = channel_registry.loc[
            channel_registry["house"].eq(house)
            & channel_registry["meter_type"].eq("mains")
            & channel_registry["meter_instance"].eq(mains_instance)
        ]

        if len(mains) != 1:
            raise ValueError(
                f"Could not resolve mains for {candidate['candidate_id']}."
            )

        meter = mains.iloc[0]

        rows.append(
            {
                **base,
                "meter_instance": int(meter["meter_instance"]),
                "meter_key": str(meter["meter_key"]),
                "channel_role": "mains",
                "appliance": "",
                "balance": False,
                "explanation": False,
                "experiment": False,
            }
        )

        auxiliary = selected_auxiliary.loc[
            selected_auxiliary["candidate_id"].eq(
                candidate["candidate_id"]
            )
            & selected_auxiliary["selection_role"].eq(
                candidate["selection_role"]
            )
            & selected_auxiliary["house"].eq(house)
        ]

        for meter in auxiliary.itertuples(index=False):
            rows.append(
                {
                    **base,
                    "meter_instance": int(meter.meter_instance),
                    "meter_key": str(meter.meter_key),
                    "channel_role": "auxiliary",
                    "appliance": str(meter.appliance),
                    "balance": bool(meter.balance),
                    "explanation": bool(meter.explanation),
                    "experiment": bool(meter.experiment),
                }
            )

    manifest = pd.DataFrame(rows, columns=MANIFEST_COLUMNS)

    if manifest.empty:
        raise ValueError("No channels selected for extraction.")

    if manifest.duplicated(
        ["selection_role", "house", "meter_instance"]
    ).any():
        raise ValueError("Selected channel manifest contains duplicates.")

    return manifest.reset_index(drop=True)


def _validate_inputs(
    candidate_profiles: pd.DataFrame,
    provisional_selection: pd.DataFrame,
    auxiliary_selection: pd.DataFrame,
    channel_registry: pd.DataFrame,
    sample_period: int,
) -> None:
    frames = {
        "candidate_profiles": candidate_profiles,
        "provisional_selection": provisional_selection,
        "auxiliary_selection": auxiliary_selection,
        "channel_registry": channel_registry,
    }

    for name, frame in frames.items():
        missing = REQUIRED_COLUMNS[name] - set(frame.columns)
        if missing:
            raise ValueError(
                f"{name} is missing columns: {', '.join(sorted(missing))}"
            )

    if sample_period <= 0:
        raise ValueError("sample_period must be greater than zero.")

    roles = set(provisional_selection["selection_role"].dropna().astype(str))
    if "primary" not in roles or not roles <= {"primary", "fallback"}:
        raise ValueError("Invalid provisional selection roles.")