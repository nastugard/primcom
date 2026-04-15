from __future__ import annotations

import os
import unittest
from decimal import Decimal
import importlib

import httpx


os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://primcom:primcom@127.0.0.1:5432/primcom_test",
)
os.environ["EXCHANGE_RATE_API_URL_TEMPLATE"] = ""

from app.services.import_calculator.adapters import resolve_exchange_rates
from app.services.import_calculator.config import get_rule_set
from app.services.import_calculator.core import (
    calculate_duty,
    calculate_excise,
    calculate_util,
    calculate_vat,
    convert_currency,
    determine_util_mode,
    quantize_money,
    select_fuel_rule,
    select_volume_duty_band,
)
from app.services.import_calculator.exceptions import CalculatorValidationError
from app.services.import_calculator.types import CalculatorInput


class ImportCalculatorCoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.rule_set = get_rule_set("2026")

    def test_new_duty_uses_max_of_percentage_and_minimum_per_cc(self) -> None:
        input_data = CalculatorInput(
            car_price_foreign=Decimal("5000"),
            currency="EUR",
            engine_volume=Decimal("3.0"),
            engine_power_hp=150,
            vehicle_age="new",
            fuel_type="petrol",
            is_personal_use=True,
            is_legal_entity=False,
            rule_version="2026",
        )
        fuel_rule = select_fuel_rule(self.rule_set, input_data.fuel_type)
        car_price_rub = convert_currency(input_data.car_price_foreign, Decimal("100.5"))

        duty, trace = calculate_duty(
            input_data,
            self.rule_set,
            car_price_rub=car_price_rub,
            eur_to_rub=Decimal("100.5"),
            fuel_rule=fuel_rule,
        )

        self.assertEqual(duty, Decimal("753750.00"))
        self.assertEqual(trace["strategy"], "new_unified_rate")
        self.assertEqual(trace["by_pct_rub"], 271350.0)
        self.assertEqual(trace["by_min_rub"], 753750.0)

    def test_duty_band_boundaries_for_3_to_5_years(self) -> None:
        expectations = {
            Decimal("1.0"): Decimal("1.5"),
            Decimal("1.5"): Decimal("1.7"),
            Decimal("1.8"): Decimal("2.5"),
            Decimal("2.0"): Decimal("2.7"),
            Decimal("3.0"): Decimal("3.0"),
            Decimal("3.1"): Decimal("3.6"),
        }
        for volume, expected in expectations.items():
            with self.subTest(engine_volume=volume):
                band = select_volume_duty_band(self.rule_set, "3-5", volume)
                self.assertEqual(band.eur_per_cc, expected)

    def test_duty_band_boundaries_for_5_plus_years(self) -> None:
        expectations = {
            Decimal("1.0"): Decimal("3.0"),
            Decimal("1.5"): Decimal("3.2"),
            Decimal("1.8"): Decimal("3.5"),
            Decimal("2.0"): Decimal("4.8"),
            Decimal("3.0"): Decimal("5.0"),
            Decimal("3.1"): Decimal("5.7"),
        }
        for volume, expected in expectations.items():
            with self.subTest(engine_volume=volume):
                band = select_volume_duty_band(self.rule_set, "5+", volume)
                self.assertEqual(band.eur_per_cc, expected)

    def test_excise_bands_cover_boundaries(self) -> None:
        expectations = {
            89: Decimal("0"),
            90: Decimal("61"),
            149: Decimal("61"),
            150: Decimal("583"),
            199: Decimal("583"),
            200: Decimal("955"),
            299: Decimal("955"),
            300: Decimal("1628"),
        }
        for hp, expected_rate in expectations.items():
            with self.subTest(engine_power_hp=hp):
                input_data = CalculatorInput(
                    car_price_foreign=Decimal("10000"),
                    currency="USD",
                    engine_volume=Decimal("2.0"),
                    engine_power_hp=hp,
                    vehicle_age="3-5",
                    fuel_type="petrol",
                    is_personal_use=True,
                    is_legal_entity=False,
                    rule_version="2026",
                )
                excise, trace = calculate_excise(input_data, self.rule_set)
                self.assertEqual(Decimal(str(trace["band"]["rate_per_hp"])), expected_rate)
                self.assertEqual(excise, quantize_money(expected_rate * Decimal(hp)))

    def test_util_mode_switches_on_hp_and_volume_thresholds(self) -> None:
        base_kwargs = {
            "car_price_foreign": Decimal("10000"),
            "currency": "USD",
            "vehicle_age": "3-5",
            "fuel_type": "petrol",
            "rule_version": "2026",
        }
        privileged = CalculatorInput(
            engine_volume=Decimal("3.0"),
            engine_power_hp=160,
            is_personal_use=True,
            is_legal_entity=False,
            **base_kwargs,
        )
        commercial_hp = CalculatorInput(
            engine_volume=Decimal("3.0"),
            engine_power_hp=161,
            is_personal_use=True,
            is_legal_entity=False,
            **base_kwargs,
        )
        commercial_volume = CalculatorInput(
            engine_volume=Decimal("3.1"),
            engine_power_hp=160,
            is_personal_use=True,
            is_legal_entity=False,
            **base_kwargs,
        )

        self.assertEqual(determine_util_mode(privileged), "privileged")
        self.assertEqual(determine_util_mode(commercial_hp), "commercial")
        self.assertEqual(determine_util_mode(commercial_volume), "commercial")

    def test_vat_uses_price_plus_duty_excise_and_util(self) -> None:
        vat, trace = calculate_vat(
            self.rule_set,
            car_price_rub=Decimal("925000"),
            duty=Decimal("542700"),
            excise=Decimal("227290"),
            util=Decimal("1650000"),
        )
        self.assertEqual(Decimal(str(trace["vat_base_rub"])), Decimal("3344990.0"))
        self.assertEqual(vat, Decimal("668998.00"))

    def test_case_1_for_3_to_5_years_uses_2_7_eur_per_cc(self) -> None:
        band = select_volume_duty_band(self.rule_set, "3-5", Decimal("2.0"))
        self.assertEqual(band.eur_per_cc, Decimal("2.7"))

    def test_case_2_for_5_plus_years_uses_4_8_eur_per_cc(self) -> None:
        band = select_volume_duty_band(self.rule_set, "5+", Decimal("2.0"))
        self.assertEqual(band.eur_per_cc, Decimal("4.8"))

    def test_acceptance_case_hits_expected_util_range(self) -> None:
        input_data = CalculatorInput(
            car_price_foreign=Decimal("10000"),
            currency="USD",
            engine_volume=Decimal("2.0"),
            engine_power_hp=238,
            vehicle_age="3-5",
            fuel_type="petrol",
            is_personal_use=True,
            is_legal_entity=False,
            rule_version="2026",
        )
        util, util_mode, _trace = calculate_util(input_data, self.rule_set)
        self.assertEqual(util_mode, "commercial")
        self.assertGreaterEqual(util, Decimal("1600000"))
        self.assertLessEqual(util, Decimal("1700000"))

    def test_missing_fuel_rule_raises_controlled_error(self) -> None:
        with self.assertRaises(CalculatorValidationError):
            select_fuel_rule(get_rule_set("2025"), "electric")


