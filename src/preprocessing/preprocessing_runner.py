# python -m src.preprocessing.preprocessing_runner

from dataclasses import dataclass
import logging

import pandas as pd

from src.common.timestamps import local_daily_mean
from src.pipeline.io import df_to_csv, read_canonical_frame
from src.common.windows import window_names
from src.config.config_forecasting import NumericalAnalysisConfig, PreprocessingConfig
from src.config.project_config import ProjectConfig, ensure_project_directories
from src.preprocessing.day_quality import exclude_incomplete_days
from src.preprocessing.gap_treatment import apply_gap_treatment
from src.preprocessing.plausibility_check import build_plausibility_flags
from src.preprocessing.split import build_split_manifest


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PreprocessingResult:
    treated_hourly: pd.DataFrame
    treated_daily: pd.DataFrame
    imputation_mask_hourly: pd.DataFrame
    plausibility_hourly: pd.DataFrame


def run_preprocessing(
    data_hourly: pd.DataFrame,
    quality_hourly: pd.DataFrame,
    config: PreprocessingConfig,
    local_timezone: str,
    *,
    sample_period_hours_hourly: float,
) -> PreprocessingResult:
    plausibility_hourly = build_plausibility_flags(
        data_hourly,
        quality_hourly,
        stuck_value_min_hours=config.stuck_value_min_hours,
        sample_period_hours=sample_period_hours_hourly,
        resolution="hourly",
    )

    treated_hourly, imputation_mask_hourly = apply_gap_treatment(
        data_hourly,
        quality_hourly,
        max_gap_intervals=config.max_imputation_gap_hourly,
        resolution="hourly",
        method=config.gap_treatment_method,
    )

    treated_hourly, imputation_mask_hourly = exclude_incomplete_days(
        treated_hourly,
        imputation_mask_hourly,
        local_timezone=local_timezone,
        sample_period_hours=sample_period_hours_hourly,
        max_single_gap_hours=config.max_imputation_gap_hourly,
        max_daily_missing_share=config.max_daily_missing_share,
    )

    treated_daily = local_daily_mean(treated_hourly, local_timezone)
    daily_index = pd.DatetimeIndex(treated_daily.index)
    treated_daily.index = daily_index.tz_convert("UTC").rename("timestamp")

    return PreprocessingResult(
        treated_hourly=treated_hourly,
        treated_daily=treated_daily,
        imputation_mask_hourly=imputation_mask_hourly,
        plausibility_hourly=plausibility_hourly,
    )


class PreprocessingRunner:
    def __init__(
        self,
        project_config: ProjectConfig | None = None,
        preprocessing_config: PreprocessingConfig | None = None,
        numerical_analysis_config: NumericalAnalysisConfig | None = None,
    ) -> None:
        self.project_config = project_config or ProjectConfig()
        self.preprocessing_config = preprocessing_config or PreprocessingConfig()
        self.numerical_analysis_config = (
            numerical_analysis_config or NumericalAnalysisConfig()
        )

    def run(self) -> None:
        ensure_project_directories(self.project_config)

        split_manifests = []

        for window in window_names():
            logger.info("Starting preprocessing for window %s...", window)

            result = run_preprocessing(
                read_canonical_frame(
                    self.project_config, "canonical_data_hourly", window
                ),
                read_canonical_frame(
                    self.project_config, "canonical_quality_hourly", window
                ),
                self.preprocessing_config,
                self.project_config.timezone,
                sample_period_hours_hourly=self.numerical_analysis_config.sample_period_hours_hourly,
            )

            output_directory = self.project_config.preprocessing_output_dir / window
            output_directory.mkdir(parents=True, exist_ok=True)

            for name, frame in vars(result).items():
                df_to_csv(frame.reset_index(), output_directory, name)

            hourly_index = pd.DatetimeIndex(result.treated_hourly.index)
            split_manifests.append(
                build_split_manifest(window, hourly_index, self.project_config.timezone)
            )

        df_to_csv(
            pd.concat(split_manifests, ignore_index=True),
            self.project_config.preprocessing_output_dir,
            "split_manifest",
        )


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    PreprocessingRunner().run()


if __name__ == "__main__":
    main()
