import asyncio
import io
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

import aiohttp
from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup, ReplyKeyboardRemove
from dotenv import load_dotenv


class ListingFlow(StatesGroup):
    market = State()
    brand = State()
    model = State()
    year = State()
    mileage_km = State()
    drive_type = State()
    engine_volume_l = State()
    power_hp = State()
    body_type = State()
    trim = State()
    price = State()
    photos = State()
    confirm = State()


@dataclass
class BotConfig:
    token: str
    api_base_url: str
    manager_api_key: str
    allowed_ids: set[int]


MARKET_KB = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="Корея"), KeyboardButton(text="Япония")]],
    resize_keyboard=True,
)

DRIVE_KB = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Передний"), KeyboardButton(text="Задний")],
        [KeyboardButton(text="Полный")],
    ],
    resize_keyboard=True,
)

PHOTOS_KB = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="Готово")], [KeyboardButton(text="Отмена")]],
    resize_keyboard=True,
)

CONFIRM_KB = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="Отправить"), KeyboardButton(text="Добавить фото")], [KeyboardButton(text="Отмена")]],
    resize_keyboard=True,
)


router = Router()
CONFIG: BotConfig | None = None


def load_config() -> BotConfig:
    load_dotenv()
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("BOT_TOKEN is not set")

    api_base_url = os.getenv("API_BASE_URL", "https://api.primcom.ru").strip().rstrip("/")
    manager_api_key = os.getenv("MANAGER_API_KEY", "").strip()
    if not manager_api_key:
        raise RuntimeError("MANAGER_API_KEY is not set")

    allowed_raw = os.getenv("MANAGER_ALLOWED_IDS", "").strip()
    allowed_ids: set[int] = set()
    if allowed_raw:
        for part in allowed_raw.split(","):
            p = part.strip()
            if not p:
                continue
            try:
                allowed_ids.add(int(p))
            except ValueError:
                logging.warning("Skip invalid MANAGER_ALLOWED_IDS value: %s", p)

    return BotConfig(
        token=token,
        api_base_url=api_base_url,
        manager_api_key=manager_api_key,
        allowed_ids=allowed_ids,
    )


def check_access(message: Message) -> bool:
    global CONFIG
    if CONFIG is None:
        return False
    if not CONFIG.allowed_ids:
        return True
    user_id = message.from_user.id if message.from_user else 0
    return user_id in CONFIG.allowed_ids


def parse_year(text: str) -> int | None:
    t = (text or "").strip()
    if not t.isdigit():
        return None
    y = int(t)
    current = datetime.now(timezone.utc).year
    if y < 1980 or y > current + 1:
        return None
    return y


def parse_decimal(text: str) -> Decimal | None:
    t = (text or "").strip().replace(" ", "").replace(",", ".")
    if not t:
        return None
    try:
        return Decimal(t)
    except InvalidOperation:
        return None


def parse_int(text: str) -> int | None:
    t = (text or "").strip().replace(" ", "")
    if not t or not t.isdigit():
        return None
    return int(t)


def market_to_api(value: str) -> str | None:
    v = (value or "").strip().lower()
    if v == "корея":
        return "korea"
    if v == "япония":
        return "japan"
    return None


def summarize_payload(data: dict) -> str:
    lines = [
        "Проверьте карточку перед отправкой:",
        f"• Площадка: {'Корея' if data.get('market') == 'korea' else 'Япония'}",
        f"• Марка и модель: {data.get('brand', '')} {data.get('model', '')}".strip(),
        f"• Год: {data.get('year', '')}",
        f"• Пробег: {data.get('mileage_km', '')} км",
        f"• Привод: {data.get('drive_type', '')}",
        f"• Объем двигателя: {data.get('engine_volume_l', '')} л",
        f"• Л.С.: {data.get('power_hp', '')}",
        f"• Кузов: {data.get('body_type', '')}",
        f"• Комплектация: {data.get('trim', '')}",
        f"• Цена: {data.get('price', '')}",
        f"• Фото: {len(data.get('photo_file_ids', []))} шт.",
    ]
    return "\n".join(lines)


