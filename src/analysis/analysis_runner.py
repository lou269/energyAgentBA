from __future__ import annotations

import logging

import pandas as pd

from src.analysis.selection.timeframe_selection import select_common_timeframe
from src.analysis.selection.channel_selection import build_channel_selection
from src.analysis.eda.io import df_to_csv
from src.analysis.analysis_config import AnalysisConfig
from src.analysis.eda.metadata_exploration import check_ac_types, inspect_mains
from src.analysis.eda.channel_quality import build_channel_quality
from src.analysis.eda.house_quality import build_house_quality 
from src.config.project_config import ProjectConfig, ensure_project_directories
from src.analysis.eda.plots import build_channel_quality_plots

from nilmtk import DataSet

logger = logging.getLogger(__name__)

class AnalysisRunner:
    def __init__(self, project_config: ProjectConfig | None = None, eda_config: AnalysisConfig | None = None) -> None:
        self.project_config = project_config or ProjectConfig()
        self.eda_config = eda_config or AnalysisConfig()


    def run(self) -> None:
        ensure_project_directories(self.project_config)
        
        logger.info("Starting EDA...")
        dataset=DataSet(self.project_config.processed_dir / "ukdale.h5")
        
        '''
        df_summary_mains = inspect_mains(dataset)
        
        
        df_to_csv(
            df=df_summary_mains,
            output_path=self.project_config.meta_output_dir,
            filename="mains_summary"
        )
        
        df_summary_ac_types = check_ac_types(dataset)
         
        df_to_csv(
            df=df_summary_ac_types,
            output_path=self.project_config.meta_output_dir,
            filename="ac_types_summary"
        )
        
        channel_quality_df = build_channel_quality(
            dataset=dataset,
            canonical_ac_type=self.eda_config.canonical_ac_type,
            min_duration_days=self.eda_config.min_duration_days,
            min_longest_good_section_days=self.eda_config.min_longest_good_section_days,
            min_sample_count=self.eda_config.min_sample_count,
            min_mean_power=self.eda_config.min_mean_power,
            max_zero_share=self.eda_config.max_zero_share,
            max_median_sample_period_seconds=self.eda_config.max_median_sample_period_seconds,
            max_p99_sample_period_seconds=self.eda_config.max_p99_sample_period_seconds,
            max_longest_gap_seconds=self.eda_config.max_longest_gap_seconds,
            reject_negative_values=self.eda_config.reject_negative_values,
        )
        
        df_to_csv(
            df=channel_quality_df,
            output_path=self.project_config.eda_output_dir,
            filename="channel_quality_summary"
        )
        
        house_quality_df = build_house_quality(
            channel_quality=channel_quality_df,
            min_usable_channels=self.eda_config.min_usable_channels,
        )
        
        
        df_to_csv(
            df=house_quality_df,
            output_path=self.project_config.eda_output_dir,
            filename="house_quality_summary"
        )
        
        
        channel_selection_df = build_channel_selection(
            channel_quality=channel_quality_df,
            house_quality = house_quality_df

        )
        
        df_to_csv(
            df=channel_selection_df,
            output_path=self.project_config.eda_output_dir,
            filename="channel_selection_summary"
        )
        

        logger.info("EDA completed.")
        
        selected_timeframe_df = select_common_timeframe(
            selected_channels=channel_selection_df,
            min_overlap_days=180,
        )

        df_to_csv(
            df=selected_timeframe_df,
            output_path=self.project_config.eda_output_dir,
            filename="selected_timeframe",
        )
        '''
        channel_quality_df = pd.read_csv(self.project_config.eda_output_dir / "channel_quality.csv")
        channel_selection_df = pd.read_csv(self.project_config.eda_output_dir / "channel_selection.csv")
        
        build_channel_quality_plots(
            channel_quality=channel_quality_df,
            selected_channels=channel_selection_df,
            output_dir=self.project_config.plots_output_dir,
            min_overlap_days=180,
            max_dropout_rate=0.10,
        )
        
def main() -> None:
    logging.basicConfig(level=logging.INFO)
    AnalysisRunner().run()
    

if __name__ == "__main__":
    main()        
