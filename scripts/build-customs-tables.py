#!/usr/bin/env python3
"""Собирает статические таблицы таможенных ставок для pages/rastamozhka-i-poshliny.html.

Источник истины — china_cars_backend/app/services/import_calculator/config.py.
Числа не переписываются руками: скрипт импортирует конфиг и считает примеры
теми же функциями, что и боевой калькулятор.

    python3 scripts/build-customs-tables.py          # перезаписать блок в странице
    python3 scripts/build-customs-tables.py --check  # упасть, если страница устарела
"""
from __future__ import annotations

import importlib.util
import io
import sys
import types as pytypes
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CALC = ROOT / "china_cars_backend" / "app" / "services" / "import_calculator"
PAGE = ROOT / "pages" / "rastamozhka-i-poshliny.html"
START = "<!-- customs-rates:start -->"
END = "<!-- customs-rates:end -->"
# Версия правил, которую калькулятор использует по умолчанию (get_rule_set(None)).
RULE_VERSION = "2026"


def load_calculator():
    """Грузит модули калькулятора по путям: пакетный __init__ тянет openai."""
    for name in ("app", "app.services", "app.services.import_calculator"):
        if name not in sys.modules:
            mod = pytypes.ModuleType(name)
            mod.__path__ = []
            sys.modules[name] = mod

    def load(short: str):
        full = f"app.services.import_calculator.{short}"
        spec = importlib.util.spec_from_file_location(full, CALC / f"{short}.py")
        mod = importlib.util.module_from_spec(spec)
        sys.modules[full] = mod
        spec.loader.exec_module(mod)
        return mod

    load("exceptions")
    types_mod = load("types")
    config = load("config")
    core = load("core")
    return config, core, types_mod


def money(value: Decimal) -> str:
    """1234567.89 -> '1 234 568 ₽' (неразрывные пробелы)."""
    return f"{int(round(float(value))):,}".replace(",", " ") + " ₽"


def num(value: Decimal) -> str:
    text = f"{Decimal(value):f}"
    # Нули обрезаем только в дробной части: иначе "20" превращается в "2".
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return (text or "0").replace(".", ",")


def volume_rows(bands) -> list[tuple[str, str]]:
    rows, prev = [], Decimal("0")
    for band in bands:
        top = band.max_engine_volume_l
        if top >= Decimal("99"):
            label = f"свыше {num(prev)} л"
        elif prev == 0:
            label = f"до {num(top)} л включительно"
        else:
            label = f"свыше {num(prev)} до {num(top)} л включительно"
        rows.append((label, f"{num(band.eur_per_cc)} € за см³"))
        prev = top
    return rows


