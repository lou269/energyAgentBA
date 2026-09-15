# python -m pytest tests/unit/proposal_experiments/e3_saisonality -v

from experiments.proposal_experiments.e_config import (
    SEASONALITY_PROPHET_VARIANTS,
    SeasonalityExperimentConfig,
)


def test_s0_s1_differ_only_in_yearly_seasonality() -> None:
    by_id = {variant.model_id: variant for variant in SEASONALITY_PROPHET_VARIANTS}

    assert set(by_id) == {"S0", "S1"}
    assert by_id["S0"].yearly_seasonality is False
    assert by_id["S1"].yearly_seasonality is True

    for variant in by_id.values():
        assert variant.weekly_seasonality is True
        assert variant.history_mode == "expanding"


def test_experiment_id_is_e3() -> None:
    assert SeasonalityExperimentConfig().experiment_id == "E3"