async def send_to_backend(bot: Bot, payload: dict) -> tuple[bool, str]:
    global CONFIG
    if CONFIG is None:
        return False, "CONFIG is not initialized"

    form = aiohttp.FormData()
    form.add_field("market", payload["market"])
    form.add_field("brand", payload["brand"])
    form.add_field("model", payload["model"])
    form.add_field("year", str(payload["year"]))
    form.add_field("mileage_km", str(payload["mileage_km"]))
    form.add_field("drive_type", payload["drive_type"])
    form.add_field("engine_volume_l", str(payload["engine_volume_l"]))
    form.add_field("power_hp", str(payload["power_hp"]))
    form.add_field("body_type", payload["body_type"])
    form.add_field("trim", payload["trim"])
    form.add_field("price", str(payload["price"]))

    for idx, file_id in enumerate(payload.get("photo_file_ids", [])):
        tg_file = await bot.get_file(file_id)
        stream = io.BytesIO()
        await bot.download(tg_file, destination=stream)
        stream.seek(0)
        form.add_field(
            "photos",
            stream.read(),
            filename=f"photo_{idx + 1}.jpg",
            content_type="image/jpeg",
        )

    url = f"{CONFIG.api_base_url}/api/manager/manual-listing"
    headers = {"X-Manager-Api-Key": CONFIG.manager_api_key}

    timeout = aiohttp.ClientTimeout(total=120)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(url, data=form, headers=headers) as resp:
            text = await resp.text()
            if resp.status >= 300:
                return False, f"Backend error {resp.status}: {text[:600]}"
            return True, text


@router.message(CommandStart())
@router.message(Command("new"))
async def start(message: Message, state: FSMContext) -> None:
    if not check_access(message):
        await message.answer("Доступ запрещен для этого аккаунта.", reply_markup=ReplyKeyboardRemove())
        return

    await state.clear()
    await message.answer(
        "Создаем новую карточку. Выберите площадку:",
        reply_markup=MARKET_KB,
    )
    await state.set_state(ListingFlow.market)


@router.message(Command("cancel"))
async def cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Ок, диалог сброшен.", reply_markup=ReplyKeyboardRemove())


@router.message(ListingFlow.market)
async def on_market(message: Message, state: FSMContext) -> None:
    market = market_to_api(message.text or "")
    if not market:
        await message.answer("Нужно выбрать: Корея или Япония.", reply_markup=MARKET_KB)
        return

    await state.update_data(market=market, photo_file_ids=[])
    await message.answer("Введите марку (например: Hyundai):", reply_markup=ReplyKeyboardRemove())
    await state.set_state(ListingFlow.brand)


@router.message(ListingFlow.brand)
async def on_brand(message: Message, state: FSMContext) -> None:
    brand = (message.text or "").strip()
    if len(brand) < 2:
        await message.answer("Слишком короткая марка. Введите еще раз.")
        return
    await state.update_data(brand=brand)
    await message.answer("Введите модель (например: Sonata):")
    await state.set_state(ListingFlow.model)


@router.message(ListingFlow.model)
async def on_model(message: Message, state: FSMContext) -> None:
    model = (message.text or "").strip()
    if len(model) < 1:
        await message.answer("Введите модель.")
        return
    await state.update_data(model=model)
    await message.answer("Введите год (YYYY):")
    await state.set_state(ListingFlow.year)


@router.message(ListingFlow.year)
async def on_year(message: Message, state: FSMContext) -> None:
    year = parse_year(message.text or "")
    if year is None:
        await message.answer("Год должен быть числом в формате YYYY (например 2021).")
        return
    await state.update_data(year=year)
    await message.answer("Введите пробег в км (например 86000):")
    await state.set_state(ListingFlow.mileage_km)


@router.message(ListingFlow.mileage_km)
async def on_mileage(message: Message, state: FSMContext) -> None:
    mileage_km = parse_int(message.text or "")
    if mileage_km is None or mileage_km <= 0:
        await message.answer("Пробег должен быть целым числом в км (например 86000).")
        return
    await state.update_data(mileage_km=mileage_km)
    await message.answer("Выберите привод:", reply_markup=DRIVE_KB)
    await state.set_state(ListingFlow.drive_type)


@router.message(ListingFlow.drive_type)
async def on_drive(message: Message, state: FSMContext) -> None:
    value = (message.text or "").strip().lower()
    mapping = {
        "передний": "Передний",
        "задний": "Задний",
        "полный": "Полный",
    }
    if value not in mapping:
        await message.answer("Выберите один из вариантов на клавиатуре.", reply_markup=DRIVE_KB)
        return
    await state.update_data(drive_type=mapping[value])
    await message.answer("Введите объем двигателя в литрах (например 2.0):", reply_markup=ReplyKeyboardRemove())
    await state.set_state(ListingFlow.engine_volume_l)


@router.message(ListingFlow.engine_volume_l)
async def on_engine_volume(message: Message, state: FSMContext) -> None:
    dv = parse_decimal(message.text or "")
    if dv is None or dv <= 0:
        await message.answer("Объем должен быть числом больше 0 (например 1.6).")
        return
    await state.update_data(engine_volume_l=str(dv.normalize()))
    await message.answer("Введите мощность в л.с. (например 204):")
    await state.set_state(ListingFlow.power_hp)


