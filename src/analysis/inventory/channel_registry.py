from __future__ import annotations

import logging
import pandas as pd
from nilmtk import DataSet

logger = logging.getLogger(__name__)


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
            ac_type_error: str | None = None

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
                ac_type_error = str(error)

            site_meter = bool(meter.is_site_meter())
            appliance_names = _get_appliance_names(meter)

            label = (
                "mains"
                if site_meter
                else appliance_names or f"meter_{meter_instance}"
            )

            device = meter.device or {}

            rows.append(
                {
                    "house": house_id,
                    "meter_instance": meter_instance,
                    "meter_key": str(meter.key),
                    "meter_type": "mains" if site_meter else "submeter",
                    "site_meter": site_meter,
                    "label": label,
                    "appliances": appliance_names,
                    "ac_types": ", ".join(ac_types),
                    "has_canonical_ac_type": canonical_ac_type in ac_types,
                    "sample_period_seconds": device.get("sample_period"),
                    "max_sample_period_seconds": device.get("max_sample_period"),
                    "ac_type_error": ac_type_error,
                }
            )

    registry = pd.DataFrame(rows)

    if registry.empty:
        logger.warning("Channel registry is empty.")
        return registry

    return registry.sort_values(
        ["house", "meter_type", "meter_instance"]
    ).reset_index(drop=True)