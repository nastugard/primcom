from __future__ import annotations

from decimal import Decimal

from app.services.import_calculator.exceptions import CalculatorValidationError
from app.services.import_calculator.types import (
    DutyNewBand,
    DutyVolumeBand,
    ExciseBand,
    FuelRule,
    RuleSet,
    UtilCommercialBand,
    UtilPrivilegedRate,
)


def _d(value: str | int | float) -> Decimal:
    return Decimal(str(value))


RULES_2025 = RuleSet(
    version="2025",
    default_exchange_rates={
        "USD": _d("90.00"),
        "EUR": _d("98.00"),
        "JPY": _d("0.61"),
    },
    fuel_rules={
        "petrol": FuelRule(code="petrol", duty_basis="standard"),
        "diesel": FuelRule(code="diesel", duty_basis="standard"),
        "hybrid": FuelRule(code="hybrid", duty_basis="standard"),
    },
    duty_config={
        "new": (
            DutyNewBand(max_value_eur=_d("8500"), pct=_d("0.54"), min_eur_per_cc=_d("2.5")),
            DutyNewBand(max_value_eur=_d("16700"), pct=_d("0.48"), min_eur_per_cc=_d("3.5")),
            DutyNewBand(max_value_eur=_d("42300"), pct=_d("0.48"), min_eur_per_cc=_d("5.5")),
            DutyNewBand(max_value_eur=_d("169000"), pct=_d("0.48"), min_eur_per_cc=_d("15")),
            DutyNewBand(max_value_eur=_d("999999999"), pct=_d("0.48"), min_eur_per_cc=_d("20")),
        ),
        "3-5": (
            DutyVolumeBand(max_engine_volume_l=_d("1.0"), eur_per_cc=_d("1.5")),
            DutyVolumeBand(max_engine_volume_l=_d("1.5"), eur_per_cc=_d("1.7")),
            DutyVolumeBand(max_engine_volume_l=_d("1.8"), eur_per_cc=_d("2.5")),
            DutyVolumeBand(max_engine_volume_l=_d("2.3"), eur_per_cc=_d("2.7")),
            DutyVolumeBand(max_engine_volume_l=_d("3.0"), eur_per_cc=_d("3.0")),
            DutyVolumeBand(max_engine_volume_l=_d("99.0"), eur_per_cc=_d("3.6")),
        ),
        "5+": (
            DutyVolumeBand(max_engine_volume_l=_d("1.0"), eur_per_cc=_d("3.0")),
            DutyVolumeBand(max_engine_volume_l=_d("1.5"), eur_per_cc=_d("3.2")),
            DutyVolumeBand(max_engine_volume_l=_d("1.8"), eur_per_cc=_d("3.5")),
            DutyVolumeBand(max_engine_volume_l=_d("2.3"), eur_per_cc=_d("4.8")),
            DutyVolumeBand(max_engine_volume_l=_d("3.0"), eur_per_cc=_d("5.0")),
            DutyVolumeBand(max_engine_volume_l=_d("99.0"), eur_per_cc=_d("5.7")),
        ),
    },
    excise_bands=(
        ExciseBand(min_hp=0, max_hp=90, rate_per_hp=_d("0")),
        ExciseBand(min_hp=90, max_hp=150, rate_per_hp=_d("58")),
        ExciseBand(min_hp=150, max_hp=200, rate_per_hp=_d("557")),
        ExciseBand(min_hp=200, max_hp=300, rate_per_hp=_d("912")),
        ExciseBand(min_hp=300, max_hp=9999, rate_per_hp=_d("1558")),
    ),
    util_base_amount_rub=_d("20000"),
    util_privileged_rates=(
        UtilPrivilegedRate(vehicle_age="new", coefficient=_d("0.17")),
        UtilPrivilegedRate(vehicle_age="3-5", coefficient=_d("0.26")),
        UtilPrivilegedRate(vehicle_age="5+", coefficient=_d("0.26")),
    ),
    util_commercial_bands=(
        UtilCommercialBand(vehicle_age="new", max_engine_volume_l=_d("1.0"), max_engine_power_hp=90, coefficient=_d("12")),
        UtilCommercialBand(vehicle_age="new", max_engine_volume_l=_d("2.0"), max_engine_power_hp=150, coefficient=_d("18")),
        UtilCommercialBand(vehicle_age="new", max_engine_volume_l=_d("3.0"), max_engine_power_hp=200, coefficient=_d("30")),
        UtilCommercialBand(vehicle_age="new", max_engine_volume_l=_d("3.0"), max_engine_power_hp=300, coefficient=_d("52")),
        UtilCommercialBand(vehicle_age="new", max_engine_volume_l=_d("99.0"), max_engine_power_hp=9999, coefficient=_d("72")),
        UtilCommercialBand(vehicle_age="3-5", max_engine_volume_l=_d("1.0"), max_engine_power_hp=90, coefficient=_d("28")),
        UtilCommercialBand(vehicle_age="3-5", max_engine_volume_l=_d("1.5"), max_engine_power_hp=150, coefficient=_d("44")),
        UtilCommercialBand(vehicle_age="3-5", max_engine_volume_l=_d("2.0"), max_engine_power_hp=200, coefficient=_d("61")),
        UtilCommercialBand(vehicle_age="3-5", max_engine_volume_l=_d("3.0"), max_engine_power_hp=300, coefficient=_d("78")),
        UtilCommercialBand(vehicle_age="3-5", max_engine_volume_l=_d("99.0"), max_engine_power_hp=9999, coefficient=_d("90")),
        UtilCommercialBand(vehicle_age="5+", max_engine_volume_l=_d("1.0"), max_engine_power_hp=90, coefficient=_d("28")),
        UtilCommercialBand(vehicle_age="5+", max_engine_volume_l=_d("1.5"), max_engine_power_hp=150, coefficient=_d("44")),
        UtilCommercialBand(vehicle_age="5+", max_engine_volume_l=_d("2.0"), max_engine_power_hp=200, coefficient=_d("61")),
        UtilCommercialBand(vehicle_age="5+", max_engine_volume_l=_d("3.0"), max_engine_power_hp=300, coefficient=_d("78")),
        UtilCommercialBand(vehicle_age="5+", max_engine_volume_l=_d("99.0"), max_engine_power_hp=9999, coefficient=_d("90")),
    ),
    vat_rate=_d("0.20"),
)


