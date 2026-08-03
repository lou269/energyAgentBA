from __future__ import annotations

import pandas as pd

    
def build_house_quality(
    channel_quality: pd.DataFrame,
    min_usable_channels: int,
) -> pd.DataFrame:
    rows = []

    for house_id, group in channel_quality.groupby("house"):
        mains_rows = group[group["meter_type"] == "mains"]
        mains = mains_rows.iloc[0].to_dict() if not mains_rows.empty else {}

        active_submeters = group[(group["meter_type"] == "submeter") & (group["has_canonical_ac_type"])]

        usable_submeters = group[(group["meter_type"] == "submeter") & (group["usable_for_active_pipeline"])]

        has_canonical_mains = bool(mains.get("has_canonical_ac_type", False))
        usable_submeter_count = len(usable_submeters)

        rows.append({
            "house": house_id,
            "mains_instance": mains.get("meter_instance"),
            "mains_ac_types": mains.get("ac_types"),
            "has_canonical_ac_type_mains": has_canonical_mains,
            "mains_start": mains.get("start"),
            "mains_end": mains.get("end"),
            "mains_duration_days": mains.get("duration_days"),
            "mains_good_duration_days": mains.get("good_duration_days"),
            "mains_longest_good_section_days": mains.get("longest_good_section_days"),
            "meters_total": len(group),
            "active_submeter_count": len(active_submeters),
            "usable_submeter_count": usable_submeter_count,
            "eligible_for_active_pipeline": (
                has_canonical_mains
                and usable_submeter_count >= min_usable_channels
            ),
        })

    return pd.DataFrame(rows)