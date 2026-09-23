# python -m pytest tests/unit/pipeline/test_comparison_harness.py -v

from dataclasses import replace
import math
from pathlib import Path

import numpy as np
import pandas as pd

from src.config.config_forecasting import ComparisonConfig, LLMConfig, SYS_VARIANTS
from src.config.project_config import ProjectConfig
from src.llm.client import ModelMetadata
from src.pipeline.comparison_harness import ScenarioData, build_scenario_from_split_manifest, run_comparison

COMPARISON_CONFIG = ComparisonConfig()

PROJECT_ROOT = ProjectConfig().project_root

EXPECTED_COLUMNS = {
    "decision_time",
    "config",
    "classification",
    "adaption_action",
    "adaption_reason",
    "retrained",
    "reference_reset",
    "mae_w",
    "error",
}


class _AlwaysEmptyClient:
    def generate_json(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        output_schema: dict[str, object],
        temperature: float,
        presence_penalty: float,
        seed: int | None,
        num_predict: int,
        num_ctx: int,
        think: bool,
        keep_alive: int | str,
    ) -> str:
        return ""

    def get_model_metadata(self, model: str) -> ModelMetadata:
        return {"name": model, "digest": None}

    def unload_model(self, model: str) -> None:
        pass

    def close(self) -> None:
        pass


def _synthetic_scenario(
    *,
    hours: int = 360,
    coldstart_days: int = 6,
    decision_count: int = 2
) -> ScenarioData:
    index = pd.date_range("2024-01-01", periods=hours, freq="1h", tz="UTC")
    hour_of_day = index.hour.to_numpy()
    values = 200.0 + 50.0 * np.sin(2 * np.pi * hour_of_day / 24) + 10.0
    series = pd.Series(values, index=index, name="target")

    decision_times = tuple(
        pd.date_range(
            start=series.index[0] + pd.Timedelta(days=coldstart_days + 1),
            periods=decision_count,
            freq="24h",
        )
    )

    return ScenarioData(
        target_series=series,
        coldstart_days=coldstart_days,
        decision_times=decision_times,
        calendar_events=(),
        calendar_source_available=False,
        calendar_source="none",
    )


def test_build_scenario_from_split_manifest_uses_given_coldstart_days() -> None:
    index = pd.date_range("2024-01-01", periods=100, freq="1h", tz="UTC")
    treated_hourly = pd.DataFrame({"target": range(100)}, index=index)
    split_manifest = pd.DataFrame(
        [
            {"frequency": "hourly", "split": "train", "start": index[0], "end": index[69], "row_count": 70},
            {"frequency": "hourly", "split": "validation", "start": index[70], "end": index[84], "row_count": 15},
            {"frequency": "hourly", "split": "test", "start": index[85], "end": index[99], "row_count": 15},
        ]
    )

    scenario = build_scenario_from_split_manifest(
        treated_hourly, split_manifest, "target", coldstart_days=2, local_timezone="UTC"
    )

    assert scenario.coldstart_days == 2
    assert scenario.target_series.index[-1] == index[99]
    # cycle_start liegt 2 Kalendertage nach Datenbeginn (index[48]),
    # decision_times[0] einen vollen lokalen Kalendertag danach, sonst ist new_observations beim ersten Zyklus-Aufruf leer
    assert scenario.decision_times[0] == index[72]
    assert scenario.decision_times[-1] <= index[99]
    assert all(second - first == pd.Timedelta(hours=24) for first, second in zip(scenario.decision_times, scenario.decision_times[1:]))


def test_build_scenario_from_split_manifest_uses_local_calendar_days() -> None:
    index = pd.date_range("2024-01-01T05:00:00Z", periods=120, freq="1h")
    treated_hourly = pd.DataFrame({"target": range(120)}, index=index)
    split_manifest = pd.DataFrame(
        [
            {"frequency": "hourly", "split": "train", "start": index[0], "end": index[89], "row_count": 90},
            {"frequency": "hourly", "split": "validation", "start": index[90], "end": index[104], "row_count": 15},
            {"frequency": "hourly", "split": "test", "start": index[105], "end": index[119], "row_count": 15},
        ]
    )

    scenario = build_scenario_from_split_manifest(
        treated_hourly, split_manifest, "target", coldstart_days=2, local_timezone="America/New_York"
    )

    cycle_start_local = index[48].tz_convert("America/New_York")
    decision_time_local = scenario.decision_times[0].tz_convert("America/New_York")

    assert cycle_start_local.hour == 0
    assert decision_time_local.hour == 0
    assert scenario.decision_times[0] == cycle_start_local.tz_convert("UTC") + pd.Timedelta(hours=24)


