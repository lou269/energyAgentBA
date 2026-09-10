# python -m pytest tests/unit/pipeline/test_pipeline_runner.py -v

import pytest

from src.pipeline.pipeline_runner import _parse_configs


def test_parse_configs_rejects_unknown_labels() -> None:
    with pytest.raises(ValueError, match="Unknown config"):
        _parse_configs("SYS0,NOT_A_CONFIG")


def test_parse_configs_returns_the_requested_variants_in_order() -> None:
    configs = _parse_configs("SYS1, SYS0")

    assert list(configs.keys()) == ["SYS1", "SYS0"]