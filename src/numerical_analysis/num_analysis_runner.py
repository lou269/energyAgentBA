# python -m src.numerical_analysis.num_analysis_runner
# jeder Lauf landet in einem eigenen Ordner output/numerical_analysis/an_<nummer>/

from dataclasses import asdict, dataclass
import logging
from time import perf_counter

import pandas as pd

from src.common.column_naming import plausibility_column, treated_column
from src.pipeline.io import df_to_csv, next_sequential_number, save_json
from src.config.config_forecasting import ForecastingConfig, NumericalAnalysisConfig
from src.config.project_config import ProjectConfig, ensure_project_directories
from src.numerical_analysis.anomaly_detection import build_anomaly_detection
from src.numerical_analysis.multi_scale_analysis import build_multi_scale_analysis
from src.numerical_analysis.numerical_analysis_run_manifest import build_numerical_analysis_run_manifest


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class NumericalAnalysisResult:
    anomaly_15min: pd.DataFrame
    anomaly_hourly: pd.DataFrame


def run_numerical_analysis(
    treated_15min: pd.DataFrame,
    treated_hourly: pd.DataFrame,
    plausibility_15min: pd.DataFrame,
    plausibility_hourly: pd.DataFrame,
    split_manifest: pd.DataFrame,
    meter_key: str,
    config: NumericalAnalysisConfig,
    local_timezone: str,
) -> NumericalAnalysisResult:
    target_column = treated_column(meter_key)
    implausible_column = plausibility_column(meter_key)

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

    analysis_15min = build_multi_scale_analysis(
        train_data=train_15min,
        validation_data=validation_15min,
        test_data=test_15min,
        target_column=target_column,
        short_term_window=config.short_term_window_15min,
        sample_period_hours=config.sample_period_hours_15min,
        long_term_window=config.long_term_window_15min,
        min_daily_reference_samples=config.min_daily_reference_samples,
        min_weekly_reference_samples=config.min_weekly_reference_samples,
        trend_threshold=config.trend_threshold,
        min_reference_power_w=config.min_reference_power_w,
        local_timezone=local_timezone,
    )

    anomaly_15min = build_anomaly_detection(
        analysis_results=analysis_15min,
        min_reference_samples=config.min_reference_samples,
        min_residual_std_w=config.min_residual_std_w,
        unusual_threshold=config.unusual_threshold,
        strong_anomaly_threshold=config.strong_anomaly_threshold,
        sample_period_hours=config.sample_period_hours_15min,
        local_timezone=local_timezone,
    )

    anomaly_15min["value_implausible"] = plausibility_15min[implausible_column].reindex(anomaly_15min.index)

    analysis_hourly = build_multi_scale_analysis(
        train_data=train_hourly,
        validation_data=validation_hourly,
        test_data=test_hourly,
        target_column=target_column,
        short_term_window=config.short_term_window_hourly,
        sample_period_hours=config.sample_period_hours_hourly,
        long_term_window=config.long_term_window_hourly,
        min_daily_reference_samples=config.min_daily_reference_samples,
        min_weekly_reference_samples=config.min_weekly_reference_samples,
        trend_threshold=config.trend_threshold,
        min_reference_power_w=config.min_reference_power_w,
        local_timezone=local_timezone,
    )

    anomaly_hourly = build_anomaly_detection(
        analysis_results=analysis_hourly,
        min_reference_samples=config.min_reference_samples,
        min_residual_std_w=config.min_residual_std_w,
        unusual_threshold=config.unusual_threshold,
        strong_anomaly_threshold=config.strong_anomaly_threshold,
        sample_period_hours=config.sample_period_hours_hourly,
        local_timezone=local_timezone,
    )

    anomaly_hourly["value_implausible"] = plausibility_hourly[implausible_column].reindex(anomaly_hourly.index)

    return NumericalAnalysisResult(anomaly_15min=anomaly_15min, anomaly_hourly=anomaly_hourly)


