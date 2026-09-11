from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
from nilmtk import DataSet

from src.analysis.common import MERGE_KEYS, require_columns
from src.data_preparation.aggregation.aggregation import build_aggregated_data
from src.data_preparation.aggregation.channel_loading import build_loaded_channels


PRESENCE_EXCLUDED_CHANNELS: dict[str, str] = {
    "H1_M1": "aggregate",
    "H1_M2": "boiler - Heizungsanlage, läuft unabhängig von Anwesenheit",
    "H1_M3": "solar_thermal_pump - Pumpe der Solarthermie, läuft unabhängig von Anwesenheit",
    "H1_M12": "fridge - Kühlschrank, läuft unabhängig von Anwesenheit durch",
    "H1_M18": "adsl_router - Router, läuft unabhängig von Anwesenheit durch",
    "H1_M21": "gigE_&_USBhub - Netzwerk-Hardware, läuft unabhängig von Anwesenheit durch",
    "H1_M43": "data_logger_pc - Messrechner der UK-DALE-Erfassung selbst, kein Haushaltsgerät, läuft zwangsläufig durchgehend; taucht in channel_registry.csv"
    "nur als 'computer / external hard disk' auf",
    "H1_M46": "baby_monitor_tx - an Kind/Betreuung gekoppelt, nicht zwingend an Abwesenheit des ganzen Haushalts"
}

DEFAULT_MIN_SAMPLING_SHARE = 0.5

DEFAULT_ACTIVE_THRESHOLD_W = 5.0

REQUIRED_REGISTRY_COLUMNS = MERGE_KEYS + ["appliances"]
REQUIRED_QUALITY_COLUMNS = MERGE_KEYS + ["is_mains", "start", "end", "sampling_share", "quality_error"]


def filter_candidate_channels(
    channel_registry: pd.DataFrame,
    channel_quality: pd.DataFrame,
    *,
    house: int,
    window_start: pd.Timestamp,
    window_end: pd.Timestamp,
    excluded_channels: dict[str, str] = PRESENCE_EXCLUDED_CHANNELS,
    min_sampling_share: float = DEFAULT_MIN_SAMPLING_SHARE,
) -> pd.DataFrame:
    """Grober Metadaten-Vorfilter """
    require_columns(channel_registry, REQUIRED_REGISTRY_COLUMNS, "channel_registry")
    require_columns(channel_quality, REQUIRED_QUALITY_COLUMNS, "channel_quality")

    if window_end <= window_start:
        raise ValueError("window_end must be after window_start.")

    registry = channel_registry.loc[
        channel_registry["house"].eq(house) & ~channel_registry["meter_key"].isin(excluded_channels)
    ].copy()

    registry["appliances"] = registry["appliances"].fillna("").astype(str).str.strip()
    registry = registry.loc[registry["appliances"].ne("")]

    quality = channel_quality.loc[
        channel_quality["house"].eq(house) & ~channel_quality["is_mains"].astype(bool)
    ].copy()
    quality["start"] = pd.to_datetime(quality["start"], utc=True)
    quality["end"] = pd.to_datetime(quality["end"], utc=True)

    quality_error = quality["quality_error"].fillna("").astype(str).str.strip()
    overlaps_window = quality["start"].lt(window_end) & quality["end"].gt(window_start)
    enough_sampling = quality["sampling_share"].fillna(0.0).ge(min_sampling_share)

    quality = quality.loc[quality_error.eq("") & overlaps_window & enough_sampling]

    return registry.merge(
        quality[MERGE_KEYS + ["start", "end", "sampling_share"]],
        on=MERGE_KEYS,
        how="inner",
        validate="one_to_one",
    ).reset_index(drop=True)