def test_build_scenario_from_split_manifest_integrates_with_run_comparison(tmp_path: Path) -> None:
    # Regressionstest für einen echten Bug: decision_times[0] == cycle_start ließ new_observations
    # im ersten Zyklus leer sein, weil state.history schon bis cycle_start - 1h reicht
    hours = 480
    index = pd.date_range("2024-01-01", periods=hours, freq="1h", tz="UTC")
    hour_of_day = index.hour.to_numpy()
    values = 200.0 + 50.0 * np.sin(2 * np.pi * hour_of_day / 24) + 10.0
    treated_hourly = pd.DataFrame({"target": values}, index=index)

    train_end_idx, validation_end_idx = 399, 439
    split_manifest = pd.DataFrame(
        [
            {"frequency": "hourly", "split": "train", "start": index[0], "end": index[train_end_idx], "row_count": train_end_idx + 1},
            {
                "frequency": "hourly",
                "split": "validation",
                "start": index[train_end_idx + 1],
                "end": index[validation_end_idx],
                "row_count": validation_end_idx - train_end_idx,
            },
            {
                "frequency": "hourly",
                "split": "test",
                "start": index[validation_end_idx + 1],
                "end": index[-1],
                "row_count": hours - validation_end_idx - 1,
            },
        ]
    )

    scenario = build_scenario_from_split_manifest(
        treated_hourly, split_manifest, "target", coldstart_days=6, local_timezone="Europe/London"
    )
    result = run_comparison(
        scenario,
        {"SYS0": SYS_VARIANTS["SYS0"]},
        tmp_path,
        PROJECT_ROOT,
        local_timezone="Europe/London",
        max_consecutive_llm_failures=COMPARISON_CONFIG.max_consecutive_llm_failures,
        max_total_llm_failures=COMPARISON_CONFIG.max_total_llm_failures,
        calendar_lookback_days=COMPARISON_CONFIG.calendar_lookback_days,
        calendar_lookahead_days=COMPARISON_CONFIG.calendar_lookahead_days,
    )

    assert len(result) == len(scenario.decision_times)
    assert result["mae_w"].apply(math.isfinite).all()


def test_run_comparison_produces_one_row_per_decision_and_config(tmp_path: Path) -> None:
    scenario = _synthetic_scenario()
    configs = {"SYS0": SYS_VARIANTS["SYS0"], "SYS1": SYS_VARIANTS["SYS1"]}

    result = run_comparison(
        scenario,
        configs,
        tmp_path,
        PROJECT_ROOT,
        local_timezone="Europe/London",
        max_consecutive_llm_failures=COMPARISON_CONFIG.max_consecutive_llm_failures,
        max_total_llm_failures=COMPARISON_CONFIG.max_total_llm_failures,
        calendar_lookback_days=COMPARISON_CONFIG.calendar_lookback_days,
        calendar_lookahead_days=COMPARISON_CONFIG.calendar_lookahead_days,
    )

    assert len(result) == len(scenario.decision_times) * len(configs)
    assert EXPECTED_COLUMNS.issubset(result.columns)
    assert (tmp_path / "comparison_summary.csv").is_file()
    assert (tmp_path / "run_manifest.json").is_file()