class ImportCalculatorExchangeTests(unittest.IsolatedAsyncioTestCase):
    async def test_exchange_rates_use_api_then_config_fallback(self) -> None:
        rule_set = get_rule_set("2026")

        async def fake_fetch(base_currency: str) -> tuple[Decimal | None, str]:
            if base_currency == "USD":
                return Decimal("93.10"), "api"
            return None, "config"

        rates = await resolve_exchange_rates(
            currency="USD",
            rule_set=rule_set,
            fetch_rate=fake_fetch,
        )

        self.assertEqual(rates.currency_to_rub, Decimal("93.10"))
        self.assertEqual(rates.currency_source, "api")
        self.assertEqual(rates.eur_to_rub, rule_set.default_exchange_rates["EUR"])
        self.assertEqual(rates.eur_source, "config")

    async def test_exchange_rate_override_has_priority(self) -> None:
        rule_set = get_rule_set("2026")

        async def fake_fetch(_base_currency: str) -> tuple[Decimal | None, str]:
            return None, "config"

        rates = await resolve_exchange_rates(
            currency="USD",
            rule_set=rule_set,
            exchange_rate_override=Decimal("97.70"),
            fetch_rate=fake_fetch,
        )

        self.assertEqual(rates.currency_to_rub, Decimal("97.70"))
        self.assertEqual(rates.currency_source, "override")
        self.assertEqual(rates.eur_to_rub, rule_set.default_exchange_rates["EUR"])


class ImportCalculatorApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        try:
            app_module = importlib.import_module("app.main")
        except RuntimeError as exc:
            if "python-multipart" in str(exc):
                self.skipTest("python-multipart is not installed in local .venv")
            raise

        transport = httpx.ASGITransport(app=app_module.app)
        self.client = httpx.AsyncClient(transport=transport, base_url="http://testserver")

    async def asyncTearDown(self) -> None:
        await self.client.aclose()

    async def test_calculate_success_without_debug(self) -> None:
        response = await self.client.post(
            "/api/import-calculator/calculate",
            json={
                "car_price_foreign": 10000,
                "currency": "USD",
                "engine_volume": 2.0,
                "engine_power_hp": 238,
                "vehicle_age": "3-5",
                "is_legal_entity": False,
                "fuel_type": "petrol",
                "is_personal_use": True,
            },
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertNotIn("debug_trace", data)
        self.assertEqual(data["meta"]["rule_version"], "2026")
        self.assertEqual(data["meta"]["util_mode"], "commercial")
        self.assertEqual(data["breakdown"]["vat"], 0)

    async def test_calculate_success_with_debug(self) -> None:
        response = await self.client.post(
            "/api/import-calculator/calculate",
            json={
                "car_price_foreign": 10000,
                "currency": "USD",
                "engine_volume": 2.0,
                "engine_power_hp": 238,
                "vehicle_age": "3-5",
                "fuel_type": "petrol",
                "is_personal_use": True,
                "is_legal_entity": True,
                "debug": True,
            },
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("debug_trace", data)
        self.assertEqual(data["debug_trace"]["duty"]["strategy"], "volume_based_eur_per_cc")
        self.assertGreater(data["breakdown"]["vat"], 0)

    async def test_case_3_legal_entity_adds_vat(self) -> None:
        response = await self.client.post(
            "/api/import-calculator/calculate",
            json={
                "car_price_foreign": 10000,
                "currency": "USD",
                "engine_volume": 2.0,
                "engine_power_hp": 238,
                "vehicle_age": "3-5",
                "fuel_type": "petrol",
                "is_personal_use": True,
                "is_legal_entity": True,
            },
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertGreater(data["breakdown"]["vat"], 0)

    async def test_case_4_individual_has_zero_vat(self) -> None:
        response = await self.client.post(
            "/api/import-calculator/calculate",
            json={
                "car_price_foreign": 10000,
                "currency": "USD",
                "engine_volume": 2.0,
                "engine_power_hp": 238,
                "vehicle_age": "3-5",
                "fuel_type": "petrol",
                "is_personal_use": True,
                "is_legal_entity": False,
            },
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["breakdown"]["vat"], 0)

    async def test_invalid_currency_returns_422(self) -> None:
        response = await self.client.post(
            "/api/import-calculator/calculate",
            json={
                "car_price_foreign": 10000,
                "currency": "CNY",
                "engine_volume": 2.0,
                "engine_power_hp": 238,
                "vehicle_age": "3-5",
                "fuel_type": "petrol",
                "is_personal_use": True,
                "is_legal_entity": False,
            },
        )

        self.assertEqual(response.status_code, 422)

    async def test_unknown_rule_version_returns_422(self) -> None:
        response = await self.client.post(
            "/api/import-calculator/calculate",
            json={
                "car_price_foreign": 10000,
                "currency": "USD",
                "engine_volume": 2.0,
                "engine_power_hp": 238,
                "vehicle_age": "3-5",
                "fuel_type": "petrol",
                "is_personal_use": True,
                "is_legal_entity": False,
                "rule_version": "2099",
            },
        )

        self.assertEqual(response.status_code, 422)
        self.assertIn("Unsupported rule_version", response.text)

    async def test_missing_fuel_rule_returns_422(self) -> None:
        response = await self.client.post(
            "/api/import-calculator/calculate",
            json={
                "car_price_foreign": 10000,
                "currency": "USD",
                "engine_volume": 0,
                "engine_power_hp": 150,
                "vehicle_age": "3-5",
                "fuel_type": "electric",
                "is_personal_use": True,
                "is_legal_entity": False,
                "rule_version": "2025",
            },
        )

        self.assertEqual(response.status_code, 422)
        self.assertIn("not configured", response.text)


if __name__ == "__main__":
    unittest.main()
