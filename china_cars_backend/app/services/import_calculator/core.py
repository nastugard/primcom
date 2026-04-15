from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal, ROUND_HALF_UP

from app.services.import_calculator.exceptions import CalculatorValidationError
from app.services.import_calculator.types import (
    CalculatorInput,
    DutyNewBand,
    DutyVolumeBand,
    ExciseBand,
    FuelRule,
    RuleSet,
    UtilCommercialBand,
    UtilMode,
    UtilPrivilegedRate,
)


MONEY_QUANT = Decimal("0.01")


def quantize_money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def convert_currency(car_price_foreign: Decimal, exchange_rate: Decimal) -> Decimal:
    return quantize_money(car_price_foreign * exchange_rate)


def convert_price_to_eur(car_price_rub: Decimal, eur_to_rub: Decimal) -> Decimal:
    if eur_to_rub <= 0:
        raise CalculatorValidationError("EUR exchange rate must be greater than zero")
    return (car_price_rub / eur_to_rub).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def select_fuel_rule(rule_set: RuleSet, fuel_type: str) -> FuelRule:
    rule = rule_set.fuel_rules.get(fuel_type)  # type: ignore[arg-type]
    if rule is None:
        raise CalculatorValidationError(
            f"Fuel type '{fuel_type}' is not configured for rule version {rule_set.version}"
        )
    return rule


def select_new_duty_band(rule_set: RuleSet, price_eur: Decimal) -> DutyNewBand:
    bands = rule_set.duty_config.get("new")
    if not bands:
        raise CalculatorValidationError(
            f"Duty config for vehicle_age 'new' is not configured in version {rule_set.version}"
        )
    for band in bands:
        if not isinstance(band, DutyNewBand):
            raise CalculatorValidationError("Invalid duty config for vehicle_age 'new'")
        if price_eur <= band.max_value_eur:
            return band
    raise CalculatorValidationError(
        f"Duty band was not found for vehicle_age 'new' and price_eur={price_eur}"
    )


def select_volume_duty_band(
    rule_set: RuleSet,
    vehicle_age: str,
    engine_volume: Decimal,
) -> DutyVolumeBand:
    bands = rule_set.duty_config.get(vehicle_age)
    if not bands:
        raise CalculatorValidationError(
            f"Duty config for vehicle_age '{vehicle_age}' is not configured in version {rule_set.version}"
        )
    for band in bands:
        if not isinstance(band, DutyVolumeBand):
            raise CalculatorValidationError(
                f"Invalid duty config for vehicle_age '{vehicle_age}'"
            )
        if engine_volume <= band.max_engine_volume_l:
            return band
    raise CalculatorValidationError(
        f"Duty band was not found for vehicle_age '{vehicle_age}' and engine_volume={engine_volume}"
    )


def calculate_duty(
    input_data: CalculatorInput,
    rule_set: RuleSet,
    *,
    car_price_rub: Decimal,
    eur_to_rub: Decimal,
    fuel_rule: FuelRule,
) -> tuple[Decimal, dict[str, object]]:
    price_eur = convert_price_to_eur(car_price_rub, eur_to_rub)

    if fuel_rule.duty_basis == "electric":
        band = select_new_duty_band(rule_set, price_eur)
        duty = quantize_money(car_price_rub * band.pct)
        trace = {
            "strategy": "electric_value_percent",
            "price_eur": float(price_eur),
            "band": {
                "max_value_eur": float(band.max_value_eur),
                "pct": float(band.pct),
            },
        }
        return duty, trace

    engine_cc = input_data.engine_volume * Decimal("1000")
    if engine_cc < 0:
        raise CalculatorValidationError("engine_volume must produce non-negative engine_volume_cc")

    if input_data.vehicle_age == "new":
        band = select_new_duty_band(rule_set, price_eur)
        by_pct = car_price_rub * band.pct
        by_min = engine_cc * band.min_eur_per_cc * eur_to_rub
        duty = quantize_money(max(by_pct, by_min))
        trace = {
            "strategy": "new_unified_rate",
            "price_eur": float(price_eur),
            "vehicle_age": input_data.vehicle_age,
            "band": {
                "max_value_eur": float(band.max_value_eur),
                "pct": float(band.pct),
                "min_eur_per_cc": float(band.min_eur_per_cc),
            },
            "engine_volume_cc": float(engine_cc),
            "by_pct_rub": float(quantize_money(by_pct)),
            "by_min_rub": float(quantize_money(by_min)),
        }
        return duty, trace

    band = select_volume_duty_band(rule_set, input_data.vehicle_age, input_data.engine_volume)
    duty = quantize_money(engine_cc * band.eur_per_cc * eur_to_rub)
    trace = {
        "strategy": "volume_based_eur_per_cc",
        "vehicle_age": input_data.vehicle_age,
        "band": {
            "max_engine_volume_l": float(band.max_engine_volume_l),
            "eur_per_cc": float(band.eur_per_cc),
        },
        "engine_volume_cc": float(engine_cc),
        "price_eur": float(price_eur),
    }
    return duty, trace


