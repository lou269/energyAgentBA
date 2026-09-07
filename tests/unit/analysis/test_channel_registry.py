# python -m pytest tests/unit/analysis/test_channel_registry.py -v

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

from src.analysis.channel_registry import CHANNEL_REGISTRY_COLUMNS, build_channel_registry


def _appliance(appliance_type: str | None) -> SimpleNamespace:
    return SimpleNamespace(identifier=SimpleNamespace(type=appliance_type))


def _meter(
    instance: int,
    key: str,
    is_site_meter: bool,
    ac_types: list[str],
    appliances: list[str | None] | None = None,
    sample_period: float | None = 6.0,
) -> Mock:
    meter = Mock()
    meter.instance.return_value = instance
    meter.key = key
    meter.is_site_meter.return_value = is_site_meter
    meter.available_ac_types.return_value = ac_types
    meter.appliances = [_appliance(name) for name in (appliances or [])]
    meter.device = {"sample_period": sample_period} if sample_period is not None else {}
    return meter


def _dataset(meters: list[Mock]) -> Mock:
    elec = Mock()
    elec.meters = meters
    building = Mock()
    building.elec = elec
    dataset = Mock()
    dataset.buildings = {1: building}
    return dataset


def test_empty_dataset_returns_empty_frame_with_columns() -> None:
    dataset = Mock()
    dataset.buildings = {}

    result = build_channel_registry(dataset, canonical_ac_type="active")

    assert result.empty
    assert list(result.columns) == CHANNEL_REGISTRY_COLUMNS


def test_meters_are_classified_and_sorted_by_house_meter_type_instance() -> None:
    mains = _meter(1, "H1-M1", is_site_meter=True, ac_types=["active"])
    submeter_canonical = _meter(2, "H1-M2", is_site_meter=False, ac_types=["active"])
    submeter_non_canonical = _meter(3, "H1-M3", is_site_meter=False, ac_types=["apparent"])
    dataset = _dataset([submeter_non_canonical, mains, submeter_canonical])

    result = build_channel_registry(dataset, canonical_ac_type="active")

    assert result["meter_instance"].tolist() == [1, 2, 3]
    assert result["meter_type"].tolist() == ["mains", "submeter", "submeter"]
    assert result["has_canonical_ac_type"].tolist() == [True, True, False]


def test_appliance_names_are_deduplicated_sorted_and_joined() -> None:
    meter = _meter(
        2,
        "H1-M2",
        is_site_meter=False,
        ac_types=["active"],
        appliances=["kettle", "fridge", "kettle", None],
    )
    dataset = _dataset([meter])

    result = build_channel_registry(dataset, canonical_ac_type="active")

    assert result.loc[0, "appliances"] == "fridge, kettle"


def test_ac_type_lookup_failure_falls_back_to_empty_list() -> None:
    meter = _meter(1, "H1-M1", is_site_meter=True, ac_types=[])
    meter.available_ac_types.side_effect = Exception("no ac type data")
    dataset = _dataset([meter])

    result = build_channel_registry(dataset, canonical_ac_type="active")

    assert result.loc[0, "ac_types"] == ""
    assert result.loc[0, "has_canonical_ac_type"] == False


