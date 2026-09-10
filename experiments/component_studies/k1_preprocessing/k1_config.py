from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd


@dataclass(frozen=True)
class K1Variant:
    variant_id: str
    max_availability_gap_hours: int


K1_VARIANTS: tuple[K1Variant, ...] = (
    K1Variant(variant_id="V1_2h", max_availability_gap_hours=2),
    K1Variant(variant_id="V2_10h", max_availability_gap_hours=10),
    K1Variant(variant_id="V3_24h", max_availability_gap_hours=24),
)


@dataclass(frozen=True)
class K1Scenario:
    scenario_id: str
    weekly_seasonality: bool
    yearly_seasonality: bool


# "base" isoliert reinen Datenmengen-Effekt (Trend + Tagesmuster). "seasonal" prüft die im ersten K1-Lauf aufgeworfene Frage,
# ob mehr Historie stärker hilft, sobald Wochen-/
# Jahressaisonalität aktiv ist. V1 hat mit ~227 Tagen weniger als das von Prophet für yearly_seasonality empfohlene volle Jahr; bewusst
# trotzdem mitgefahren, um das Verhalten sichtbar zu machen statt es auszuschliessen
K1_SCENARIOS: tuple[K1Scenario, ...] = (
    K1Scenario(scenario_id="base", weekly_seasonality=False, yearly_seasonality=False),
    K1Scenario(scenario_id="seasonal", weekly_seasonality=True, yearly_seasonality=True),
)

# Festes Validation-Fenster für alle drei Varianten (identisch zu V1s ursprünglichem Split), damit nur die Trainingslänge variiert 
# und nicht zusätzlich der ausgewertete Kalenderzeitraum 
FIXED_VALIDATION_START: pd.Timestamp = pd.Timestamp("2015-12-14 11:00:00", tz="UTC")
FIXED_VALIDATION_END: pd.Timestamp = pd.Timestamp("2016-01-31 23:00:00", tz="UTC")

K1_OUTPUT_ROOT: Path = Path(__file__).resolve().parent / "output"


def k1_variant_output_dir(variant_id: str) -> Path:
    return K1_OUTPUT_ROOT / variant_id


def k1_scenario_output_dir(variant_id: str, scenario_id: str) -> Path:
    return k1_variant_output_dir(variant_id) / scenario_id