def build(config, core, types_mod) -> str:
    rules = config.RULES_BY_VERSION[RULE_VERSION]
    eur = rules.default_exchange_rates["EUR"]
    out: list[str] = [START]
    a = out.append

    a('\n    <section class="section" aria-label="Ставки таможенных платежей">')
    a('      <div class="container">')
    a('        <h2 class="section__title">Ставки таможенных платежей</h2>')
    a('        <p class="section__lead">')
    a(f'          Ставки, по которым считает наш калькулятор: правила {rules.version} года.')
    a('          Итоговая сумма зависит от курса валюты на день оплаты, поэтому таблицы')
    a('          дают порядок величин, а не окончательную стоимость и не являются офертой.')
    a('        </p>')

    # --- Пошлина ---
    a('        <h3 class="rate-table__caption">Таможенная пошлина, автомобили до 3 лет включительно</h3>')
    a('        <p class="rate-table__note">')
    a('          Берётся большее из двух значений: процент от стоимости либо минимум за см³ объёма.')
    a('        </p>')
    a('        <div class="rate-table__scroll">')
    a('          <table class="rate-table">')
    a('            <thead><tr><th scope="col">Стоимость автомобиля</th><th scope="col">Процент от стоимости</th><th scope="col">Минимум за см³</th></tr></thead>')
    a('            <tbody>')
    prev = Decimal("0")
    for band in rules.duty_config["new"]:
        top = band.max_value_eur
        if top >= Decimal("999999999"):
            label = f"свыше {int(prev):,} €".replace(",", " ")
        elif prev == 0:
            label = f"до {int(top):,} € включительно".replace(",", " ")
        else:
            label = f"свыше {int(prev):,} до {int(top):,} € включительно".replace(",", " ")
        pct = f"{int(band.pct * 100)}%"
        a(f'              <tr><td>{label}</td><td>{pct}</td><td>{num(band.min_eur_per_cc)} € за см³</td></tr>')
        prev = top
    a('            </tbody>')
    a('          </table>')
    a('        </div>')

    for age_key, title in (("3-5", "от 3 до 5 лет"), ("5+", "старше 5 лет")):
        a(f'        <h3 class="rate-table__caption">Таможенная пошлина, автомобили {title}</h3>')
        a('        <div class="rate-table__scroll">')
        a('          <table class="rate-table">')
        a('            <thead><tr><th scope="col">Объём двигателя</th><th scope="col">Ставка</th></tr></thead>')
        a('            <tbody>')
        for label, rate in volume_rows(rules.duty_config[age_key]):
            a(f'              <tr><td>{label}</td><td>{rate}</td></tr>')
        a('            </tbody>')
        a('          </table>')
        a('        </div>')

    # --- Акциз ---
    a('        <h3 class="rate-table__caption">Акциз по мощности двигателя</h3>')
    a('        <div class="rate-table__scroll">')
    a('          <table class="rate-table">')
    a('            <thead><tr><th scope="col">Мощность</th><th scope="col">Ставка за 1 л.с.</th></tr></thead>')
    a('            <tbody>')
    for band in rules.excise_bands:
        if band.max_hp >= 9999:
            label = f"свыше {band.min_hp} л.с."
        elif band.min_hp == 0:
            label = f"до {band.max_hp} л.с. включительно"
        else:
            label = f"свыше {band.min_hp} до {band.max_hp} л.с. включительно"
        rate = "не начисляется" if band.rate_per_hp == 0 else f"{num(band.rate_per_hp)} ₽"
        a(f'              <tr><td>{label}</td><td>{rate}</td></tr>')
    a('            </tbody>')
    a('          </table>')
    a('        </div>')

    # --- Утильсбор ---
    priv = {r.vehicle_age: r.coefficient for r in rules.util_privileged_rates}
    a('        <h3 class="rate-table__caption">Утилизационный сбор</h3>')
    a('        <p class="rate-table__note">')
    a(f'          Считается как базовая ставка {money(rules.util_base_amount_rub)} умноженная на коэффициент.')
    a('          Льготный коэффициент применяется к автомобилю для личного пользования')
    a('          мощностью до 160 л.с. и объёмом до 3 л включительно; в остальных случаях — коммерческий.')
    a('        </p>')
    a('        <div class="rate-table__scroll">')
    a('          <table class="rate-table">')
    a('            <thead><tr><th scope="col">Возраст автомобиля</th><th scope="col">Льготный коэффициент</th><th scope="col">Сумма льготного сбора</th></tr></thead>')
    a('            <tbody>')
    for key, label in (("new", "до 3 лет включительно"), ("3-5", "от 3 до 5 лет"), ("5+", "старше 5 лет")):
        coef = priv[key]
        a(f'              <tr><td>{label}</td><td>{num(coef)}</td><td>{money(rules.util_base_amount_rub * coef)}</td></tr>')
    a('            </tbody>')
    a('          </table>')
    a('        </div>')

    # --- НДС ---
    a('        <h3 class="rate-table__caption">НДС</h3>')
    a('        <p class="rate-table__note">')
    a(f'          {int(rules.vat_rate * 100)}% начисляется только при ввозе на юридическое лицо,')
    a('          на сумму стоимости автомобиля, пошлины, акциза и утилизационного сбора.')
    a('          При ввозе на физическое лицо НДС не начисляется.')
    a('        </p>')

    # --- Примеры ---
    examples = [
        ("Компактный седан из Японии, 5 лет", Decimal("1200000"), Decimal("1.5"), 109, "5+", "petrol"),
        ("Кроссовер из Кореи, 4 года", Decimal("2100000"), Decimal("2.0"), 149, "3-5", "petrol"),
        ("Крупный внедорожник из Китая, 4 года", Decimal("3800000"), Decimal("3.0"), 249, "3-5", "petrol"),
    ]
    a('        <h3 class="rate-table__caption">Три примера расчёта</h3>')
    a('        <p class="rate-table__note">')
    a(f'          Ввоз на физическое лицо для личного пользования, курс {num(eur)} ₽ за евро.')
    a('          Указаны только таможенные платежи: без стоимости доставки, оформления и услуг компании.')
    a('        </p>')
    a('        <div class="rate-table__scroll">')
    a('          <table class="rate-table">')
    a('            <thead><tr><th scope="col">Автомобиль</th><th scope="col">Цена</th><th scope="col">Пошлина</th><th scope="col">Акциз</th><th scope="col">Утильсбор</th><th scope="col">Платежи всего</th></tr></thead>')
    a('            <tbody>')
    for title, price_rub, volume, hp, age, fuel in examples:
        data = types_mod.CalculatorInput(
            car_price_foreign=price_rub, currency="USD", engine_volume=volume,
            engine_power_hp=hp, vehicle_age=age, fuel_type=fuel,
            is_personal_use=True, is_legal_entity=False, rule_version=RULE_VERSION,
        )
        fuel_rule = core.select_fuel_rule(rules, fuel)
        duty, _ = core.calculate_duty(
            data, rules, car_price_rub=price_rub, eur_to_rub=eur, fuel_rule=fuel_rule,
        )
        excise, _ = core.calculate_excise(data, rules)
        util, _, _ = core.calculate_util(data, rules)
        payments = duty + excise + util
        a(f'              <tr><td>{title}, {num(volume)} л, {hp} л.с.</td><td>{money(price_rub)}</td>'
          f'<td>{money(duty)}</td><td>{money(excise)}</td><td>{money(util)}</td>'
          f'<td><strong>{money(payments)}</strong></td></tr>')
    a('            </tbody>')
    a('          </table>')
    a('        </div>')
    a('        <p class="rate-table__note">')
    a('          Обратите внимание на третий пример: утилизационный сбор там в сотни раз больше,')
    a('          чем в первых двух. Причина не в цене автомобиля, а в мощности — 249 л.с. выше')
    a('          льготного порога в 160 л.с., поэтому применяется коммерческий коэффициент,')
    a('          даже когда автомобиль ввозится для личного пользования. Это самая частая причина')
    a('          неожиданного роста бюджета, поэтому мощность стоит проверять до покупки.')
    a('        </p>')
    a('        <p class="rate-table__note">')
    a('          Примеры рассчитаны по тем же правилам, что и калькулятор на сайте.')
    a('          Для конкретного автомобиля сумма считается по актуальному курсу.')
    a('        </p>')
    a('        <p>')
    a('          <a class="btn btn--primary" href="./kalkulyator-stoimosti.html">Рассчитать свой автомобиль</a>')
    a('        </p>')
    a('      </div>')
    a('    </section>\n    ')
    out.append(END)
    return "\n".join(out)


def main() -> int:
    config, core, types_mod = load_calculator()
    block = build(config, core, types_mod)
    page = io.open(PAGE, encoding="utf-8").read()
    if START not in page or END not in page:
        print(f"ОШИБКА: в {PAGE.name} нет маркеров {START} / {END}", file=sys.stderr)
        return 2
    head, rest = page.split(START, 1)
    _, tail = rest.split(END, 1)
    updated = head + block + tail
    if "--check" in sys.argv:
        if updated != page:
            print("ОШИБКА: таблицы ставок устарели относительно config.py.", file=sys.stderr)
            print("Выполните: python3 scripts/build-customs-tables.py", file=sys.stderr)
            return 1
        print("Таблицы ставок совпадают с config.py.")
        return 0
    io.open(PAGE, "w", encoding="utf-8").write(updated)
    print(f"Таблицы ставок обновлены из правил {RULE_VERSION}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
