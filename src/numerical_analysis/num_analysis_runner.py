# python -m src.numerical_analysis.num_analysis_runner

import logging

import pandas as pd

from src.pipeline.io import df_to_csv
from src.config.numerical_analysis_config import NumericalAnalysisConfig
from src.config.project_config import ProjectConfig, ensure_project_directories
from src.numerical_analysis.anomaly_detection import build_anomaly_detection
from src.numerical_analysis.multi_scale_analysis import build_multi_scale_analysis


logger = logging.getLogger(__name__)


class NumericalAnalysisRunner:
    def __init__(self, project_config=None, analysis_config=None):
        self.project_config = project_config or ProjectConfig()
        self.analysis_config = analysis_config or NumericalAnalysisConfig()

    def run(self):
        ensure_project_directories(self.project_config)

        logger.info("Starting numerical analysis...")

        treated_15min = pd.read_csv(
            self.project_config.preprocessing_output_dir / "treated_15min.csv",
            parse_dates=["timestamp"],
            index_col="timestamp",
        )

        treated_hourly = pd.read_csv(
            self.project_config.preprocessing_output_dir / "treated_hourly.csv",
            parse_dates=["timestamp"],
            index_col="timestamp",
        )

        split_manifest = pd.read_csv(
            self.project_config.preprocessing_output_dir / "split_manifest.csv",
            parse_dates=["start", "end"],
        )

        canonical_manifest = pd.read_csv(
            self.project_config.canonical_output_dir / "canonical_manifest.csv"
        )

        target_column = canonical_manifest.loc[
            canonical_manifest["channel_role"] == "mains", "meter_key"
        ].iloc[0]

        split_15min = split_manifest[
            split_manifest["frequency"] == "15min"
        ].set_index("split")

        train_15min = treated_15min.loc[
            split_15min.loc["train", "start"]:split_15min.loc["train", "end"]
        ]

        validation_15min = treated_15min.loc[
            split_15min.loc["validation", "start"]:
            split_15min.loc["validation", "end"]
        ]

        test_15min = treated_15min.loc[
            split_15min.loc["test", "start"]:split_15min.loc["test", "end"]
        ]

        split_hourly = split_manifest[
            split_manifest["frequency"] == "hourly"
        ].set_index("split")

        train_hourly = treated_hourly.loc[
            split_hourly.loc["train", "start"]:split_hourly.loc["train", "end"]
        ]

        validation_hourly = treated_hourly.loc[
            split_hourly.loc["validation", "start"]:
            split_hourly.loc["validation", "end"]
        ]

        test_hourly = treated_hourly.loc[
            split_hourly.loc["test", "start"]:split_hourly.loc["test", "end"]
        ]

        logger.info("Building 15-minute analysis...")

        analysis_15min = build_multi_scale_analysis(
            train_data=train_15min,
            validation_data=validation_15min,
            test_data=test_15min,
            target_column=target_column,
            short_term_window=self.analysis_config.short_term_window_15min,
            sample_period_hours=self.analysis_config.sample_period_hours_15min,
            long_term_window=self.analysis_config.long_term_window_15min,
            min_daily_reference_samples=self.analysis_config.min_daily_reference_samples,
            min_weekly_reference_samples=self.analysis_config.min_weekly_reference_samples,
            trend_threshold=self.analysis_config.trend_threshold,
        )
        
        anomaly_15min = build_anomaly_detection(
            analysis_results=analysis_15min,
            min_reference_samples=self.analysis_config.min_reference_samples,
            unusual_threshold=self.analysis_config.unusual_threshold,
            strong_anomaly_threshold=self.analysis_config.strong_anomaly_threshold,
        )

        logger.info("Building hourly analysis...")

        analysis_hourly = build_multi_scale_analysis(
            train_data=train_hourly,
            validation_data=validation_hourly,
            test_data=test_hourly,
            target_column=target_column,
            short_term_window=self.analysis_config.short_term_window_hourly,
            sample_period_hours=self.analysis_config.sample_period_hours_hourly,
            long_term_window=self.analysis_config.long_term_window_hourly,
            min_daily_reference_samples=self.analysis_config.min_daily_reference_samples,
            min_weekly_reference_samples=self.analysis_config.min_weekly_reference_samples,
            trend_threshold=self.analysis_config.trend_threshold,
        )

        anomaly_hourly = build_anomaly_detection(
            analysis_results=analysis_hourly,
            min_reference_samples=self.analysis_config.min_reference_samples,
            unusual_threshold=self.analysis_config.unusual_threshold,
            strong_anomaly_threshold=self.analysis_config.strong_anomaly_threshold,
        )

        df_to_csv(
            anomaly_15min.reset_index(),
            self.project_config.numerical_analysis_output_dir,
            "anomaly_scores_15min",
        )

        df_to_csv(
            anomaly_hourly.reset_index(),
            self.project_config.numerical_analysis_output_dir,
            "anomaly_scores_hourly",
        )

        logger.info("Numerical analysis completed.")


def main():
    logging.basicConfig(level=logging.INFO)
    NumericalAnalysisRunner().run()


if __name__ == "__main__":
    main()