class NumericalAnalysisRunner:
    def __init__(
        self,
        project_config: ProjectConfig | None = None,
        analysis_config: NumericalAnalysisConfig | None = None,
        forecasting_config: ForecastingConfig | None = None,
    ) -> None:
        self.project_config = project_config or ProjectConfig()
        self.analysis_config = analysis_config or NumericalAnalysisConfig()
        self.forecasting_config = forecasting_config or ForecastingConfig()

    def run(self) -> None:
        ensure_project_directories(self.project_config)
        run_started = perf_counter()

        logger.info("Starting numerical analysis...")

        treated_15min_path = self.project_config.preprocessing_output_dir / "treated_15min.csv"
        treated_hourly_path = self.project_config.preprocessing_output_dir / "treated_hourly.csv"
        plausibility_15min_path = self.project_config.preprocessing_output_dir / "plausibility_15min.csv"
        plausibility_hourly_path = self.project_config.preprocessing_output_dir / "plausibility_hourly.csv"
        split_manifest_path = self.project_config.preprocessing_output_dir / "split_manifest.csv"

        treated_15min = pd.read_csv(
            treated_15min_path,
            parse_dates=["timestamp"],
            index_col="timestamp",
        )

        treated_hourly = pd.read_csv(
            treated_hourly_path,
            parse_dates=["timestamp"],
            index_col="timestamp",
        )

        plausibility_15min = pd.read_csv(
            plausibility_15min_path,
            parse_dates=["timestamp"],
            index_col="timestamp",
        )

        plausibility_hourly = pd.read_csv(
            plausibility_hourly_path,
            parse_dates=["timestamp"],
            index_col="timestamp",
        )

        split_manifest = pd.read_csv(
            split_manifest_path,
            parse_dates=["start", "end"],
        )

        canonical_manifest_path = self.project_config.canonical_output_dir / "canonical_manifest.csv"
        canonical_manifest = pd.read_csv(canonical_manifest_path)

        candidate_id = str(canonical_manifest["candidate_id"].iloc[0])
        meter_key = str(canonical_manifest["meter_key"].iloc[0])

        logger.info("Building 15-minute and hourly analysis...")

        result = run_numerical_analysis(
            treated_15min=treated_15min,
            treated_hourly=treated_hourly,
            plausibility_15min=plausibility_15min,
            plausibility_hourly=plausibility_hourly,
            split_manifest=split_manifest,
            meter_key=meter_key,
            config=self.analysis_config,
            local_timezone=self.forecasting_config.timezone,
        )

        run_number = next_sequential_number(self.project_config.numerical_analysis_output_dir, prefix="an")
        run_id = f"an_{run_number:03d}"
        run_directory = self.project_config.numerical_analysis_output_dir / run_id

        if run_directory.exists():
            raise FileExistsError(f"Numerical analysis run directory already exists: {run_directory}")

        run_directory.mkdir(parents=True, exist_ok=False)

        df_to_csv(
            result.anomaly_15min.reset_index(),
            run_directory,
            "anomaly_scores_15min",
        )

        df_to_csv(
            result.anomaly_hourly.reset_index(),
            run_directory,
            "anomaly_scores_hourly",
        )

        manifest = build_numerical_analysis_run_manifest(
            project_root=self.project_config.project_root,
            run_id=run_id,
            candidate_id=candidate_id,
            config_values={**asdict(self.analysis_config), "local_timezone": self.forecasting_config.timezone},
            input_paths={
                "treated_15min": treated_15min_path,
                "treated_hourly": treated_hourly_path,
                "plausibility_15min": plausibility_15min_path,
                "plausibility_hourly": plausibility_hourly_path,
                "split_manifest": split_manifest_path,
                "canonical_manifest": canonical_manifest_path,
            },
            output_paths={
                "anomaly_scores_15min": run_directory / "anomaly_scores_15min.csv",
                "anomaly_scores_hourly": run_directory / "anomaly_scores_hourly.csv",
            },
            runtime_seconds=perf_counter() - run_started,
        )

        save_json(manifest, run_directory / "run_manifest.json")

        logger.info("Numerical analysis completed: run_id=%s.", run_id)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    NumericalAnalysisRunner().run()


if __name__ == "__main__":
    main()