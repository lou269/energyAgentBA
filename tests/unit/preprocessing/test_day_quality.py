# python -m pytest tests/unit/preprocessing/test_day_quality.py -v

import pandas as pd

from src.common.column_naming import imputation_column, treated_column
from src.preprocessing.day_quality import exclude_incomplete_days

TREATED = treated_column("m1")
IMPUTED = imputation_column("m1")


def _frame(index: pd.DatetimeIndex, values: list[float | None], column: str = "m1") -> pd.DataFrame:
    return pd.DataFrame({treated_column(column): values}, index=index)


def _mask(index: pd.DatetimeIndex, imputed: list[bool], column: str = "m1") -> pd.DataFrame:
    return pd.DataFrame({imputation_column(column): imputed}, index=index)


def test_a_gap_longer_than_the_limit_excludes_the_whole_day() -> None:
    index = pd.date_range("2020-01-01", periods=24, freq="1h", tz="UTC")
    values: list[float | None] = [100.0] * 24
    # Stunden 10-13 (4h) fehlen, ueber dem Einzellueckenlimit von 3h
    for hour in range(10, 14):
        values[hour] = None
    treated = _frame(index, values)
    # Stunde 5 war eine erfolgreich imputierte Kurzlücke im selben Tag
    imputed = [False] * 24
    imputed[5] = True
    mask = _mask(index, imputed)

    result_treated, result_mask = exclude_incomplete_days(
        treated, mask,
        local_timezone="UTC", sample_period_hours=1.0,
        max_single_gap_hours=3.0, max_daily_missing_share=0.5,
    )

    assert result_treated[TREATED].isna().all()
    # die vorher als imputiert markierte Stunde 5 darf nach dem Ausschluss nicht mehr als imputiert gelten
    assert not result_mask[IMPUTED].any()


def test_missing_share_alone_excludes_the_day_without_any_single_long_gap() -> None:
    index = pd.date_range("2020-01-01", periods=24, freq="1h", tz="UTC")
    values: list[float | None] = [100.0] * 24
    # drei getrennte 1h-Luecken (Stunden 2, 10, 18), jede einzeln unter dem 3h-Limit,
    # zusammen aber 3/24 = 12.5% > 10% Tagesausfall
    for hour in (2, 10, 18):
        values[hour] = None
    treated = _frame(index, values)
    mask = _mask(index, [False] * 24)

    result_treated, _ = exclude_incomplete_days(
        treated, mask,
        local_timezone="UTC", sample_period_hours=1.0,
        max_single_gap_hours=3.0, max_daily_missing_share=0.10,
    )

    assert result_treated[TREATED].isna().all()


def test_a_day_below_both_thresholds_is_left_untouched() -> None:
    index = pd.date_range("2020-01-01", periods=24, freq="1h", tz="UTC")
    values: list[float | None] = [100.0] * 24
    values[5] = None  # 1h Luecke, 1/24 = 4.2%, unter beiden Schwellen
    treated = _frame(index, values)
    mask = _mask(index, [False] * 24)

    result_treated, result_mask = exclude_incomplete_days(
        treated, mask,
        local_timezone="UTC", sample_period_hours=1.0,
        max_single_gap_hours=3.0, max_daily_missing_share=0.10,
    )

    assert result_treated[TREATED].isna().sum() == 1
    assert result_treated[TREATED].isna().tolist() == [i == 5 for i in range(24)]
    assert not result_mask[IMPUTED].any()


def test_only_the_day_touched_by_the_gap_is_excluded_not_the_whole_series() -> None:
    index = pd.date_range("2020-01-01", periods=48, freq="1h", tz="UTC")
    values: list[float | None] = [100.0] * 48
    for hour in range(10, 14):  # Tag 1, 4h Luecke
        values[hour] = None
    treated = _frame(index, values)
    mask = _mask(index, [False] * 48)

    result_treated, _ = exclude_incomplete_days(
        treated, mask,
        local_timezone="UTC", sample_period_hours=1.0,
        max_single_gap_hours=3.0, max_daily_missing_share=0.5,
    )

    day_one = result_treated[TREATED].iloc[:24]
    day_two = result_treated[TREATED].iloc[24:]
    assert day_one.isna().all()
    assert not day_two.isna().any()


def test_only_the_affected_meter_column_is_excluded() -> None:
    index = pd.date_range("2020-01-01", periods=24, freq="1h", tz="UTC")
    m1_values: list[float | None] = [100.0] * 24
    for hour in range(10, 14):
        m1_values[hour] = None
    m2_values = [50.0] * 24

    treated = pd.DataFrame(
        {treated_column("m1"): m1_values, treated_column("m2"): m2_values},
        index=index,
    )
    mask = pd.DataFrame(
        {imputation_column("m1"): [False] * 24, imputation_column("m2"): [False] * 24},
        index=index,
    )

    result_treated, _ = exclude_incomplete_days(
        treated, mask,
        local_timezone="UTC", sample_period_hours=1.0,
        max_single_gap_hours=3.0, max_daily_missing_share=0.5,
    )

    assert result_treated[treated_column("m1")].isna().all()
    assert not result_treated[treated_column("m2")].isna().any()


def test_day_boundary_follows_local_timezone_not_utc() -> None:
    # Etc/GMT-2 hat (POSIX-Vorzeichenkonvention) Offset UTC+2, der lokale Tageswechsel liegt damit bei UTC 22:00, nicht bei UTC-Mitternacht
    index = pd.date_range("2020-01-01T20:00:00", periods=6, freq="1h", tz="UTC")
    # lokal (UTC+2): 22:00/23:00 (noch 1. Januar), dann 00:00-03:00 (2. Januar)
    values = [100.0, 100.0, None, None, None, None]  # 4h Luecke, komplett am lokalen 2. Januar
    treated = _frame(index, values)
    mask = _mask(index, [False] * 6)

    result_treated, _ = exclude_incomplete_days(
        treated, mask,
        local_timezone="Etc/GMT-2", sample_period_hours=1.0,
        max_single_gap_hours=3.0, max_daily_missing_share=0.9,
    )

    # die Lücke fällt komplett auf den lokalen 2. Januar, der 1. Januar (lokal, nur die ersten zwei UTC-Stunden) bleibt unberührt
    assert not result_treated[TREATED].iloc[:2].isna().any()
    assert result_treated[TREATED].iloc[2:].isna().all()