def test_run_comparison_off_mode_never_classifies_or_adapts(tmp_path: Path) -> None:
    scenario = _synthetic_scenario()
    configs = {"SYS0": SYS_VARIANTS["SYS0"]}

    result = run_comparison(
        scenario,
        configs,
        tmp_path,
        PROJECT_ROOT,
        local_timezone="Europe/London",
        max_consecutive_llm_failures=COMPARISON_CONFIG.max_consecutive_llm_failures,
        max_total_llm_failures=COMPARISON_CONFIG.max_total_llm_failures,
        calendar_lookback_days=COMPARISON_CONFIG.calendar_lookback_days,
        calendar_lookahead_days=COMPARISON_CONFIG.calendar_lookahead_days,
    )

    assert result["classification"].isna().all()
    assert (result["adaption_action"] == "none").all()


def test_run_comparison_fixed_train_retrains_only_once(tmp_path: Path) -> None:
    scenario = _synthetic_scenario(decision_count=3)
    configs = {"SYS0": SYS_VARIANTS["SYS0"]}

    result = run_comparison(
        scenario,
        configs,
        tmp_path,
        PROJECT_ROOT,
        local_timezone="Europe/London",
        max_consecutive_llm_failures=COMPARISON_CONFIG.max_consecutive_llm_failures,
        max_total_llm_failures=COMPARISON_CONFIG.max_total_llm_failures,
        calendar_lookback_days=COMPARISON_CONFIG.calendar_lookback_days,
        calendar_lookahead_days=COMPARISON_CONFIG.calendar_lookahead_days,
    ).sort_values("decision_time")

    assert result["retrained"].tolist() == [True, False, False]


def test_run_comparison_expanding_variant_retrains_every_cycle(tmp_path: Path) -> None:
    scenario = _synthetic_scenario(decision_count=3)
    configs = {"SYS1": SYS_VARIANTS["SYS1"]}

    result = run_comparison(
        scenario,
        configs,
        tmp_path,
        PROJECT_ROOT,
        local_timezone="Europe/London",
        max_consecutive_llm_failures=COMPARISON_CONFIG.max_consecutive_llm_failures,
        max_total_llm_failures=COMPARISON_CONFIG.max_total_llm_failures,
        calendar_lookback_days=COMPARISON_CONFIG.calendar_lookback_days,
        calendar_lookahead_days=COMPARISON_CONFIG.calendar_lookahead_days,
    ).sort_values("decision_time")

    assert result["retrained"].tolist() == [True, True, True]


def test_run_comparison_mae_is_finite(tmp_path: Path) -> None:
    scenario = _synthetic_scenario()
    configs = {"SYS0": SYS_VARIANTS["SYS0"], "SYS1": SYS_VARIANTS["SYS1"]}

    result = run_comparison(
        scenario,
        configs,
        tmp_path,
        PROJECT_ROOT,
        local_timezone="Europe/London",
        max_consecutive_llm_failures=COMPARISON_CONFIG.max_consecutive_llm_failures,
        max_total_llm_failures=COMPARISON_CONFIG.max_total_llm_failures,
        calendar_lookback_days=COMPARISON_CONFIG.calendar_lookback_days,
        calendar_lookahead_days=COMPARISON_CONFIG.calendar_lookahead_days,
    )

    for mae_w in result["mae_w"]:
        assert isinstance(mae_w, float)
        assert math.isfinite(mae_w)


def test_run_comparison_with_target_imputed_shorter_than_forecast_horizon(tmp_path: Path) -> None:
    scenario_base = _synthetic_scenario()
    target_imputed = pd.Series(
        False,
        index=scenario_base.target_series.index[: 24 * scenario_base.coldstart_days],
        dtype=bool,
    )
    scenario = replace(scenario_base, target_imputed=target_imputed)

    result = run_comparison(
        scenario,
        {"SYS0": SYS_VARIANTS["SYS0"]},
        tmp_path,
        PROJECT_ROOT,
        local_timezone="Europe/London",
        max_consecutive_llm_failures=COMPARISON_CONFIG.max_consecutive_llm_failures,
        max_total_llm_failures=COMPARISON_CONFIG.max_total_llm_failures,
        calendar_lookback_days=COMPARISON_CONFIG.calendar_lookback_days,
        calendar_lookahead_days=COMPARISON_CONFIG.calendar_lookahead_days,
    )

    assert result["mae_w"].apply(math.isfinite).all()


