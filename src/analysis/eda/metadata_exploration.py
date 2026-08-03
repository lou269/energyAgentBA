from __future__ import annotations

import logging
from typing import Any
import pandas as pd
from nilmtk import DataSet

logger = logging.getLogger(__name__)


def get_mains_meters(elec) -> list:
    try:
        mains = elec.mains()
    except Exception:
        return []

    if hasattr(mains, "meters"):
        return list(mains.meters)

    return [mains]

def get_appliance_names(meter: Any) -> str:
    appliances = getattr(meter, "appliances", [])

    names = [
        appliance.identifier.type
        for appliance in appliances
        if hasattr(appliance, "identifier")
    ]

    return ", ".join(names)

def build_channel_registry(
    dataset: DataSet,
    canonical_ac_type: str = "active",
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for house_id, building in dataset.buildings.items():
        elec = building.elec

        mains_instances = {
            meter.instance()
            for meter in get_mains_meters(elec)
        }

        for meter in elec.meters:
            meter_instance = meter.instance()
            metadata_error: str | None = None

            try:
                ac_types = list(
                    meter.available_ac_types("power")
                )
            except Exception as error:
                logger.warning(
                    "House %s meter %s: could not read AC types: %s",
                    house_id,
                    meter_instance,
                    error,
                )
                ac_types = []
                metadata_error = str(error)

            try:
                label = meter.label()
            except Exception as error:
                logger.warning(
                    "House %s meter %s: could not read label: %s",
                    house_id,
                    meter_instance,
                    error,
                )
                label = None

                if metadata_error is None:
                    metadata_error = str(error)

            device = meter.device or {}

            meter_type = (
                "mains"
                if meter_instance in mains_instances
                else "submeter"
            )

            rows.append(
                {
                    "house": house_id,
                    "meter_instance": meter_instance,
                    "meter_key": str(meter.key),
                    "meter_type": meter_type,
                    "site_meter": meter.is_site_meter(),
                    "label": label,
                    "appliances": get_appliance_names(meter),
                    "ac_types": ", ".join(ac_types),
                    "has_canonical_ac_type": (canonical_ac_type in ac_types),
                    "sample_period_seconds": device.get("sample_period"),
                    "max_sample_period_seconds": device.get("max_sample_period"),
                    "metadata_error": metadata_error,
                }
            )

    registry = pd.DataFrame(rows)

    if registry.empty:
        logger.warning(
            "Channel registry is empty."
        )
        return registry

    return registry.sort_values(
        by=["house", "meter_type", "meter_instance"],
        ascending=[True, True, True],
    ).reset_index(drop=True)



