from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal


CurrencyCode = Literal["USD", "EUR", "JPY"]
VehicleAge = Literal["new", "used"]
FuelType = Literal["petrol", "diesel", "hybrid", "electric"]
UtilMode = Literal["privileged", "commercial"]


@dataclass(frozen=True)
class FuelRule:
    code: FuelType
    duty_basis: Literal["standard", "electric"]


@dataclass(frozen=True)
class DutyNewBand:
    max_value_eur: Decimal
    pct: Decimal
    min_eur_per_cc: Decimal


@dataclass(frozen=True)
class DutyUsedBand:
    max_engine_volume_l: Decimal
    eur_per_cc: Decimal


@dataclass(frozen=True)
class ExciseBand:
    min_hp: int
    max_hp: int
    rate_per_hp: Decimal


@dataclass(frozen=True)
class UtilPrivilegedRate:
    vehicle_age: VehicleAge
    coefficient: Decimal


@dataclass(frozen=True)
class UtilCommercialBand:
    vehicle_age: VehicleAge
    max_engine_volume_l: Decimal
    max_engine_power_hp: int
    coefficient: Decimal


@dataclass(frozen=True)
class RuleSet:
    version: str
    default_exchange_rates: dict[CurrencyCode, Decimal]
    fuel_rules: dict[FuelType, FuelRule]
    new_duty_bands: tuple[DutyNewBand, ...]
    used_duty_bands: tuple[DutyUsedBand, ...]
    excise_bands: tuple[ExciseBand, ...]
    util_base_amount_rub: Decimal
    util_privileged_rates: tuple[UtilPrivilegedRate, ...]
    util_commercial_bands: tuple[UtilCommercialBand, ...]
    vat_rate: Decimal


@dataclass(frozen=True)
class CalculatorInput:
    car_price_foreign: Decimal
    currency: CurrencyCode
    engine_volume: Decimal
    engine_power_hp: int
    vehicle_age: VehicleAge
    fuel_type: FuelType
    is_personal_use: bool
    rule_version: str


@dataclass(frozen=True)
class ResolvedRates:
    currency_to_rub: Decimal
    currency_source: str
    eur_to_rub: Decimal
    eur_source: str

