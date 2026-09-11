# python -m experiments.sensitivity_analysis.data_selection_sensitivity

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import logging

import pandas as pd

from data_preparation.selection.auxiliary_appliance_selection import build_auxiliary_appliance_selection
from old.old_src_vor_umbau.provisional_selection import build_candidate_selection_outputs
from src.config.config_nilmtk import AnalysisConfig
from src.config.project_config import ProjectConfig
from src.pipeline.io import save_json
from src.pipeline.provenance import file_sha256, git_output

logger = logging.getLogger(__name__)

DEFAULT_CONFIG = AnalysisConfig()

# Vergleichsvarianten, keine final begründeten Werte.
MIN_LONGEST_SEGMENT_DAYS_VARIANTS = (
    30.0,
    DEFAULT_CONFIG.min_longest_segment_days,
    90.0,
)

MIN_AUXILIARY_WINDOW_COVERAGE_SHARE_VARIANTS = (
    DEFAULT_CONFIG.min_auxiliary_window_coverage_share,
    0.80,
    0.95,
)


def evaluate_segment_duration(
    candidate_profiles: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    summary_rows = []
    decision_frames = []

    for min_segment_days in MIN_LONGEST_SEGMENT_DAYS_VARIANTS:
        selection, decisions = build_candidate_selection_outputs(
            candidate_profiles=candidate_profiles,
            min_longest_segment_days=min_segment_days,
        )

        selected_by_role = (
            selection.set_index("selection_role")["candidate_id"]
            if not selection.empty
            else pd.Series(dtype="object")
        )

        summary_rows.append(
            {
                "min_longest_segment_days": min_segment_days,
                "eligible_candidate_count": int(decisions["eligible_for_selection"].sum()),
                "primary_candidate_id": selected_by_role.get("primary"),
                "fallback_candidate_id": selected_by_role.get("fallback"),
            }
        )
        decision_frames.append(decisions)

    return pd.DataFrame(summary_rows), pd.concat(decision_frames, ignore_index=True)


def evaluate_auxiliary_coverage(
    candidate_profiles: pd.DataFrame,
    provisional_selection: pd.DataFrame,
    channel_registry: pd.DataFrame,
    channel_quality: pd.DataFrame,
    good_sections: pd.DataFrame,
) -> pd.DataFrame:
    rows = []

    for coverage_share in MIN_AUXILIARY_WINDOW_COVERAGE_SHARE_VARIANTS:
        auxiliary_selection = build_auxiliary_appliance_selection(
            candidate_profiles=candidate_profiles,
            provisional_selection=provisional_selection,
            channel_registry=channel_registry,
            channel_quality=channel_quality,
            good_sections=good_sections,
        )

        for selected_candidate in provisional_selection.itertuples(index=False):
            candidate_appliances = auxiliary_selection.loc[
                auxiliary_selection["candidate_id"].eq(selected_candidate.candidate_id)
                & auxiliary_selection["selected_window_coverage_share"].ge(coverage_share)
            ].sort_values("availability_rank")

            rows.append(
                {
                    "min_window_coverage_share": coverage_share,
                    "selection_role": selected_candidate.selection_role,
                    "candidate_id": selected_candidate.candidate_id,
                    "available_auxiliary_channel_count": len(candidate_appliances),
                    "available_meter_keys": "|".join(candidate_appliances["meter_key"].astype(str)),
                }
            )

    return pd.DataFrame(rows)


def main() -> None:
    logging.basicConfig(level=logging.INFO)

    project_config = ProjectConfig()
    created_at = datetime.now(timezone.utc)
    run_id = created_at.strftime("%Y%m%dT%H%M%SZ")

    input_paths = {
        "candidate_profiles": project_config.selection_output_dir / "profiles.csv",
        "channel_registry": project_config.meta_output_dir / "channel_registry.csv",
        "channel_quality": project_config.diagnostics_output_dir / "channel_quality.csv",
        "good_sections": project_config.diagnostics_output_dir / "good_sections.csv",
    }

    missing_inputs = [path for path in input_paths.values() if not path.exists()]
    if missing_inputs:
        raise FileNotFoundError(
            "Missing analysis outputs: " + ", ".join(str(path) for path in missing_inputs)
        )

    candidate_profiles = pd.read_csv(input_paths["candidate_profiles"])
    channel_registry = pd.read_csv(input_paths["channel_registry"])
    channel_quality = pd.read_csv(input_paths["channel_quality"])
    good_sections = pd.read_csv(input_paths["good_sections"])

    # build_candidate_selection_outputs erwartet run_id aktuell indirekt als Spalte für das Entscheidungsprotokoll
    candidate_profiles["run_id"] = run_id

    logger.info("Evaluating minimum segment duration...")

    segment_results, segment_decisions = evaluate_segment_duration(candidate_profiles)

    # Die Segmentdauer bleibt fixiert, damit anschließen ausschließlich die Hilfsgeräte-Abdeckung verändert wird
    default_selection, _ = build_candidate_selection_outputs(
        candidate_profiles=candidate_profiles,
        min_longest_segment_days=DEFAULT_CONFIG.min_longest_segment_days,
    )

    logger.info("Evaluating auxiliary coverage...")

    auxiliary_results = evaluate_auxiliary_coverage(
        candidate_profiles=candidate_profiles,
        provisional_selection=default_selection,
        channel_registry=channel_registry,
        channel_quality=channel_quality,
        good_sections=good_sections,
    )

    output_dir = project_config.output_dir / "sensitivity_analysis" / "data_selection" / run_id
    output_dir.mkdir(parents=True, exist_ok=False)

    segment_results.to_csv(
        output_dir / "segment_duration_summary.csv",
        index=False,
    )

    segment_decisions.to_csv(
        output_dir / "segment_duration_decisions.csv",
        index=False,
    )

    auxiliary_results.to_csv(
        output_dir / "auxiliary_coverage_summary.csv",
        index=False,
    )

    git_commit = git_output(
        project_config.project_root,
        "rev-parse",
        "HEAD",
    )

    git_dirty = bool(
        git_output(
            project_config.project_root,
            "status",
            "--porcelain",
        )
    )

    save_json(
        {
            "run_id": run_id,
            "created_at_utc": created_at.isoformat(),
            "dataset_release": project_config.dataset_release,
            "dataset_doi": project_config.dataset_doi,
            "analysis_config": asdict(DEFAULT_CONFIG),
            "variants": {
                "min_longest_segment_days": MIN_LONGEST_SEGMENT_DAYS_VARIANTS,
                "min_auxiliary_window_coverage_share": MIN_AUXILIARY_WINDOW_COVERAGE_SHARE_VARIANTS,
            },
            "inputs": {
                name: {
                    "path": str(path),
                    "sha256": file_sha256(path),
                }
                for name, path in input_paths.items()
            },
            "code_version": {
                "git_commit": git_commit,
                "git_dirty": git_dirty,
            },
        },
        output_dir / "data_selection_sensitivity_manifest.json",
    )

    logger.info("Results saved to %s", output_dir)


if __name__ == "__main__":
    main()