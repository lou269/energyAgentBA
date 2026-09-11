# python -m experiments.scenarios.g5_measurement_error.inject_measurement_error
#
# Baut keine echten Pipeline-Outputs um. Liest die realen kanonischen Stunden-Daten,
# korrumpiert genau eine Stunde (negative Leistung = physikalisch unmöglich für einen
# reinen Verbrauchszähler) und lässt Gap-Treatment/Analyse/Anomalie-Erkennung auf dieser
# Kopie laufen. decision_time liegt bewusst außerhalb der simulierten Urlaubsfenster aus
# experiments/scenarios/calendar_events.json, damit der G5-Testfall nicht mit G2/absence
# vermischt wird.

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.config.config_forecasting import NumericalAnalysisConfig, PreprocessingConfig
from src.config.project_config import ProjectConfig
from src.numerical_analysis.anomaly_detection import build_anomaly_detection
from src.numerical_analysis.multi_scale_analysis import build_multi_scale_analysis
from src.preprocessing.gap_treatment import apply_gap_treatment
from src.preprocessing.plausibility_check import build_plausibility_flags


DECISION_TIME = pd.Timestamp("2016-01-10T11:00:00+00:00")
FAULT_VALUE_W = -50.0
STUCK_VALUE_MIN_HOURS = 6.0

OUTPUT_DIR = Path(__file__).parent


def main() -> None:
    project_config = ProjectConfig()
    preprocessing_config = PreprocessingConfig()
    analysis_config = NumericalAnalysisConfig()

    data = pd.read_csv(
        project_config.canonical_output_dir / "canonical_data_hourly.csv",
        parse_dates=["timestamp"],
        index_col="timestamp",
    )
    quality = pd.read_csv(
        project_config.canonical_output_dir / "canonical_quality_hourly.csv",
        parse_dates=["timestamp"],
        index_col="timestamp",
    )

    canonical_manifest = pd.read_csv(project_config.canonical_output_dir / "canonical_manifest.csv")
    target_column = str(canonical_manifest["meter_key"].iloc[0])

    split_manifest = pd.read_csv(
        project_config.preprocessing_output_dir / "split_manifest.csv",
        parse_dates=["start", "end"],
    )

    split_hourly = split_manifest[split_manifest["frequency"] == "hourly"].set_index("split")

    analysis_timestamp = DECISION_TIME - pd.Timedelta(hours=1)

    if analysis_timestamp not in data.index:
        raise ValueError(f"{analysis_timestamp} is not a real timestamp in canonical_data_hourly.csv.")

    corrupted_data = data.copy()
    corrupted_data.loc[analysis_timestamp, target_column] = FAULT_VALUE_W

    corrupted_quality = quality.copy()
    corrupted_quality.loc[analysis_timestamp, f"{target_column}_coverage_mask"] = True

    plausibility = build_plausibility_flags(
        corrupted_data,
        corrupted_quality,
        stuck_value_min_hours=STUCK_VALUE_MIN_HOURS,
        sample_period_hours=analysis_config.sample_period_hours_hourly,
    )

    treated, _imputation_mask = apply_gap_treatment(
        corrupted_data,
        corrupted_quality,
        max_gap_intervals=preprocessing_config.max_imputation_gap_hourly,
        method=preprocessing_config.gap_treatment_method,
    )

    train_data = treated.loc[split_hourly.loc["train", "start"]:split_hourly.loc["train", "end"]]
    validation_data = treated.loc[split_hourly.loc["validation", "start"]:split_hourly.loc["validation", "end"]]
    test_data = treated.loc[split_hourly.loc["test", "start"]:split_hourly.loc["test", "end"]]

    analysis = build_multi_scale_analysis(
        train_data=train_data,
        validation_data=validation_data,
        test_data=test_data,
        target_column=target_column,
        short_term_window=analysis_config.short_term_window_hourly,
        sample_period_hours=analysis_config.sample_period_hours_hourly,
        long_term_window=analysis_config.long_term_window_hourly,
        min_daily_reference_samples=analysis_config.min_daily_reference_samples,
        min_weekly_reference_samples=analysis_config.min_weekly_reference_samples,
        trend_threshold=analysis_config.trend_threshold,
        min_reference_power_w=analysis_config.min_reference_power_w,
    )

    anomaly = build_anomaly_detection(
        analysis_results=analysis,
        min_reference_samples=analysis_config.min_reference_samples,
        min_residual_std_w=analysis_config.min_residual_std_w,
        unusual_threshold=analysis_config.unusual_threshold,
        strong_anomaly_threshold=analysis_config.strong_anomaly_threshold,
        sample_period_hours=analysis_config.sample_period_hours_hourly,
    )

    anomaly["value_implausible"] = plausibility[target_column].reindex(anomaly.index)

    analysis_row = anomaly.loc[analysis_timestamp]

    print(analysis_row)

    output_file = OUTPUT_DIR / "corrupted_analysis_row.csv"
    pd.DataFrame([analysis_row]).to_csv(output_file, index=False)

    print(f"\nCorrupted analysis row saved to {output_file}")


if __name__ == "__main__":
    main()
