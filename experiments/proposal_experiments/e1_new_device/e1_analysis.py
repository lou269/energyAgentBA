# conda run -n forecasting-env python -m experiments.proposal_experiments.e1_new_device.e1_analysis
# optional: <run_directory> [control_run_directory] als Argumente

import sys
from pathlib import Path

import pandas as pd

from experiments.proposal_experiments.e_config import E1Config
from experiments.proposal_experiments.shared_analysis import (
    compare_mae_before_after_effect,
    summarize_classification_detection,
    summarize_classification_rate,
    summarize_mae_before_after,
)
from src.common.timestamps import parse_utc_timestamp
from src.pipeline.io import df_to_csv, find_run_directory, resolve_run_directory

OUTPUT_DIR = Path(__file__).parent / "output"


def _resolve_control_run_directory() -> Path | None:
    # anders als der Hauptlauf optional, ohne Kontrolllauf fällt nur der Treatment/Control-Vergleich weg
    if len(sys.argv) > 2:
        return Path(sys.argv[2])

    latest_control_run = find_run_directory(OUTPUT_DIR, prefix="e1_control")
    return latest_control_run[1] if latest_control_run is not None else None


def _compare_classification_rates(treatment: pd.DataFrame, control: pd.DataFrame) -> pd.DataFrame:
    """Stellt gegenüber, wie oft jede Config jede Klassifikation nach Cutover vergibt - mit vs. ohne echte Geräteänderung"""
    merged = treatment.merge(
        control, on=["config", "classification"], how="outer", suffixes=("_treatment", "_control"),
    ).fillna({"rate_treatment": 0.0, "rate_control": 0.0})
    merged["rate_delta"] = merged["rate_treatment"] - merged["rate_control"]

    columns = ["config", "classification", "rate_treatment", "rate_control", "rate_delta"]
    return merged[columns].sort_values(["config", "classification"]).reset_index(drop=True)


def main() -> None:
    run_directory = resolve_run_directory(OUTPUT_DIR, "e1", sys.argv[1] if len(sys.argv) > 1 else None)
    control_run_directory = _resolve_control_run_directory()
    e1_config = E1Config()
    cutover_time = parse_utc_timestamp(e1_config.cutover_time, "E1Config.cutover_time")

    comparison = pd.read_csv(run_directory / "comparison_summary.csv", parse_dates=["decision_time"])

    detection = summarize_classification_detection(comparison, cutover_time, "new_pattern")
    mae_before_after = summarize_mae_before_after(comparison, cutover_time)

    df_to_csv(detection, run_directory, "e1_new_pattern_detection")
    df_to_csv(mae_before_after, run_directory, "e1_mae_before_after")

    print(detection.to_string(index=False))
    print()
    print(mae_before_after.to_string(index=False))

    if control_run_directory is None:
        print()
        print(f"no e1_control_XXX run found under {OUTPUT_DIR} - skipping treatment/control comparison.")
        return

    control_comparison = pd.read_csv(control_run_directory / "comparison_summary.csv", parse_dates=["decision_time"])

    control_detection = summarize_classification_detection(control_comparison, cutover_time, "new_pattern")
    control_mae_before_after = summarize_mae_before_after(control_comparison, cutover_time)
    df_to_csv(control_detection, control_run_directory, "e1_new_pattern_detection")
    df_to_csv(control_mae_before_after, control_run_directory, "e1_mae_before_after")

    treatment_rates = summarize_classification_rate(comparison, cutover_time)
    control_rates = summarize_classification_rate(control_comparison, cutover_time)
    rate_comparison = _compare_classification_rates(treatment_rates, control_rates)
    df_to_csv(rate_comparison, run_directory, "e1_treatment_vs_control_classification_rate")

    mae_effect = compare_mae_before_after_effect(mae_before_after, control_mae_before_after)
    df_to_csv(mae_effect, run_directory, "e1_treatment_vs_control_mae_effect")

    print()
    print(f"treatment/control classification rate ({run_directory.name} vs. {control_run_directory.name}):")
    print(rate_comparison.to_string(index=False))
    print()
    print("treatment/control MAE effect (diff-in-diff, W):")
    print(mae_effect.to_string(index=False))


if __name__ == "__main__":
    main()