def _series_with_a_sustained_jump(hours: int, jump_hour: int, *, seed: int = 1) -> pd.Series:
    
    index = pd.date_range("2024-01-01", periods=hours, freq="1h", tz="UTC")
    day_of_series = np.arange(hours) // 24
    jitter_by_day = np.random.default_rng(seed).normal(0.0, 5.0, size=day_of_series.max() + 1)
    values = 200.0 + 50.0 * np.sin(2 * np.pi * index.hour.to_numpy() / 24) + jitter_by_day[day_of_series]
    values[jump_hour:] += 300.0
    return pd.Series(values, index=index, name="target")


def test_run_comparison_survives_llm_inference_failures(tmp_path: Path) -> None:
    # Ollama liefert gelegentlich ungültige Ausgaben -> Fehlschlag darf Vergleichslauf nciht abbrechen
    hours, coldstart_days = 24 * 30, 24
    series = _series_with_a_sustained_jump(hours, 24 * coldstart_days)
    scenario = ScenarioData(
        target_series=series,
        coldstart_days=coldstart_days,
        decision_times=tuple(
            pd.date_range(start=series.index[0] + pd.Timedelta(days=coldstart_days + 1), periods=3, freq="24h")
        ),
        calendar_events=(),
        calendar_source_available=False,
        calendar_source="none",
    )

    base_config = SYS_VARIANTS["SYS1"]
    config = replace(
        base_config,
        llm_mode="real",
        llm_config=LLMConfig(model="test-model", max_attempts=1),
        numerical_analysis_config=replace(
            base_config.numerical_analysis_config,
            min_daily_reference_samples=5,
            min_weekday_reference_samples=1,
        ),
    )

    result = run_comparison(
        scenario,
        {"SYS_TEST": config},
        tmp_path,
        PROJECT_ROOT,
        local_timezone="Europe/London",
        llm_prompt="irrelevant for this test",
        llm_client=_AlwaysEmptyClient(),
        max_consecutive_llm_failures=COMPARISON_CONFIG.max_consecutive_llm_failures,
        max_total_llm_failures=COMPARISON_CONFIG.max_total_llm_failures,
        calendar_lookback_days=COMPARISON_CONFIG.calendar_lookback_days,
        calendar_lookahead_days=COMPARISON_CONFIG.calendar_lookahead_days,
    )

    assert len(result) == len(scenario.decision_times)
    assert (result["error"] != "").all()
    assert result["classification"].isna().all()
    assert result["mae_w"].isna().all()


def test_run_comparison_records_rule_based_explanation(tmp_path: Path) -> None:
    # garantiert eine echte Anomalie pro Zyklus -> rule_based_classify wird aufgerufen und liefert eine reasoning, die hier als "explanation" landen muss
    hours, coldstart_days = 24 * 30, 24
    series = _series_with_a_sustained_jump(hours, 24 * coldstart_days, seed=2)
    scenario = ScenarioData(
        target_series=series,
        coldstart_days=coldstart_days,
        decision_times=tuple(
            pd.date_range(start=series.index[0] + pd.Timedelta(days=coldstart_days + 1), periods=2, freq="24h")
        ),
        calendar_events=(),
        calendar_source_available=False,
        calendar_source="none",
    )

    base_config = SYS_VARIANTS["SYS2"]
    config = replace(
        base_config,
        numerical_analysis_config=replace(base_config.numerical_analysis_config, min_daily_reference_samples=5),
    )

    result = run_comparison(
        scenario,
        {"SYS2": config},
        tmp_path,
        PROJECT_ROOT,
        local_timezone="Europe/London",
        max_consecutive_llm_failures=COMPARISON_CONFIG.max_consecutive_llm_failures,
        max_total_llm_failures=COMPARISON_CONFIG.max_total_llm_failures,
        calendar_lookback_days=COMPARISON_CONFIG.calendar_lookback_days,
        calendar_lookahead_days=COMPARISON_CONFIG.calendar_lookahead_days,
    )

    classified = result.loc[result["classification"].notna()]
    assert not classified.empty
    assert (classified["explanation"] != "").all()