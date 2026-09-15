# conda run -n nilmtk-env python -m experiments.proposal_experiments.e1_new_device.e1_device_check

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from experiments.proposal_experiments.e_config import E1Config
from experiments.proposal_experiments.shared_nilmtk import load_nilmtk_context, load_treated_mains_series
from src.config.config_nilmtk import AnalysisConfig, DataPreparationConfig
from src.config.project_config import ProjectConfig
from src.data_preparation.auxiliary_appliance_selection import build_auxiliary_appliance_selection
from src.pipeline.io import df_to_csv

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path(__file__).parent / "output"


def build_weekly_device_summary(device_hourly: pd.Series, coverage_mask: pd.Series) -> pd.DataFrame:
    """Wochenweise Aktivität/Abdeckung eines Gerätekanals -> Grundlage für die Cutover-Wahl"""
    # active_hours: Stunden mit Leistung > 10W (grober Betriebsindikator, kein harter Schwellenwert)
    is_active = device_hourly > 10.0

    weekly = pd.DataFrame(
        {
            "power_w_mean": device_hourly.resample("7D").mean(),
            "power_w_max": device_hourly.resample("7D").max(),
            "active_hours": is_active.resample("7D").sum(),
            "coverage_share": coverage_mask.resample("7D").mean(),
        }
    )

    return weekly.reset_index().rename(columns={"timestamp": "week_start"})


class DeviceCheckRunner:
    def __init__(
        self,
        project_config: ProjectConfig | None = None,
        data_config: DataPreparationConfig | None = None,
        analysis_config: AnalysisConfig | None = None,
        e1_config: E1Config | None = None,
    ) -> None:
        self.project_config = project_config or ProjectConfig()
        self.data_config = data_config or DataPreparationConfig()
        self.analysis_config = analysis_config or AnalysisConfig()
        self.e1_config = e1_config or E1Config()

    def run(self) -> None:
        
        device_meter_key = self.e1_config.device_meter_key

        context = load_nilmtk_context(self.project_config)
        mains_data = load_treated_mains_series(self.project_config, context.mains_meter_key)

        logger.info("Checking %s coverage over the mains candidate window %s to %s...", device_meter_key, context.window_start, context.window_end)


        selection = build_auxiliary_appliance_selection(
            context.dataset,
            context.channel_registry,
            context.channel_quality,
            mains_data,
            house=context.house,
            window_start=context.window_start,
            window_end=context.window_end,
            canonical_ac_type=self.data_config.canonical_ac_type,
            min_coverage_share=self.data_config.min_coverage_share,
            min_sampling_share=self.analysis_config.min_auxiliary_window_coverage_share,
            restrict_to_meter_keys={device_meter_key},
        )

        if device_meter_key not in selection.data_hourly.columns:
            raise ValueError(f"{device_meter_key} did not pass the auxiliary appliance filters over the candidate window.")

        device_hourly = selection.data_hourly[device_meter_key]
        coverage_mask = selection.quality_hourly[f"{device_meter_key}_coverage_mask"]
        weekly = build_weekly_device_summary(device_hourly, coverage_mask)

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        df_to_csv(selection.ranking, OUTPUT_DIR, "e1_device_quality")
        df_to_csv(device_hourly.rename("power_w").reset_index(), OUTPUT_DIR, "h1_m5_hourly")
        df_to_csv(weekly, OUTPUT_DIR, "h1_m5_weekly_coverage")

        overall_coverage = float(coverage_mask.mean())
        logger.info(
            "Done: %d hourly rows, overall coverage_share=%.3f. See %s for a week-by-week breakdown to pick the cutover.",
            len(device_hourly), overall_coverage, OUTPUT_DIR / "h1_m5_weekly_coverage.csv"
        )



def main() -> None:
    logging.basicConfig(level=logging.INFO)
    DeviceCheckRunner().run()

if __name__ == "__main__":
    main()