from __future__ import annotations

import logging
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


def check_ac_types(dataset: DataSet) -> pd.DataFrame:
    summary = []

    for house_id, building in dataset.buildings.items():
        elec = building.elec
        mains_instances = {meter.instance() for meter in get_mains_meters(elec)}

        for meter in elec.meters:
            try:
                ac_types = meter.available_ac_types("power")
            except Exception as error:
                ac_types = [f"ERROR: {error}"]

            appliance_names = [
                app.identifier.type
                for app in meter.appliances
                if hasattr(app, "identifier")
            ]
            

            summary.append({
                "house": house_id,
                "meter_instance": meter.instance(),
                "meter_type": "mains" if meter.instance() in mains_instances else "submeter",
                "ac_types": ", ".join(ac_types),
                "has_active": "active" in ac_types,
                "has_apparent": "apparent" in ac_types,
                "appliances": ", ".join(appliance_names),
            })

    return pd.DataFrame(summary)


def inspect_mains(dataset: DataSet) -> pd.DataFrame:
    summary = []

    for house_id, building in dataset.buildings.items():
        elec = building.elec

        for mains in get_mains_meters(elec):
            ac_types = mains.available_ac_types("power")

            summary.append({
                "house": house_id,
                "instance": mains.instance(),
                "key": str(mains.key),
                "label": mains.label(),
                "ac_types": ", ".join(ac_types),
                "has_active": "active" in ac_types,
                "has_apparent": "apparent" in ac_types,
                "site_meter": mains.is_site_meter(),
                "submeter_instances": ", ".join(
                    str(meter.instance()) for meter in elec.submeters().meters
                ),
            })


    return pd.DataFrame(summary)



