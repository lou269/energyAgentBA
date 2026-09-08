from __future__ import annotations

import logging
import pandas as pd
from nilmtk import DataSet

logger = logging.getLogger(__name__)

CHANNEL_REGISTRY_COLUMNS = [
    "house",
    "meter_instance",
    "meter_key",
    "meter_type",
    "appliances",
    "ac_types",
    "has_canonical_ac_type",
    "sample_period_seconds",
]

def _get_appliance_names(meter) -> str:
    names = []

    for appliance in meter.appliances:
        if appliance.identifier.type is not None:
            names.append(str(appliance.identifier.type))

    return ", ".join(sorted(set(names)))

def build_channel_registry(
    dataset: DataSet,
    canonical_ac_type: str,
) -> pd.DataFrame:
    rows = []

    for house_id, building in dataset.buildings.items():
        for meter in building.elec.meters:
            meter_instance = meter.instance()

            try:
                ac_types = list(meter.available_ac_types("power"))
            except Exception as error:
                logger.warning(
                    "House %s meter %s: could not read AC types: %s",
                    house_id,
                    meter_instance,
                    error,
                )
                ac_types = []

            site_meter = bool(meter.is_site_meter())
            device = meter.device or {}

            rows.append(
                {
                    "house": house_id,
                    "meter_instance": meter_instance,
                    "meter_key": f"H{house_id}_M{meter_instance}",
                    "meter_type": "mains" if site_meter else "submeter",
                    "appliances": _get_appliance_names(meter),
                    "ac_types": ", ".join(ac_types),
                    "has_canonical_ac_type": canonical_ac_type in ac_types,
                    "sample_period_seconds": device.get("sample_period"),
                }
            )

    registry = pd.DataFrame(
        rows,
        columns=CHANNEL_REGISTRY_COLUMNS,
    )

    if registry.empty:
        logger.warning("Channel registry is empty.")
        return registry

    return registry.sort_values(
        ["house", "meter_type", "meter_instance"]
    ).reset_index(drop=True)