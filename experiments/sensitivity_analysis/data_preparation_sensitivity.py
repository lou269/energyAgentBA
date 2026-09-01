# python -m experiments.sensitivity_analysis.data_preparation_sensitivity

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from hashlib import sha256
import logging
from pathlib import Path
import subprocess

import pandas as pd

from src.config.data_preparation_config import DataPreparationConfig
from src.config.project_config import ProjectConfig
from src.data_preparation.selected_candidate_validation import select_candidate_role
from src.pipeline.io import save_json

logger = logging.getLogger(__name__)

DEFAULT_CONFIG = DataPreparationConfig()

# Vergleichsvarianten, keine final begründeten Werte.
MIN_MAINS_COVERAGE_SHARE_VARIANTS = (0.90, DEFAULT_CONFIG.min_mains_coverage_share, 1.00)
MIN_MAINS_VALID_DURATION_DAYS_VARIANTS = (30.0, DEFAULT_CONFIG.min_mains_valid_duration_days, 90.0)

REQUIRED_COLUMNS = {
    "selection_role",
    "candidate_id",
    "grid_complete",
    "mains_coverage_share",
    "mains_valid_duration_days",
}


def file_sha256(path: Path) -> str:
    digest = sha256()

    with path.open("rb") as file:
        while chunk := file.read(1024 * 1024):
            digest.update(chunk)

    return digest.hexdigest()


def evaluate_thresholds(
    candidate_metrics: pd.DataFrame,
    *,
    min_coverage_share: float,
    min_valid_duration_days: float,
) -> pd.DataFrame:
    results = candidate_metrics[
        ["selection_role", "candidate_id", "grid_complete", "mains_coverage_share", "mains_valid_duration_days"]
    ].copy()

    results["validation_passed"] = (
        results["grid_complete"].eq(True)
        & results["mains_coverage_share"].ge(min_coverage_share)
        & results["mains_valid_duration_days"].ge(min_valid_duration_days)
    )

    selected_role = select_candidate_role(results)

    results.insert(0, "min_mains_coverage_share", min_coverage_share)
    results.insert(1, "min_mains_valid_duration_days", min_valid_duration_days)
    results["selected_canonical_role"] = selected_role

    return results


def main() -> None:
    logging.basicConfig(level=logging.INFO)

    project_config = ProjectConfig()
    candidate_validation_path = project_config.validation_output_dir / "candidate_validation.csv"

    if not candidate_validation_path.exists():
        raise FileNotFoundError(f"Missing data-preparation output: {candidate_validation_path}")

    candidate_metrics = pd.read_csv(candidate_validation_path)

    missing_columns = REQUIRED_COLUMNS - set(candidate_metrics.columns)
    if missing_columns:
        raise ValueError("candidate_validation.csv is missing columns: " + ", ".join(sorted(missing_columns)))

    candidate_metrics["mains_coverage_share"] = pd.to_numeric(candidate_metrics["mains_coverage_share"], errors="raise")
    candidate_metrics["mains_valid_duration_days"] = pd.to_numeric(
        candidate_metrics["mains_valid_duration_days"], errors="raise"
    )

    logger.info("Evaluating mains coverage thresholds...")

    coverage_results = pd.concat(
        [
            evaluate_thresholds(
                candidate_metrics,
                min_coverage_share=coverage_share,
                min_valid_duration_days=DEFAULT_CONFIG.min_mains_valid_duration_days,
            )
            for coverage_share in MIN_MAINS_COVERAGE_SHARE_VARIANTS
        ],
        ignore_index=True,
    )

    logger.info("Evaluating mains duration thresholds...")

    duration_results = pd.concat(
        [
            evaluate_thresholds(
                candidate_metrics,
                min_coverage_share=DEFAULT_CONFIG.min_mains_coverage_share,
                min_valid_duration_days=duration_days,
            )
            for duration_days in MIN_MAINS_VALID_DURATION_DAYS_VARIANTS
        ],
        ignore_index=True,
    )

    created_at = datetime.now(timezone.utc)
    run_id = created_at.strftime("%Y%m%dT%H%M%SZ")

    output_dir = project_config.output_dir / "sensitivity_analysis" / "data_preparation" / run_id
    output_dir.mkdir(parents=True, exist_ok=False)

    coverage_results.to_csv(output_dir / "mains_coverage_summary.csv", index=False)
    duration_results.to_csv(output_dir / "mains_valid_duration_summary.csv", index=False)

    git_commit = subprocess.run(
        ["git", "-C", str(project_config.project_root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    git_dirty = bool(
        subprocess.run(
            ["git", "-C", str(project_config.project_root), "status", "--porcelain"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    )

    save_json(
        {
            "run_id": run_id,
            "created_at_utc": created_at.isoformat(),
            "dataset_release": project_config.dataset_release,
            "dataset_doi": project_config.dataset_doi,
            "data_preparation_config": asdict(DEFAULT_CONFIG),
            "variants": {
                "T-011_min_mains_coverage_share": MIN_MAINS_COVERAGE_SHARE_VARIANTS,
                "T-012_min_mains_valid_duration_days": MIN_MAINS_VALID_DURATION_DAYS_VARIANTS,
            },
            "fixed_parameters": {
                "coverage_analysis": {
                    "min_mains_valid_duration_days": DEFAULT_CONFIG.min_mains_valid_duration_days,
                },
                "duration_analysis": {
                    "min_mains_coverage_share": DEFAULT_CONFIG.min_mains_coverage_share,
                },
            },
            "selection_rules": {
                "coverage": (
                    "Reject variants that leave no valid candidate. "
                    "Final selection additionally requires the downstream effect of missing values."
                ),
                "duration": (
                    "Require sufficient time for train, validation and test periods "
                    "while retaining a fallback candidate where possible."
                ),
            },
            "input": {
                "path": str(candidate_validation_path),
                "sha256": file_sha256(candidate_validation_path),
            },
            "code_version": {
                "git_commit": git_commit,
                "git_dirty": git_dirty,
            },
        },
        output_dir / "data_preparation_sensitivity_manifest.json",
    )

    logger.info("Results saved to %s", output_dir)


if __name__ == "__main__":
    main()