def select_excise_band(rule_set: RuleSet, engine_power_hp: int) -> ExciseBand:
    for band in rule_set.excise_bands:
        if band.min_hp <= engine_power_hp < band.max_hp:
            return band
    return rule_set.excise_bands[-1]


def calculate_excise(
    input_data: CalculatorInput,
    rule_set: RuleSet,
) -> tuple[Decimal, dict[str, object]]:
    band = select_excise_band(rule_set, input_data.engine_power_hp)
    excise = quantize_money(Decimal(input_data.engine_power_hp) * band.rate_per_hp)
    trace = {
        "band": asdict(band),
        "engine_power_hp": input_data.engine_power_hp,
    }
    return excise, trace


def determine_util_mode(input_data: CalculatorInput) -> UtilMode:
    if (
        input_data.is_personal_use
        and input_data.engine_power_hp <= 160
        and input_data.engine_volume <= Decimal("3.0")
    ):
        return "privileged"
    return "commercial"


def select_util_privileged_rate(rule_set: RuleSet, vehicle_age: str) -> UtilPrivilegedRate:
    for rate in rule_set.util_privileged_rates:
        if rate.vehicle_age == vehicle_age:
            return rate
    raise CalculatorValidationError(
        f"Privileged util rate is not configured for vehicle_age '{vehicle_age}'"
    )


def select_util_commercial_band(
    rule_set: RuleSet,
    *,
    vehicle_age: str,
    engine_volume: Decimal,
    engine_power_hp: int,
) -> UtilCommercialBand:
    for band in rule_set.util_commercial_bands:
        if band.vehicle_age != vehicle_age:
            continue
        if engine_volume <= band.max_engine_volume_l and engine_power_hp <= band.max_engine_power_hp:
            return band
    raise CalculatorValidationError(
        "Commercial util coefficient is not configured for the provided engine parameters"
    )


def calculate_util(
    input_data: CalculatorInput,
    rule_set: RuleSet,
) -> tuple[Decimal, UtilMode, dict[str, object]]:
    mode = determine_util_mode(input_data)
    base_amount = rule_set.util_base_amount_rub
    if mode == "privileged":
        rate = select_util_privileged_rate(rule_set, input_data.vehicle_age)
        util = quantize_money(base_amount * rate.coefficient)
        trace = {
            "mode": mode,
            "coefficient": float(rate.coefficient),
            "base_amount_rub": float(base_amount),
        }
        return util, mode, trace

    band = select_util_commercial_band(
        rule_set,
        vehicle_age=input_data.vehicle_age,
        engine_volume=input_data.engine_volume,
        engine_power_hp=input_data.engine_power_hp,
    )
    util = quantize_money(base_amount * band.coefficient)
    trace = {
        "mode": mode,
        "band": asdict(band),
        "base_amount_rub": float(base_amount),
    }
    return util, mode, trace


def calculate_vat(
    rule_set: RuleSet,
    *,
    car_price_rub: Decimal,
    duty: Decimal,
    excise: Decimal,
    util: Decimal,
) -> tuple[Decimal, dict[str, object]]:
    vat_base = car_price_rub + duty + excise + util
    vat = quantize_money(vat_base * rule_set.vat_rate)
    trace = {
        "vat_base_rub": float(quantize_money(vat_base)),
        "vat_rate": float(rule_set.vat_rate),
    }
    return vat, trace


def calculate_total(
    *,
    car_price_rub: Decimal,
    duty: Decimal,
    excise: Decimal,
    util: Decimal,
    vat: Decimal,
) -> Decimal:
    return quantize_money(car_price_rub + duty + excise + util + vat)