@router.message(ListingFlow.power_hp)
async def on_power(message: Message, state: FSMContext) -> None:
    hp = parse_int(message.text or "")
    if hp is None or hp <= 0:
        await message.answer("Мощность должна быть целым числом (например 204).")
        return
    await state.update_data(power_hp=hp)
    await message.answer("Введите тип кузова (например: седан, кроссовер):")
    await state.set_state(ListingFlow.body_type)


@router.message(ListingFlow.body_type)
async def on_body(message: Message, state: FSMContext) -> None:
    body = (message.text or "").strip()
    if len(body) < 2:
        await message.answer("Введите тип кузова текстом.")
        return
    await state.update_data(body_type=body)
    await message.answer("Введите комплектацию:")
    await state.set_state(ListingFlow.trim)


@router.message(ListingFlow.trim)
async def on_trim(message: Message, state: FSMContext) -> None:
    trim = (message.text or "").strip()
    if len(trim) < 2:
        await message.answer("Введите комплектацию текстом.")
        return
    await state.update_data(trim=trim)
    await message.answer("Введите конечную цену во Владивостоке с учетом нашей комиссии (только число, без валюты, например 156000):")
    await state.set_state(ListingFlow.price)


@router.message(ListingFlow.price)
async def on_price(message: Message, state: FSMContext) -> None:
    price = parse_decimal(message.text or "")
    if price is None or price <= 0:
        await message.answer("Цена должна быть числом больше 0.")
        return
    await state.update_data(price=str(price.normalize()))
    await message.answer(
        "Загрузите фото (можно несколько сообщений). Когда закончите, нажмите «Готово».",
        reply_markup=PHOTOS_KB,
    )
    await state.set_state(ListingFlow.photos)


@router.message(ListingFlow.photos, F.photo)
async def on_photo(message: Message, state: FSMContext) -> None:
    photos = message.photo or []
    if not photos:
        await message.answer("Фото не найдено, отправьте еще раз.")
        return
    best = photos[-1]
    data = await state.get_data()
    file_ids = list(data.get("photo_file_ids", []))
    if len(file_ids) >= 20:
        await message.answer("Достигнут лимит 20 фото. Нажмите «Готово».")
        return
    file_ids.append(best.file_id)
    await state.update_data(photo_file_ids=file_ids)
    await message.answer(f"Фото добавлено: {len(file_ids)} шт.")


@router.message(ListingFlow.photos)
async def on_photos_text(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip().lower()
    if text == "отмена":
        await state.clear()
        await message.answer("Диалог отменен.", reply_markup=ReplyKeyboardRemove())
        return

    if text != "готово":
        await message.answer("Пришлите фото или нажмите «Готово».")
        return

    data = await state.get_data()
    if not data.get("photo_file_ids"):
        await message.answer("Нужно загрузить минимум одно фото.")
        return

    await message.answer(summarize_payload(data), reply_markup=CONFIRM_KB)
    await state.set_state(ListingFlow.confirm)


@router.message(ListingFlow.confirm)
async def on_confirm(message: Message, state: FSMContext, bot: Bot) -> None:
    cmd = (message.text or "").strip().lower()

    if cmd == "отмена":
        await state.clear()
        await message.answer("Диалог отменен.", reply_markup=ReplyKeyboardRemove())
        return

    if cmd == "добавить фото":
        await message.answer("Загрузите дополнительные фото и нажмите «Готово».", reply_markup=PHOTOS_KB)
        await state.set_state(ListingFlow.photos)
        return

    if cmd != "отправить":
        await message.answer("Используйте кнопки: «Отправить», «Добавить фото» или «Отмена».", reply_markup=CONFIRM_KB)
        return

    data = await state.get_data()
    await message.answer("Отправляю на сервер...", reply_markup=ReplyKeyboardRemove())

    try:
        ok, backend_text = await send_to_backend(bot, data)
    except Exception as exc:
        logging.exception("send_to_backend failed")
        await message.answer(f"Ошибка отправки: {exc}")
        return

    if not ok:
        await message.answer(f"Сервер вернул ошибку:\n{backend_text}")
        return

    await state.clear()
    await message.answer("Карточка успешно создана и отправлена на сайт. Для новой карточки нажмите /new")


@router.message()
async def fallback(message: Message) -> None:
    if not check_access(message):
        await message.answer("Доступ запрещен для этого аккаунта.")
        return
    await message.answer("Используйте /new для создания карточки или /cancel для отмены.")


async def main() -> None:
    global CONFIG
    CONFIG = load_config()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    bot = Bot(token=CONFIG.token)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

    logging.info("manager-listings-bot started")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
