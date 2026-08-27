from __future__ import annotations

from inspect import signature

from src.analysis.inventory.channel_registry import (
    CHANNEL_REGISTRY_COLUMNS,
)
from src.analysis.selection.auxiliary_appliance_selection import (
    AUXILIARY_AVAILABILITY_COLUMNS,
)
from src.analysis.selection.candidate_profiling import (
    PROFILE_COLUMNS,
)
from src.analysis.selection.provisional_selection import (
    SELECTION_COLUMNS,
)
from src.data_preparation.selected_data import (
    REQUIRED_COLUMNS,
    build_selected_data,
)


ANALYSIS_OUTPUT_COLUMNS = {
    "candidate_profiles": set(PROFILE_COLUMNS),
    "provisional_selection": set(SELECTION_COLUMNS),
    "auxiliary_selection": set(AUXILIARY_AVAILABILITY_COLUMNS),
    "channel_registry": set(CHANNEL_REGISTRY_COLUMNS),
}


def test_analysis_outputs_cover_required_columns() -> None:
    for artifact, required_columns in REQUIRED_COLUMNS.items():
        missing_columns = (
            required_columns
            - ANALYSIS_OUTPUT_COLUMNS[artifact]
        )

        assert not missing_columns, (
            f"{artifact} violates the Analysis -> Data Preparation "
            f"contract. Missing columns: {sorted(missing_columns)}"
        )


def test_build_selected_data_accepts_runner_signature() -> None:
    signature(build_selected_data).bind(
        dataset=object(),
        candidate_profiles=object(),
        provisional_selection=object(),
        auxiliary_selection=object(),
        channel_registry=object(),
        sample_period=6,
        canonical_ac_type="active",
        include_fallback=True,
        chunksize=None,
    )