def rank_by_coverage(
    quality: pd.DataFrame,
    data: pd.DataFrame,
    candidates: pd.DataFrame,
    *,
    window_start: pd.Timestamp,
    window_end: pd.Timestamp,
    active_threshold_w: float = DEFAULT_ACTIVE_THRESHOLD_W,
) -> pd.DataFrame:

    if candidates.empty:
        return pd.DataFrame(columns=["meter_key", "appliance", "coverage_share", "activity_share", "rank"])

    windowed_quality = quality.loc[window_start : window_end - pd.Timedelta(seconds=1)]
    windowed_data = data.loc[window_start : window_end - pd.Timedelta(seconds=1)]
    rows: list[dict[str, object]] = []

    for candidate in candidates.itertuples(index=False):
        meter_key = str(candidate.meter_key)
        mask_column = f"{meter_key}_coverage_mask"

        if mask_column not in windowed_quality.columns or windowed_quality.empty:
            coverage_share = 0.0
        else:
            coverage_share = float(windowed_quality[mask_column].mean())

        if meter_key not in windowed_data.columns or windowed_data.empty:
            activity_share = 0.0
        else:
            activity_share = float(windowed_data[meter_key].gt(active_threshold_w).mean())

        rows.append(
            {
                "meter_key": meter_key,
                "appliance": candidate.appliances,
                "coverage_share": coverage_share,
                "activity_share": activity_share,
            }
        )
        

    ranked = pd.DataFrame(rows).sort_values(
        by=["activity_share", "coverage_share", "meter_key"],
        ascending=[False, False, True],
        kind="mergesort",
    ).reset_index(drop=True)
    ranked["rank"] = ranked.index + 1

    return ranked


@dataclass(frozen=True)
class AuxiliaryApplianceSelection:
    ranking: pd.DataFrame  # meter_key, appliance, coverage_share, activity_share, rank -> nach activity_share absteigend sortiert
    data_hourly: pd.DataFrame  # echte, aggregierte Stundenwerte der Kandidaten im Zielfenster (W) -> für die eigentliche Addition/Subtraktion in E1/E2, kein zweiter Load nötig


def build_auxiliary_appliance_selection(
    dataset: DataSet,
    channel_registry: pd.DataFrame,
    channel_quality: pd.DataFrame,
    *,
    house: int,
    window_start: pd.Timestamp,
    window_end: pd.Timestamp,
    canonical_ac_type: str,
    min_coverage_share: float,
    excluded_channels: dict[str, str] = PRESENCE_EXCLUDED_CHANNELS,
    min_sampling_share: float = DEFAULT_MIN_SAMPLING_SHARE,
) -> AuxiliaryApplianceSelection:
   
   
    candidates = filter_candidate_channels(
        channel_registry,
        channel_quality,
        house=house,
        window_start=window_start,
        window_end=window_end,
        excluded_channels=excluded_channels,
        min_sampling_share=min_sampling_share,
    )

    empty_ranking = pd.DataFrame(columns=["meter_key", "appliance", "coverage_share", "activity_share", "rank"])

    if candidates.empty:
        return AuxiliaryApplianceSelection(ranking=empty_ranking, data_hourly=pd.DataFrame())

    loaded_channels = build_loaded_channels(
        dataset=dataset,
        channel_quality=channel_quality,
        canonical_ac_type=canonical_ac_type,
        mains_only=False,
        selected_house_ids=[house],
        include_meter_keys=set(candidates["meter_key"]),
        window_start=window_start,
        window_end=window_end,
    )

    sample_periods = dict(zip(channel_registry["meter_key"], channel_registry["sample_period_seconds"]))

    _data_15min, _quality_15min, data_hourly, quality_hourly = build_aggregated_data(
        channels=loaded_channels,
        sample_periods=sample_periods,
        min_coverage_share=min_coverage_share,
    )

    ranking = rank_by_coverage(
        quality_hourly,
        data_hourly,
        candidates,
        window_start=window_start,
        window_end=window_end,
    )

    return AuxiliaryApplianceSelection(
        ranking=ranking,
        data_hourly=data_hourly.loc[window_start : window_end - pd.Timedelta(hours=1)],
    )