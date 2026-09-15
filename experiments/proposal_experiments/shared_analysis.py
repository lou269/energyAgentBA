import pandas as pd

def summarize_classification_detection(
    comparison: pd.DataFrame,
    event_time: pd.Timestamp,
    target_classification: str,
) -> pd.DataFrame:
    """Ab wann klassifiziert jede Config die Tage nach event_time als target_classification, wie oft wird adaptiert"""
    post_event = comparison.loc[comparison["decision_time"] >= event_time]

    rows: list[dict[str, object]] = []

    for config, group in post_event.groupby("config"):
        matches = group.loc[group["classification"] == target_classification]
        first_detection = matches["decision_time"].min() if not matches.empty else pd.NaT

        rows.append(
            {
                "config": config,
                "post_event_days": len(group),
                "target_classification": target_classification,
                "target_classification_days": len(matches),
                "first_detection": first_detection,
                "days_to_first_detection": (first_detection - event_time).total_seconds() / 86400 if pd.notna(first_detection) else float("nan"),
                "adaption_count": int((group["adaption_action"] != "none").sum())
            }
        )


    return pd.DataFrame(rows).sort_values("config").reset_index(drop=True)



def summarize_mae_before_after(comparison: pd.DataFrame, event_time: pd.Timestamp) -> pd.DataFrame:
    """Mittlerer/Median mae_w vor vs. nach event_time"""
    comparison = comparison.dropna(subset=["mae_w"]).copy()
    comparison["period"] = "before_event"
    comparison.loc[comparison["decision_time"] >= event_time, "period"] = "after_event"

    return (
        comparison.groupby(["config", "period"])["mae_w"]
        .agg(mean_mae_w="mean", median_mae_w="median", day_count="count")
        .reset_index()
        .sort_values(["config", "period"])
        .reset_index(drop=True)
    )