from __future__ import annotations

from decimal import Decimal

from app.services.import_calculator.adapters import resolve_exchange_rates
from app.services.import_calculator.config import get_rule_set
from app.services.import_calculator.core import (
    calculate_duty,
    calculate_excise,
    calculate_total,
    calculate_util,
    calculate_vat,
    convert_currency,
    quantize_money,
    select_fuel_rule,
)
from app.services.import_calculator.types import CalculatorInput


async def calculate_import_cost(
    input_data: CalculatorInput,
    *,
    exchange_rate_override: Decimal | None = None,
    debug: bool = False,
) -> dict[str, object]:
    rule_set = get_rule_set(input_data.rule_version)
    fuel_rule = select_fuel_rule(rule_set, input_data.fuel_type)
    rates = await resolve_exchange_rates(
        currency=input_data.currency,
        rule_set=rule_set,
        exchange_rate_override=exchange_rate_override,
    )

    car_price_rub = convert_currency(input_data.car_price_foreign, rates.currency_to_rub)
    duty, duty_trace = calculate_duty(
        input_data,
        rule_set,
        car_price_rub=car_price_rub,
        eur_to_rub=rates.eur_to_rub,
        fuel_rule=fuel_rule,
    )
    excise, excise_trace = calculate_excise(input_data, rule_set)
    util, util_mode, util_trace = calculate_util(input_data, rule_set)
    if input_data.is_legal_entity:
        vat, vat_trace = calculate_vat(
            rule_set,
            car_price_rub=car_price_rub,
            duty=duty,
            excise=excise,
            util=util,
        )
    else:
        vat = Decimal("0.00")
        vat_trace = {
            "vat_base_rub": float(quantize_money(car_price_rub + duty + excise + util)),
            "vat_rate": float(rule_set.vat_rate),
            "applied": False,
        }
    total = calculate_total(
        car_price_rub=car_price_rub,
        duty=duty,
        excise=excise,
        util=util,
        vat=vat,
    )

    response: dict[str, object] = {
        "total_cost": float(total),
        "breakdown": {
            "car_price_rub": float(car_price_rub),
            "duty": float(duty),
            "excise": float(excise),
            "util": float(util),
            "vat": float(vat),
        },
        "meta": {
            "rule_version": rule_set.version,
            "exchange_rate": float(quantize_money(rates.currency_to_rub)),
            "exchange_rate_source": rates.currency_source,
            "util_mode": util_mode,
        },
    }

    if debug:
        response["debug_trace"] = {
            "input": {
                "car_price_foreign": float(input_data.car_price_foreign),
                "currency": input_data.currency,
                "engine_volume": float(input_data.engine_volume),
                "engine_power_hp": input_data.engine_power_hp,
                "vehicle_age": input_data.vehicle_age,
                "fuel_type": input_data.fuel_type,
                "is_personal_use": input_data.is_personal_use,
                "is_legal_entity": input_data.is_legal_entity,
                "rule_version": input_data.rule_version,
            },
            "exchange": {
                "currency_to_rub": float(quantize_money(rates.currency_to_rub)),
                "currency_source": rates.currency_source,
                "eur_to_rub": float(quantize_money(rates.eur_to_rub)),
                "eur_source": rates.eur_source,
            },
            "fuel_rule": {
                "code": fuel_rule.code,
                "duty_basis": fuel_rule.duty_basis,
            },
            "duty": duty_trace,
            "excise": excise_trace,
            "util": util_trace,
            "vat": vat_trace,
        }

    return response