RULES_2026 = RuleSet(
    version="2026",
    default_exchange_rates={
        "USD": _d("92.50"),
        "EUR": _d("100.50"),
        "JPY": _d("0.64"),
    },
    fuel_rules={
        "petrol": FuelRule(code="petrol", duty_basis="standard"),
        "diesel": FuelRule(code="diesel", duty_basis="standard"),
        "hybrid": FuelRule(code="hybrid", duty_basis="standard"),
        "electric": FuelRule(code="electric", duty_basis="electric"),
    },
    duty_config={
        "new": (
            DutyNewBand(max_value_eur=_d("8500"), pct=_d("0.54"), min_eur_per_cc=_d("2.5")),
            DutyNewBand(max_value_eur=_d("16700"), pct=_d("0.48"), min_eur_per_cc=_d("3.5")),
            DutyNewBand(max_value_eur=_d("42300"), pct=_d("0.48"), min_eur_per_cc=_d("5.5")),
            DutyNewBand(max_value_eur=_d("169000"), pct=_d("0.48"), min_eur_per_cc=_d("15")),
            DutyNewBand(max_value_eur=_d("999999999"), pct=_d("0.48"), min_eur_per_cc=_d("20")),
        ),
        "3-5": (
            DutyVolumeBand(max_engine_volume_l=_d("1.0"), eur_per_cc=_d("1.5")),
            DutyVolumeBand(max_engine_volume_l=_d("1.5"), eur_per_cc=_d("1.7")),
            DutyVolumeBand(max_engine_volume_l=_d("1.8"), eur_per_cc=_d("2.5")),
            DutyVolumeBand(max_engine_volume_l=_d("2.3"), eur_per_cc=_d("2.7")),
            DutyVolumeBand(max_engine_volume_l=_d("3.0"), eur_per_cc=_d("3.0")),
            DutyVolumeBand(max_engine_volume_l=_d("99.0"), eur_per_cc=_d("3.6")),
        ),
        "5+": (
            DutyVolumeBand(max_engine_volume_l=_d("1.0"), eur_per_cc=_d("3.0")),
            DutyVolumeBand(max_engine_volume_l=_d("1.5"), eur_per_cc=_d("3.2")),
            DutyVolumeBand(max_engine_volume_l=_d("1.8"), eur_per_cc=_d("3.5")),
            DutyVolumeBand(max_engine_volume_l=_d("2.3"), eur_per_cc=_d("4.8")),
            DutyVolumeBand(max_engine_volume_l=_d("3.0"), eur_per_cc=_d("5.0")),
            DutyVolumeBand(max_engine_volume_l=_d("99.0"), eur_per_cc=_d("5.7")),
        ),
    },
    excise_bands=(
        ExciseBand(min_hp=0, max_hp=90, rate_per_hp=_d("0")),
        ExciseBand(min_hp=90, max_hp=150, rate_per_hp=_d("61")),
        ExciseBand(min_hp=150, max_hp=200, rate_per_hp=_d("583")),
        ExciseBand(min_hp=200, max_hp=300, rate_per_hp=_d("955")),
        ExciseBand(min_hp=300, max_hp=9999, rate_per_hp=_d("1628")),
    ),
    util_base_amount_rub=_d("20000"),
    util_privileged_rates=(
        UtilPrivilegedRate(vehicle_age="new", coefficient=_d("0.17")),
        UtilPrivilegedRate(vehicle_age="3-5", coefficient=_d("0.26")),
        UtilPrivilegedRate(vehicle_age="5+", coefficient=_d("0.26")),
    ),
    util_commercial_bands=(
        UtilCommercialBand(vehicle_age="new", max_engine_volume_l=_d("1.0"), max_engine_power_hp=90, coefficient=_d("14")),
        UtilCommercialBand(vehicle_age="new", max_engine_volume_l=_d("2.0"), max_engine_power_hp=150, coefficient=_d("21")),
        UtilCommercialBand(vehicle_age="new", max_engine_volume_l=_d("3.0"), max_engine_power_hp=200, coefficient=_d("35")),
        UtilCommercialBand(vehicle_age="new", max_engine_volume_l=_d("3.0"), max_engine_power_hp=300, coefficient=_d("60")),
        UtilCommercialBand(vehicle_age="new", max_engine_volume_l=_d("99.0"), max_engine_power_hp=9999, coefficient=_d("82")),
        UtilCommercialBand(vehicle_age="3-5", max_engine_volume_l=_d("1.0"), max_engine_power_hp=90, coefficient=_d("32")),
        UtilCommercialBand(vehicle_age="3-5", max_engine_volume_l=_d("1.5"), max_engine_power_hp=150, coefficient=_d("48")),
        UtilCommercialBand(vehicle_age="3-5", max_engine_volume_l=_d("2.0"), max_engine_power_hp=200, coefficient=_d("68")),
        UtilCommercialBand(vehicle_age="3-5", max_engine_volume_l=_d("3.0"), max_engine_power_hp=300, coefficient=_d("82.5")),
        UtilCommercialBand(vehicle_age="3-5", max_engine_volume_l=_d("99.0"), max_engine_power_hp=9999, coefficient=_d("96")),
        UtilCommercialBand(vehicle_age="5+", max_engine_volume_l=_d("1.0"), max_engine_power_hp=90, coefficient=_d("32")),
        UtilCommercialBand(vehicle_age="5+", max_engine_volume_l=_d("1.5"), max_engine_power_hp=150, coefficient=_d("48")),
        UtilCommercialBand(vehicle_age="5+", max_engine_volume_l=_d("2.0"), max_engine_power_hp=200, coefficient=_d("68")),
        UtilCommercialBand(vehicle_age="5+", max_engine_volume_l=_d("3.0"), max_engine_power_hp=300, coefficient=_d("82.5")),
        UtilCommercialBand(vehicle_age="5+", max_engine_volume_l=_d("99.0"), max_engine_power_hp=9999, coefficient=_d("96")),
    ),
    vat_rate=_d("0.20"),
)


RULES_BY_VERSION = {
    RULES_2025.version: RULES_2025,
    RULES_2026.version: RULES_2026,
}


def get_rule_set(version: str | None = None) -> RuleSet:
    resolved = str(version or "2026").strip() or "2026"
    rule_set = RULES_BY_VERSION.get(resolved)
    if rule_set is None:
        supported = ", ".join(sorted(RULES_BY_VERSION))
        raise CalculatorValidationError(
            f"Unsupported rule_version '{resolved}'. Supported versions: {supported}"
        )
    return rule_set
