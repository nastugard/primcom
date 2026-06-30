import asyncio
import io
import logging
import mimetypes
import os
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

import aiohttp
from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup, ReplyKeyboardRemove
from dotenv import load_dotenv

try:
    from aiogram.fsm.storage.memory import SimpleEventIsolation
except ImportError:  # pragma: no cover - compatibility with older aiogram builds
    SimpleEventIsolation = None


IMPORT_MARKETS = {
    "китай": "china",
    "china": "china",
    "кнр": "china",
    "корея": "korea",
    "korea": "korea",
    "южная корея": "korea",
    "япония": "japan",
    "japan": "japan",
}
IMPORT_DRIVES = {
    "передний": "Передний",
    "передний привод": "Передний",
    "front": "Передний",
    "fwd": "Передний",
    "задний": "Задний",
    "задний привод": "Задний",
    "rear": "Задний",
    "rwd": "Задний",
    "полный": "Полный",
    "полный привод": "Полный",
    "4wd": "Полный",
    "awd": "Полный",
}
IMPORT_BODY_TYPES = {
    "седан": "Седан",
    "универсал": "Универсал",
    "хэтчбек": "Хэтчбек",
    "хетчбек": "Хэтчбек",
    "купе": "Купе",
    "джип": "Джип",
    "внедорожник": "Джип",
    "кроссовер": "Кроссовер",
    "suv": "Кроссовер",
    "минивэн": "Минивэн",
    "минивен": "Минивэн",
    "пикап": "Пикап",
    "лифтбек": "Лифтбек",
}
IMPORT_KNOWN_BRANDS = sorted(
    {
        "Alfa Romeo", "Aston Martin", "BYD", "BMW", "Changan", "Chery", "Chevrolet",
        "Citroen", "Exeed", "Ford", "Geely", "Genesis", "Great Wall", "Haval", "Honda",
        "Hongqi", "Hyundai", "Infiniti", "Jaguar", "Jeep", "Kia", "Land Rover", "Lexus",
        "Li Auto", "Mazda", "Mercedes-Benz", "Mercedes Benz", "Mitsubishi", "Nissan",
        "Omoda", "Peugeot", "Porsche", "Renault", "Skoda", "Subaru", "Suzuki", "Tank",
        "Tesla", "Toyota", "Volkswagen", "Volvo", "Zeekr", "Ауди", "БМВ", "Лада",
        "Лексус", "Мерседес", "Тойота",
    },
    key=len,
    reverse=True,
)
IMPORT_FIELD_ALIASES = {
    "year": ("год", "year"),
    "engine_volume_l": ("двигатель", "объем двигателя", "объём двигателя", "мотор"),
    "mileage_km": ("пробег", "mileage"),
    "drive_type": ("привод", "drive"),
    "body_type": ("кузов", "тип кузова", "body"),
    "power_hp": ("мощность", "л.с.", "лс", "power"),
    "trim": ("комплектация", "комплект", "trim"),
    "auction_grade": ("оценка", "аукционная оценка", "auction grade"),
    "price": ("цена", "стоимость", "price"),
}


def _import_clean_line(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip(" \t\r\n|•—–-")


def _import_positive_int(value: str) -> int | None:
    digits = re.sub(r"\D", "", str(value or ""))
    number = int(digits) if digits else 0
    return number if number > 0 else None


def _import_decimal(value: str) -> str | None:
    number = re.sub(r"[^0-9,.\-]", "", str(value or "")).replace(",", ".")
    try:
        decimal = Decimal(number)
    except (InvalidOperation, ValueError):
        return None
    if decimal <= 0:
        return None
    text = format(decimal.normalize(), "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def _import_labeled_values(text: str) -> dict[str, str]:
    found: dict[str, str] = {}
    aliases = sorted(
        ((alias, field) for field, names in IMPORT_FIELD_ALIASES.items() for alias in names),
        key=lambda item: len(item[0]),
        reverse=True,
    )
    pattern = re.compile(
        rf"^\s*(?P<label>{'|'.join(re.escape(alias) for alias, _ in aliases)})"
        r"\s*(?:[-–—:=]|→|->)+\s*(?P<value>.+?)\s*$",
        re.IGNORECASE,
    )
    for raw_line in str(text or "").splitlines():
        match = pattern.match(_import_clean_line(raw_line))
        if not match:
            continue
        label = match.group("label").casefold()
        for alias, field_name in aliases:
            if label == alias.casefold():
                found.setdefault(field_name, _import_clean_line(match.group("value")))
                break
    price_match = re.search(
        r"(?:цена|стоимость|price)\s*(?:[-–—:=]|→|->)*\s*([0-9][0-9\s.,]*)",
        str(text or ""),
        re.IGNORECASE,
    )
    if price_match:
        found.setdefault("price", price_match.group(1))
    return found


def _import_title(text: str) -> str:
    labels = {alias.casefold() for names in IMPORT_FIELD_ALIASES.values() for alias in names}
    for raw_line in str(text or "").splitlines():
        line = _import_clean_line(raw_line)
        lowered = re.sub(r"[^\w\s-]", "", line, flags=re.UNICODE).casefold().strip()
        if not lowered or lowered in {"характеристики", "характеристика", "описание", "автомобиль"}:
            continue
        if any(re.search(rf"(?<!\w){re.escape(label)}(?!\w)", lowered) for label in IMPORT_MARKETS):
            continue
        if any(lowered.startswith(label) for label in labels):
            continue
        if re.search(r"\d[\d\s.,]*\s*(?:₽|руб)", line, re.IGNORECASE):
            continue
        if len(line) >= 3:
            return line
    return ""


def _import_brand_model(title: str) -> tuple[str, str]:
    clean = _import_clean_line(title)
    lowered = clean.casefold()
    for brand in IMPORT_KNOWN_BRANDS:
        if lowered == brand.casefold():
            return clean, ""
        if lowered.startswith(brand.casefold() + " "):
            return clean[: len(brand)], clean[len(brand):].strip()
    parts = clean.split(maxsplit=1)
    return (parts[0], parts[1]) if len(parts) == 2 else (clean, "")


def parse_forwarded_listing(text: str) -> dict[str, object]:
    raw = str(text or "").strip()
    if not raw:
        return {}
    values = _import_labeled_values(raw)
    brand, model = _import_brand_model(_import_title(raw))
    payload: dict[str, object] = {}

    lowered = raw.casefold()
    for label, market in IMPORT_MARKETS.items():
        if re.search(rf"(?<!\w){re.escape(label)}(?!\w)", lowered):
            payload["market"] = market
            break
    if brand:
        payload["brand"] = brand
    if model:
        payload["model"] = model

    year = _import_positive_int(values.get("year", ""))
    if year and 1980 <= year <= 2100:
        payload["year"] = year
    mileage = _import_positive_int(values.get("mileage_km", ""))
    if mileage:
        payload["mileage_km"] = mileage
    engine = _import_decimal(values.get("engine_volume_l", ""))
    if engine:
        payload["engine_volume_l"] = engine
    power = _import_positive_int(values.get("power_hp", ""))
    if power:
        payload["power_hp"] = power
    price = _import_positive_int(values.get("price", ""))
    if price:
        payload["price"] = str(price)

    drive = _import_clean_line(values.get("drive_type", "")).casefold()
    if drive:
        payload["drive_type"] = IMPORT_DRIVES.get(drive, drive.capitalize())
    body = _import_clean_line(values.get("body_type", "")).casefold()
    if body:
        payload["body_type"] = IMPORT_BODY_TYPES.get(body, body.capitalize())
    trim = _import_clean_line(values.get("trim", ""))
    if trim:
        payload["trim"] = trim
    grade = _import_clean_line(values.get("auction_grade", ""))
    if grade:
        payload["auction_grade"] = grade
    return payload


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
    body_custom = State()
    trim = State()
    auction_grade = State()
    price = State()
    photos = State()
    confirm = State()


class EditFlow(StatesGroup):
    listing_id = State()


class DeleteFlow(StatesGroup):
    listing_id = State()
    confirm = State()


@dataclass
class BotConfig:
    token: str
    api_base_url: str
    manager_api_key: str
    allowed_ids: set[int]


@dataclass
class AlbumBuffer:
    messages: list[Message] = field(default_factory=list)
    task: asyncio.Task | None = None


BTN_NEW = "Добавить карточку"
BTN_EDIT = "Изменить карточку"
BTN_DELETE = "Удалить карточку"
BTN_RECENT = "Показать последние карточки"
BTN_IMPORT_HELP = "Импорт из Telegram"


MAIN_MENU_KB = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text=BTN_NEW), KeyboardButton(text=BTN_EDIT)],
        [KeyboardButton(text=BTN_DELETE), KeyboardButton(text=BTN_RECENT)],
        [KeyboardButton(text=BTN_IMPORT_HELP)],
    ],
    resize_keyboard=True,
)


MARKET_KB = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="Китай"), KeyboardButton(text="Корея"), KeyboardButton(text="Япония")]],
    resize_keyboard=True,
)

DRIVE_KB = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Передний"), KeyboardButton(text="Задний")],
        [KeyboardButton(text="Полный")],
        [KeyboardButton(text="Отмена")],
    ],
    resize_keyboard=True,
)

DRIVE_EDIT_KB = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Передний"), KeyboardButton(text="Задний")],
        [KeyboardButton(text="Полный")],
        [KeyboardButton(text="Оставить")],
        [KeyboardButton(text="Отмена")],
    ],
    resize_keyboard=True,
)

BODY_KB = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Седан"), KeyboardButton(text="Универсал")],
        [KeyboardButton(text="Хэтчбек"), KeyboardButton(text="Купе")],
        [KeyboardButton(text="Джип"), KeyboardButton(text="Кроссовер")],
        [KeyboardButton(text="Другое")],
        [KeyboardButton(text="Отмена")],
    ],
    resize_keyboard=True,
)

BODY_EDIT_KB = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Седан"), KeyboardButton(text="Универсал")],
        [KeyboardButton(text="Хэтчбек"), KeyboardButton(text="Купе")],
        [KeyboardButton(text="Джип"), KeyboardButton(text="Кроссовер")],
        [KeyboardButton(text="Другое")],
        [KeyboardButton(text="Оставить")],
        [KeyboardButton(text="Отмена")],
    ],
    resize_keyboard=True,
)

EDIT_TEXT_KB = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="Оставить")], [KeyboardButton(text="Отмена")]],
    resize_keyboard=True,
)

TRIM_KB = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="Пропустить")], [KeyboardButton(text="Отмена")]],
    resize_keyboard=True,
)

TRIM_EDIT_KB = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Оставить")],
        [KeyboardButton(text="Пропустить")],
        [KeyboardButton(text="Отмена")],
    ],
    resize_keyboard=True,
)

AUCTION_GRADE_KB = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="Пропустить")], [KeyboardButton(text="Отмена")]],
    resize_keyboard=True,
)

AUCTION_GRADE_EDIT_KB = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Оставить")],
        [KeyboardButton(text="Пропустить")],
        [KeyboardButton(text="Отмена")],
    ],
    resize_keyboard=True,
)

PHOTOS_KB = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="Готово")], [KeyboardButton(text="Отмена")]],
    resize_keyboard=True,
)

PHOTOS_EDIT_KB = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Готово")],
        [KeyboardButton(text="Оставить фото")],
        [KeyboardButton(text="Отмена")],
    ],
    resize_keyboard=True,
)

CONFIRM_KB = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="Отправить"), KeyboardButton(text="Добавить фото")], [KeyboardButton(text="Отмена")]],
    resize_keyboard=True,
)

DELETE_CONFIRM_KB = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="Удалить")], [KeyboardButton(text="Отмена")]],
    resize_keyboard=True,
)


router = Router()
CONFIG: BotConfig | None = None
ALBUM_BUFFERS: dict[tuple[int, str], AlbumBuffer] = {}
ALBUM_WAIT_SECONDS = 1.2
APP_VERSION = "2026-06-22.telegram-import-v3"


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


async def deny_if_no_access(message: Message) -> bool:
    if check_access(message):
        return False
    await message.answer("Доступ запрещен для этого аккаунта.", reply_markup=ReplyKeyboardRemove())
    return True


async def send_main_menu(message: Message, text: str = "Выберите действие:") -> None:
    await message.answer(text, reply_markup=MAIN_MENU_KB)


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


def format_decimal_text(value: Decimal | None) -> str:
    if value is None:
        return ""
    text = format(value.normalize(), "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def parse_int(text: str) -> int | None:
    t = (text or "").strip().replace(" ", "")
    if not t or not t.isdigit():
        return None
    return int(t)


def market_to_api(value: str) -> str | None:
    v = (value or "").strip().lower()
    if v == "китай":
        return "china"
    if v == "корея":
        return "korea"
    if v == "япония":
        return "japan"
    return None


def market_to_human(value: str) -> str:
    market = str(value or "").strip().lower()
    if market == "china":
        return "Китай"
    if market == "korea":
        return "Корея"
    if market == "japan":
        return "Япония"
    return "—"


def is_edit_mode(data: dict) -> bool:
    return str(data.get("mode") or "").strip().lower() == "edit"


def is_keep(text: str) -> bool:
    return (text or "").strip().lower() == "оставить"


def is_skip(text: str) -> bool:
    return (text or "").strip().lower() == "пропустить"


def is_cancel(text: str) -> bool:
    return (text or "").strip().lower() == "отмена"


def body_mapping() -> dict[str, str]:
    return {
        "седан": "Седан",
        "универсал": "Универсал",
        "хэтчбек": "Хэтчбек",
        "купе": "Купе",
        "джип": "Джип",
        "кроссовер": "Кроссовер",
    }


def summarize_payload(data: dict) -> str:
    mode = "редактирование" if is_edit_mode(data) else "создание"
    market = str(data.get("market") or "")
    market_human = market_to_human(market)
    trim_val = str(data.get("trim") or "").strip()
    auction_grade_val = str(data.get("auction_grade") or "").strip()

    if is_edit_mode(data):
        replace_photos = bool(data.get("replace_photos"))
        if replace_photos:
            photos_line = f"заменить на {len(data.get('photo_file_ids', []))} шт."
        else:
            photos_line = "оставить текущие"
    else:
        photos_line = f"{len(data.get('photo_file_ids', []))} шт."

    lines = [
        "Проверьте карточку перед отправкой:",
        f"• Режим: {mode}",
        f"• Площадка: {market_human}",
        f"• Марка и модель: {str(data.get('brand') or '').strip()} {str(data.get('model') or '').strip()}".strip(),
        f"• Год: {data.get('year', '')}",
        f"• Пробег: {data.get('mileage_km', '')} км",
        f"• Привод: {data.get('drive_type', '')}",
        f"• Объем двигателя: {data.get('engine_volume_l', '')} л",
        f"• Л.С.: {data.get('power_hp', '')}",
        f"• Кузов: {data.get('body_type', '')}",
        f"• Комплектация: {trim_val or '—'}",
        f"• Цена: {data.get('price', '')}",
        f"• Фото: {photos_line}",
    ]
    if market == "japan":
        lines.insert(12, f"• Оценка по аукционному листу: {auction_grade_val or '—'}")
    if is_edit_mode(data):
        lines.insert(2, f"• ID карточки: {data.get('edit_listing_id', '')}")
    return "\n".join(lines)


def _extract_command_arg(text: str | None) -> str:
    raw = str(text or "").strip()
    if not raw:
        return ""
    parts = raw.split(maxsplit=1)
    if len(parts) < 2:
        return ""
    return parts[1].strip()


def format_exception_message(exc: BaseException) -> str:
    if isinstance(exc, TimeoutError):
        return "TimeoutError: таймаут при скачивании фото из Telegram или отправке данных"

    current: BaseException | None = exc
    seen: set[int] = set()
    parts: list[str] = []

    while current is not None and id(current) not in seen and len(parts) < 3:
        seen.add(id(current))
        name = current.__class__.__name__
        text = str(current).strip()
        parts.append(f"{name}: {text}" if text else name)
        current = current.__cause__ or current.__context__

    return " -> ".join(parts) if parts else exc.__class__.__name__


def is_supported_image_document(message: Message) -> bool:
    document = message.document
    if document is None:
        return False

    mime_type = str(document.mime_type or "").strip().lower()
    if mime_type.startswith("image/"):
        return True

    filename = str(document.file_name or "").strip().lower()
    return filename.endswith((".jpg", ".jpeg", ".png", ".webp"))


def extract_image_file_id(message: Message) -> str | None:
    photos = message.photo or []
    if photos:
        return photos[-1].file_id

    document = message.document
    if document is not None and is_supported_image_document(message):
        return document.file_id

    sticker = message.sticker
    if sticker is not None and not bool(sticker.is_animated) and not bool(sticker.is_video):
        return sticker.file_id

    animation = message.animation
    if animation is not None:
        mime_type = str(animation.mime_type or "").strip().lower()
        filename = str(animation.file_name or "").strip().lower()
        if mime_type.startswith("image/") or filename.endswith((".jpg", ".jpeg", ".png", ".webp")):
            return animation.file_id

    return None


def describe_message_payload(message: Message) -> str:
    parts: list[str] = []
    if message.content_type:
        parts.append(f"type={message.content_type}")
    if message.document:
        parts.append(f"document_mime={message.document.mime_type or '—'}")
        parts.append(f"document_name={message.document.file_name or '—'}")
    if message.sticker:
        parts.append(
            "sticker="
            f"animated:{bool(message.sticker.is_animated)},video:{bool(message.sticker.is_video)}"
        )
    if message.animation:
        parts.append(f"animation_mime={message.animation.mime_type or '—'}")
        parts.append(f"animation_name={message.animation.file_name or '—'}")
    return ", ".join(parts) or "type=unknown"


def guess_upload_meta(tg_file_path: str | None, fallback_name: str) -> tuple[str, str]:
    path = str(tg_file_path or "").strip()
    ext = os.path.splitext(path)[1].lower()
    if ext not in {".jpg", ".jpeg", ".png", ".webp"}:
        ext = ".jpg"

    content_type = mimetypes.types_map.get(ext)
    if ext in {".jpg", ".jpeg"}:
        content_type = "image/jpeg"
        ext = ".jpg"
    elif ext == ".png":
        content_type = "image/png"
    elif ext == ".webp":
        content_type = "image/webp"

    return f"{fallback_name}{ext}", content_type or "image/jpeg"


async def add_photo_file_id(message: Message, state: FSMContext, file_id: str) -> None:
    data = await state.get_data()
    file_ids = list(data.get("photo_file_ids", []))
    if len(file_ids) >= 20:
        await message.answer("Достигнут лимит 20 фото. Нажмите «Готово».")
        return

    file_ids.append(file_id)
    await state.update_data(photo_file_ids=file_ids, replace_photos=True)
    await message.answer(f"Фото добавлено: {len(file_ids)} шт.")


async def _api_json_request(method: str, path: str, *, params: dict | None = None) -> tuple[bool, object]:
    global CONFIG
    if CONFIG is None:
        return False, "CONFIG is not initialized"

    url = f"{CONFIG.api_base_url}{path}"
    headers = {"X-Manager-Api-Key": CONFIG.manager_api_key}
    timeout = aiohttp.ClientTimeout(total=40)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.request(method=method.upper(), url=url, headers=headers, params=params) as resp:
            text = await resp.text()
            if resp.status >= 300:
                return False, f"Backend error {resp.status}: {text[:600]}"
            try:
                return True, await resp.json()
            except Exception:
                return False, "Backend returned non-JSON response"


async def fetch_manual_listing(listing_id: str) -> tuple[bool, object]:
    return await _api_json_request("GET", f"/api/manager/manual-listing/{listing_id}")


async def list_recent_manual_listings(market: str = "all", limit: int = 10) -> tuple[bool, object]:
    params = {"market": market, "limit": str(limit), "offset": "0"}
    return await _api_json_request("GET", "/api/manager/manual-listings", params=params)


async def delete_manual_listing(listing_id: str) -> tuple[bool, object]:
    return await _api_json_request("DELETE", f"/api/manager/manual-listing/{listing_id}")


async def send_to_backend(bot: Bot, payload: dict) -> tuple[bool, str]:
    global CONFIG
    if CONFIG is None:
        return False, "CONFIG is not initialized"

    form = aiohttp.FormData()
    form.add_field("market", str(payload.get("market") or ""))
    form.add_field("brand", str(payload.get("brand") or ""))
    form.add_field("model", str(payload.get("model") or ""))
    optional_fields = (
        "year",
        "mileage_km",
        "drive_type",
        "engine_volume_l",
        "power_hp",
        "body_type",
        "trim",
        "price",
        "auction_grade",
    )
    for field_name in optional_fields:
        field_value = str(payload.get(field_name) or "").strip()
        if field_value:
            form.add_field(field_name, field_value)

    listing_id = str(payload.get("edit_listing_id") or "").strip()
    if listing_id:
        form.add_field("listing_id", listing_id)

    replace_photos = bool(payload.get("replace_photos", True))
    form.add_field("replace_photos", "1" if replace_photos else "0")

    for idx, file_id in enumerate(payload.get("photo_file_ids", [])):
        tg_file = await bot.get_file(file_id)
        stream = io.BytesIO()
        await bot.download(tg_file, destination=stream)
        stream.seek(0)
        filename, content_type = guess_upload_meta(tg_file.file_path, f"photo_{idx + 1}")
        form.add_field(
            "photos",
            stream.read(),
            filename=filename,
            content_type=content_type,
        )

    url = f"{CONFIG.api_base_url}/api/manager/manual-listing"
    headers = {"X-Manager-Api-Key": CONFIG.manager_api_key}
    timeout = aiohttp.ClientTimeout(total=180)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(url, data=form, headers=headers) as resp:
            text = await resp.text()
            if resp.status >= 300:
                return False, f"Backend error {resp.status}: {text[:600]}"
            return True, text


async def maybe_cancel(message: Message, state: FSMContext) -> bool:
    if not is_cancel(message.text or ""):
        return False
    await state.clear()
    await send_main_menu(message, "Диалог отменен. Выберите действие:")
    return True


def _fmt_current(value: object) -> str:
    s = str(value or "").strip()
    return s or "—"


async def ask_brand(message: Message, data: dict) -> None:
    if is_edit_mode(data):
        await message.answer(
            f"Введите марку (текущая: {_fmt_current(data.get('brand'))}) или нажмите «Оставить».",
            reply_markup=EDIT_TEXT_KB,
        )
    else:
        await message.answer("Введите марку (например: Hyundai):", reply_markup=ReplyKeyboardRemove())


async def ask_model(message: Message, data: dict) -> None:
    if is_edit_mode(data):
        await message.answer(
            f"Введите модель (текущая: {_fmt_current(data.get('model'))}) или нажмите «Оставить».",
            reply_markup=EDIT_TEXT_KB,
        )
    else:
        await message.answer("Введите модель (например: Sonata):", reply_markup=ReplyKeyboardRemove())


async def ask_year(message: Message, data: dict) -> None:
    if is_edit_mode(data):
        await message.answer(
            f"Введите год YYYY (текущий: {_fmt_current(data.get('year'))}) или «Оставить».",
            reply_markup=EDIT_TEXT_KB,
        )
    else:
        await message.answer("Введите год (YYYY):", reply_markup=ReplyKeyboardRemove())


async def ask_mileage(message: Message, data: dict) -> None:
    if is_edit_mode(data):
        await message.answer(
            f"Введите пробег в км (текущий: {_fmt_current(data.get('mileage_km'))}) или «Оставить».",
            reply_markup=EDIT_TEXT_KB,
        )
    else:
        await message.answer("Введите пробег в км (например 86000):", reply_markup=ReplyKeyboardRemove())


async def ask_drive(message: Message, data: dict) -> None:
    if is_edit_mode(data):
        await message.answer(
            f"Выберите привод (текущий: {_fmt_current(data.get('drive_type'))}) или «Оставить».",
            reply_markup=DRIVE_EDIT_KB,
        )
    else:
        await message.answer("Выберите привод:", reply_markup=DRIVE_KB)


async def ask_engine_volume(message: Message, data: dict) -> None:
    if is_edit_mode(data):
        await message.answer(
            f"Введите объем двигателя в литрах (текущий: {_fmt_current(data.get('engine_volume_l'))}) или «Оставить».",
            reply_markup=EDIT_TEXT_KB,
        )
    else:
        await message.answer("Введите объем двигателя в литрах (например 2.0):", reply_markup=ReplyKeyboardRemove())


async def ask_power(message: Message, data: dict) -> None:
    if is_edit_mode(data):
        await message.answer(
            f"Введите мощность в л.с. (текущая: {_fmt_current(data.get('power_hp'))}) или «Оставить».",
            reply_markup=EDIT_TEXT_KB,
        )
    else:
        await message.answer("Введите мощность в л.с. (например 204):", reply_markup=ReplyKeyboardRemove())


async def ask_body_type(message: Message, data: dict) -> None:
    if is_edit_mode(data):
        await message.answer(
            f"Выберите тип кузова (текущий: {_fmt_current(data.get('body_type'))}).",
            reply_markup=BODY_EDIT_KB,
        )
    else:
        await message.answer("Выберите тип кузова:", reply_markup=BODY_KB)


async def ask_trim(message: Message, data: dict) -> None:
    if is_edit_mode(data):
        await message.answer(
            f"Введите комплектацию (текущая: {_fmt_current(data.get('trim'))}) или «Оставить»/«Пропустить».",
            reply_markup=TRIM_EDIT_KB,
        )
    else:
        await message.answer(
            "Введите комплектацию или нажмите «Пропустить».",
            reply_markup=TRIM_KB,
        )


async def ask_auction_grade(message: Message, data: dict) -> None:
    if is_edit_mode(data):
        await message.answer(
            f"Оценка по аукционному листу (текущая: {_fmt_current(data.get('auction_grade'))}) или «Оставить»/«Пропустить».",
            reply_markup=AUCTION_GRADE_EDIT_KB,
        )
    else:
        await message.answer(
            "Введите оценку по аукционному листу или нажмите «Пропустить».",
            reply_markup=AUCTION_GRADE_KB,
        )


async def ask_price(message: Message, data: dict) -> None:
    if is_edit_mode(data):
        await message.answer(
            f"Введите конечную цену во Владивостоке (текущая: {_fmt_current(data.get('price'))}) или «Оставить».",
            reply_markup=EDIT_TEXT_KB,
        )
    else:
        await message.answer(
            "Введите конечную цену во Владивостоке с учетом нашей комиссии (только число, например 156000):",
            reply_markup=ReplyKeyboardRemove(),
        )


async def ask_photos(message: Message, data: dict) -> None:
    if is_edit_mode(data):
        current_count = int(data.get("existing_photo_count") or 0)
        await message.answer(
            "Отправьте новые фото (полная замена текущих). "
            f"Сейчас в карточке: {current_count} шт. "
            "Нажмите «Оставить фото», если менять не нужно, либо «Готово» после загрузки.",
            reply_markup=PHOTOS_EDIT_KB,
        )
    else:
        await message.answer(
            "Загрузите фото или файлы-изображения JPG/PNG/WEBP (можно несколько сообщений). Когда закончите, нажмите «Готово».",
            reply_markup=PHOTOS_KB,
        )


async def ask_edit_listing_id(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Введите UUID карточки, которую нужно изменить:", reply_markup=ReplyKeyboardRemove())
    await state.set_state(EditFlow.listing_id)


async def ask_delete_listing_id(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Введите UUID карточки, которую нужно удалить:", reply_markup=ReplyKeyboardRemove())
    await state.set_state(DeleteFlow.listing_id)


async def process_forwarded_listing(
    message: Message,
    state: FSMContext,
    *,
    caption: str,
    photo_file_ids: list[str],
) -> None:
    logging.info(
        "telegram_import_received chat_id=%s caption_length=%s photos=%s",
        message.chat.id,
        len(caption),
        len(photo_file_ids),
    )
    parsed = parse_forwarded_listing(caption)
    if not parsed:
        logging.warning("telegram_import_parse_empty chat_id=%s", message.chat.id)
        await message.answer(
            "Не удалось распознать карточку. Перешлите исходную публикацию с подписью и фотографиями "
            "или используйте «Добавить карточку» для ручного ввода."
        )
        return

    unique_file_ids = list(dict.fromkeys(photo_file_ids))[:20]
    if not parsed.get("market"):
        logging.warning("telegram_import_market_missing chat_id=%s parsed=%s", message.chat.id, parsed)
        await message.answer(
            "Не удалось определить площадку (Китай, Корея или Япония), поэтому карточку нельзя направить "
            "в нужный раздел сайта. Публикация не импортирована."
        )
        return
    if not unique_file_ids:
        logging.warning("telegram_import_photos_missing chat_id=%s", message.chat.id)
        await message.answer("В публикации нет фотографий. Публикация не импортирована.")
        return

    await state.clear()
    imported_data = {
        "mode": "create",
        "trim": "",
        "auction_grade": "",
        "replace_photos": True,
        "photo_file_ids": unique_file_ids,
        **parsed,
    }
    await state.update_data(**imported_data)
    data = await state.get_data()
    recognized_title = f"{str(data.get('brand') or '').strip()} {str(data.get('model') or '').strip()}".strip()
    status_lines = [
        "Карточка из Telegram распознана.",
        f"Автомобиль: {recognized_title or 'не определен'}",
        f"Фото: {len(unique_file_ids)} шт.",
        "На сайт будут отправлены только данные из публикации.",
    ]
    await message.answer("\n".join(status_lines), reply_markup=ReplyKeyboardRemove())
    await message.answer(summarize_payload(data), reply_markup=CONFIRM_KB)
    await state.set_state(ListingFlow.confirm)
    logging.info(
        "telegram_import_ready chat_id=%s market=%s title=%r photos=%s",
        message.chat.id,
        data.get("market"),
        recognized_title,
        len(unique_file_ids),
    )


async def _finish_album(key: tuple[int, str], state: FSMContext) -> None:
    try:
        await asyncio.sleep(ALBUM_WAIT_SECONDS)
    except asyncio.CancelledError:
        return

    buffer: AlbumBuffer | None = None
    try:
        buffer = ALBUM_BUFFERS.pop(key, None)
        if buffer is None or not buffer.messages:
            return
        messages = sorted(buffer.messages, key=lambda item: item.message_id)
        caption = next(
            (str(item.caption or item.text or "").strip() for item in messages if str(item.caption or item.text or "").strip()),
            "",
        )
        file_ids = [file_id for item in messages if (file_id := extract_image_file_id(item))]
        logging.info(
            "telegram_import_album_ready chat_id=%s media_group_id=%s messages=%s photos=%s",
            key[0],
            key[1],
            len(messages),
            len(file_ids),
        )
        await process_forwarded_listing(messages[0], state, caption=caption, photo_file_ids=file_ids)
    except Exception:
        logging.exception("telegram_import_album_failed chat_id=%s media_group_id=%s", key[0], key[1])
        if buffer is not None and buffer.messages:
            try:
                await buffer.messages[0].answer(
                    "Ошибка обработки пересланной публикации. Подробности записаны в журнал бота."
                )
            except Exception:
                logging.exception("telegram_import_error_reply_failed chat_id=%s", key[0])


async def start_new_flow(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.update_data(mode="create", photo_file_ids=[], replace_photos=True)
    await message.answer("Создаем новую карточку. Выберите площадку:", reply_markup=MARKET_KB)
    await state.set_state(ListingFlow.market)


async def start_edit_flow(message: Message, state: FSMContext, listing_id: str) -> None:
    ok, payload = await fetch_manual_listing(listing_id)
    if not ok:
        await message.answer(f"Не удалось загрузить карточку: {payload}")
        return
    if not isinstance(payload, dict):
        await message.answer("Неожиданный ответ backend при загрузке карточки.")
        return

    market = str(payload.get("market") or "").strip().lower()
    if market not in {"china", "korea", "japan"}:
        await message.answer("Карточка не относится к рынкам Китай/Корея/Япония.")
        return

    await state.clear()
    await state.update_data(
        mode="edit",
        edit_listing_id=str(payload.get("id") or listing_id),
        market=market,
        brand=str(payload.get("brand") or "").strip(),
        model=str(payload.get("model") or "").strip(),
        year=payload.get("year"),
        mileage_km=payload.get("mileage_km"),
        drive_type=str(payload.get("drive_type") or "").strip(),
        engine_volume_l=str(payload.get("engine_volume_l") or "").strip(),
        power_hp=payload.get("power_hp"),
        body_type=str(payload.get("body_type") or "").strip(),
        trim=str(payload.get("trim") or "").strip(),
        auction_grade=str(payload.get("auction_grade") or "").strip(),
        price=str(payload.get("price") or "").strip(),
        photo_file_ids=[],
        replace_photos=False,
        existing_photo_count=int(payload.get("images_count") or 0),
    )

    title = f"{str(payload.get('brand') or '').strip()} {str(payload.get('model') or '').strip()}".strip()
    await message.answer(
        "Режим редактирования карточки.\n"
        f"ID: {payload.get('id')}\n"
        f"Площадка: {market_to_human(market)}\n"
        f"Текущая карточка: {title or '—'}",
        reply_markup=ReplyKeyboardRemove(),
    )
    data = await state.get_data()
    await ask_brand(message, data)
    await state.set_state(ListingFlow.brand)


async def show_recent_listings(message: Message, market: str = "all") -> None:
    ok, payload = await list_recent_manual_listings(market=market, limit=10)
    if not ok:
        await message.answer(f"Не удалось получить список: {payload}")
        return
    if not isinstance(payload, dict):
        await message.answer("Неожиданный ответ backend.")
        return

    items = payload.get("items") if isinstance(payload.get("items"), list) else []
    if not items:
        await message.answer("Карточек не найдено.")
        return

    lines = ["Последние карточки:"]
    for item in items:
        if not isinstance(item, dict):
            continue
        listing_id = str(item.get("id") or "")
        market_human = market_to_human(str(item.get("market") or ""))
        title = f"{str(item.get('brand') or '').strip()} {str(item.get('model') or '').strip()}".strip() or "Без названия"
        lines.append(f"• {listing_id} | {market_human} | {title}")
    await message.answer("\n".join(lines))


@router.message(CommandStart())
async def start(message: Message, state: FSMContext) -> None:
    if await deny_if_no_access(message):
        return
    await state.clear()
    await send_main_menu(message, "Готово. Выберите действие:")


@router.message(Command("new"))
async def start_new_command(message: Message, state: FSMContext) -> None:
    if await deny_if_no_access(message):
        return
    await start_new_flow(message, state)


@router.message(StateFilter(None), F.text == BTN_NEW)
async def start_new_button(message: Message, state: FSMContext) -> None:
    if await deny_if_no_access(message):
        return
    await start_new_flow(message, state)


@router.message(StateFilter(None), F.text == BTN_IMPORT_HELP)
async def import_help(message: Message) -> None:
    if await deny_if_no_access(message):
        return
    await message.answer(
        "Перешлите боту публикацию из Telegram-канала целиком: подпись и альбом фотографий. "
        "Бот заполнит найденные поля и покажет карточку перед сохранением. "
        "Отсутствующие характеристики запрашиваться не будут.",
        reply_markup=MAIN_MENU_KB,
    )


@router.message(StateFilter(None), F.photo | F.document)
async def import_forwarded_media(message: Message, state: FSMContext) -> None:
    if await deny_if_no_access(message):
        return

    file_id = extract_image_file_id(message)
    if not file_id:
        await message.answer("Файл не похож на изображение. Перешлите публикацию с JPG, PNG или WEBP.")
        return

    media_group_id = str(message.media_group_id or "").strip()
    logging.info(
        "telegram_import_media chat_id=%s message_id=%s media_group_id=%s has_caption=%s",
        message.chat.id,
        message.message_id,
        media_group_id or "single",
        bool(message.caption or message.text),
    )
    if not media_group_id:
        await process_forwarded_listing(
            message,
            state,
            caption=str(message.caption or message.text or "").strip(),
            photo_file_ids=[file_id],
        )
        return

    key = (int(message.chat.id), media_group_id)
    buffer = ALBUM_BUFFERS.setdefault(key, AlbumBuffer())
    buffer.messages.append(message)
    if buffer.task is not None and not buffer.task.done():
        buffer.task.cancel()
    buffer.task = asyncio.create_task(_finish_album(key, state))


@router.message(Command("edit"))
async def edit_start_command(message: Message, state: FSMContext) -> None:
    if await deny_if_no_access(message):
        return

    arg = _extract_command_arg(message.text)
    if arg:
        try:
            str(uuid.UUID(arg))
        except Exception:
            await message.answer("Неверный формат ID. Нужен UUID карточки.")
            return
        await start_edit_flow(message, state, arg)
        return

    await ask_edit_listing_id(message, state)


@router.message(StateFilter(None), F.text == BTN_EDIT)
async def edit_start_button(message: Message, state: FSMContext) -> None:
    if await deny_if_no_access(message):
        return
    await ask_edit_listing_id(message, state)


@router.message(EditFlow.listing_id)
async def edit_get_id(message: Message, state: FSMContext) -> None:
    if await deny_if_no_access(message):
        return
    if await maybe_cancel(message, state):
        return

    listing_id = (message.text or "").strip()
    try:
        str(uuid.UUID(listing_id))
    except Exception:
        await message.answer("Неверный формат ID. Нужен UUID карточки.")
        return

    await start_edit_flow(message, state, listing_id)


@router.message(Command("delete"))
async def delete_start_command(message: Message, state: FSMContext) -> None:
    if await deny_if_no_access(message):
        return

    arg = _extract_command_arg(message.text)
    if arg:
        try:
            str(uuid.UUID(arg))
        except Exception:
            await message.answer("Неверный формат ID. Нужен UUID карточки.")
            return
        ok, payload = await fetch_manual_listing(arg)
        if not ok:
            await message.answer(f"Не удалось загрузить карточку: {payload}")
            return
        if not isinstance(payload, dict):
            await message.answer("Неожиданный ответ backend.")
            return

        title = f"{str(payload.get('brand') or '').strip()} {str(payload.get('model') or '').strip()}".strip()
        await state.clear()
        await state.update_data(delete_listing_id=arg, delete_preview_title=title)
        await message.answer(
            "Подтвердите удаление карточки:\n"
            f"ID: {arg}\n"
            f"Карточка: {title or '—'}",
            reply_markup=DELETE_CONFIRM_KB,
        )
        await state.set_state(DeleteFlow.confirm)
        return

    await ask_delete_listing_id(message, state)


@router.message(StateFilter(None), F.text == BTN_DELETE)
async def delete_start_button(message: Message, state: FSMContext) -> None:
    if await deny_if_no_access(message):
        return
    await ask_delete_listing_id(message, state)


@router.message(DeleteFlow.listing_id)
async def delete_get_id(message: Message, state: FSMContext) -> None:
    if await deny_if_no_access(message):
        return
    if await maybe_cancel(message, state):
        return

    listing_id = (message.text or "").strip()
    try:
        str(uuid.UUID(listing_id))
    except Exception:
        await message.answer("Неверный формат ID. Нужен UUID карточки.")
        return

    ok, payload = await fetch_manual_listing(listing_id)
    if not ok:
        await message.answer(f"Не удалось загрузить карточку: {payload}")
        return
    if not isinstance(payload, dict):
        await message.answer("Неожиданный ответ backend.")
        return

    title = f"{str(payload.get('brand') or '').strip()} {str(payload.get('model') or '').strip()}".strip()
    await state.update_data(delete_listing_id=listing_id, delete_preview_title=title)
    await message.answer(
        "Подтвердите удаление карточки:\n"
        f"ID: {listing_id}\n"
        f"Карточка: {title or '—'}",
        reply_markup=DELETE_CONFIRM_KB,
    )
    await state.set_state(DeleteFlow.confirm)


@router.message(DeleteFlow.confirm)
async def delete_confirm(message: Message, state: FSMContext) -> None:
    if await deny_if_no_access(message):
        return
    if await maybe_cancel(message, state):
        return

    cmd = (message.text or "").strip().lower()
    if cmd != "удалить":
        await message.answer("Нажмите «Удалить» или «Отмена».", reply_markup=DELETE_CONFIRM_KB)
        return

    data = await state.get_data()
    listing_id = str(data.get("delete_listing_id") or "").strip()
    if not listing_id:
        await state.clear()
        await send_main_menu(message, "Состояние удалено. Выберите действие:")
        return

    ok, payload = await delete_manual_listing(listing_id)
    if not ok:
        await message.answer(f"Ошибка удаления: {payload}")
        return

    await state.clear()
    await send_main_menu(message, f"Карточка удалена: {listing_id}")


@router.message(Command("recent"))
async def recent_listings(message: Message) -> None:
    if await deny_if_no_access(message):
        return

    arg = _extract_command_arg(message.text).lower()
    market = "all"
    if arg in {"china", "китай"}:
        market = "china"
    elif arg in {"korea", "корея"}:
        market = "korea"
    elif arg in {"japan", "япония"}:
        market = "japan"
    await show_recent_listings(message, market=market)

 
@router.message(StateFilter(None), F.text == BTN_RECENT)
async def recent_listings_button(message: Message) -> None:
    if await deny_if_no_access(message):
        return
    await show_recent_listings(message, market="all")


@router.message(Command("cancel"))
async def cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await send_main_menu(message, "Ок, диалог сброшен. Выберите действие:")


@router.message(ListingFlow.market)
async def on_market(message: Message, state: FSMContext) -> None:
    if await deny_if_no_access(message):
        return
    if await maybe_cancel(message, state):
        return

    market = market_to_api(message.text or "")
    if not market:
        await message.answer("Нужно выбрать: Китай, Корея или Япония.", reply_markup=MARKET_KB)
        return

    await state.update_data(market=market, photo_file_ids=[], replace_photos=True)
    data = await state.get_data()
    await ask_brand(message, data)
    await state.set_state(ListingFlow.brand)


@router.message(ListingFlow.brand)
async def on_brand(message: Message, state: FSMContext) -> None:
    if await deny_if_no_access(message):
        return
    if await maybe_cancel(message, state):
        return

    data = await state.get_data()
    txt = (message.text or "").strip()
    if is_edit_mode(data) and is_keep(txt):
        brand = str(data.get("brand") or "").strip()
        if len(brand) < 2:
            await message.answer("Текущее значение пустое. Введите марку.")
            return
    else:
        brand = txt
        if len(brand) < 2:
            await message.answer("Слишком короткая марка. Введите еще раз.")
            return

    await state.update_data(brand=brand)
    data = await state.get_data()
    await ask_model(message, data)
    await state.set_state(ListingFlow.model)


@router.message(ListingFlow.model)
async def on_model(message: Message, state: FSMContext) -> None:
    if await deny_if_no_access(message):
        return
    if await maybe_cancel(message, state):
        return

    data = await state.get_data()
    txt = (message.text or "").strip()
    if is_edit_mode(data) and is_keep(txt):
        model = str(data.get("model") or "").strip()
        if len(model) < 1:
            await message.answer("Текущее значение пустое. Введите модель.")
            return
    else:
        model = txt
        if len(model) < 1:
            await message.answer("Введите модель.")
            return

    await state.update_data(model=model)
    data = await state.get_data()
    await ask_year(message, data)
    await state.set_state(ListingFlow.year)


@router.message(ListingFlow.year)
async def on_year(message: Message, state: FSMContext) -> None:
    if await deny_if_no_access(message):
        return
    if await maybe_cancel(message, state):
        return

    data = await state.get_data()
    txt = (message.text or "").strip()
    if is_edit_mode(data) and is_keep(txt):
        year_raw = data.get("year")
        year = int(year_raw) if isinstance(year_raw, int) else parse_year(str(year_raw or ""))
        if year is None:
            await message.answer("Текущее значение пустое/некорректное. Введите год YYYY.")
            return
    else:
        year = parse_year(txt)
        if year is None:
            await message.answer("Год должен быть числом в формате YYYY (например 2021).")
            return

    await state.update_data(year=year)
    data = await state.get_data()
    await ask_mileage(message, data)
    await state.set_state(ListingFlow.mileage_km)


@router.message(ListingFlow.mileage_km)
async def on_mileage(message: Message, state: FSMContext) -> None:
    if await deny_if_no_access(message):
        return
    if await maybe_cancel(message, state):
        return

    data = await state.get_data()
    txt = (message.text or "").strip()
    if is_edit_mode(data) and is_keep(txt):
        mileage_raw = data.get("mileage_km")
        mileage_km = int(mileage_raw) if isinstance(mileage_raw, int) else parse_int(str(mileage_raw or ""))
        if mileage_km is None or mileage_km <= 0:
            await message.answer("Текущее значение пустое/некорректное. Введите пробег в км.")
            return
    else:
        mileage_km = parse_int(txt)
        if mileage_km is None or mileage_km <= 0:
            await message.answer("Пробег должен быть целым числом в км (например 86000).")
            return

    await state.update_data(mileage_km=mileage_km)
    data = await state.get_data()
    await ask_drive(message, data)
    await state.set_state(ListingFlow.drive_type)


@router.message(ListingFlow.drive_type)
async def on_drive(message: Message, state: FSMContext) -> None:
    if await deny_if_no_access(message):
        return
    if await maybe_cancel(message, state):
        return

    data = await state.get_data()
    value = (message.text or "").strip().lower()
    mapping = {
        "передний": "Передний",
        "задний": "Задний",
        "полный": "Полный",
    }

    if is_edit_mode(data) and is_keep(value):
        drive_type = str(data.get("drive_type") or "").strip()
        if not drive_type:
            await message.answer("Текущее значение пустое. Выберите привод.")
            return
    else:
        if value not in mapping:
            await message.answer(
                "Выберите один из вариантов на клавиатуре.",
                reply_markup=DRIVE_EDIT_KB if is_edit_mode(data) else DRIVE_KB,
            )
            return
        drive_type = mapping[value]

    await state.update_data(drive_type=drive_type)
    data = await state.get_data()
    await ask_engine_volume(message, data)
    await state.set_state(ListingFlow.engine_volume_l)


@router.message(ListingFlow.engine_volume_l)
async def on_engine_volume(message: Message, state: FSMContext) -> None:
    if await deny_if_no_access(message):
        return
    if await maybe_cancel(message, state):
        return

    data = await state.get_data()
    txt = (message.text or "").strip()
    if is_edit_mode(data) and is_keep(txt):
        dv = parse_decimal(str(data.get("engine_volume_l") or ""))
        if dv is None or dv <= 0:
            await message.answer("Текущее значение пустое/некорректное. Введите объем двигателя.")
            return
    else:
        dv = parse_decimal(txt)
        if dv is None or dv <= 0:
            await message.answer("Объем должен быть числом больше 0 (например 1.6).")
            return

    await state.update_data(engine_volume_l=format_decimal_text(dv))
    data = await state.get_data()
    await ask_power(message, data)
    await state.set_state(ListingFlow.power_hp)


@router.message(ListingFlow.power_hp)
async def on_power(message: Message, state: FSMContext) -> None:
    if await deny_if_no_access(message):
        return
    if await maybe_cancel(message, state):
        return

    data = await state.get_data()
    txt = (message.text or "").strip()
    if is_edit_mode(data) and is_keep(txt):
        hp_raw = data.get("power_hp")
        hp = int(hp_raw) if isinstance(hp_raw, int) else parse_int(str(hp_raw or ""))
        if hp is None or hp <= 0:
            await message.answer("Текущее значение пустое/некорректное. Введите мощность.")
            return
    else:
        hp = parse_int(txt)
        if hp is None or hp <= 0:
            await message.answer("Мощность должна быть целым числом (например 204).")
            return

    await state.update_data(power_hp=hp)
    data = await state.get_data()
    await ask_body_type(message, data)
    await state.set_state(ListingFlow.body_type)


@router.message(ListingFlow.body_type)
async def on_body(message: Message, state: FSMContext) -> None:
    if await deny_if_no_access(message):
        return
    if await maybe_cancel(message, state):
        return

    data = await state.get_data()
    txt = (message.text or "").strip()
    lower = txt.lower()

    if is_edit_mode(data) and is_keep(lower):
        body = str(data.get("body_type") or "").strip()
        if not body:
            await message.answer("Текущее значение пустое. Выберите кузов.")
            return
        await state.update_data(body_type=body)
    else:
        mapping = body_mapping()
        if lower == "другое":
            await message.answer("Введите тип кузова текстом:", reply_markup=ReplyKeyboardRemove())
            await state.set_state(ListingFlow.body_custom)
            return
        body = mapping.get(lower)
        if not body:
            await message.answer(
                "Выберите вариант на клавиатуре или «Другое».",
                reply_markup=BODY_EDIT_KB if is_edit_mode(data) else BODY_KB,
            )
            return
        await state.update_data(body_type=body)

    data = await state.get_data()
    await ask_trim(message, data)
    await state.set_state(ListingFlow.trim)


@router.message(ListingFlow.body_custom)
async def on_body_custom(message: Message, state: FSMContext) -> None:
    if await deny_if_no_access(message):
        return
    if await maybe_cancel(message, state):
        return

    body = (message.text or "").strip()
    if len(body) < 2:
        await message.answer("Введите тип кузова текстом (минимум 2 символа).")
        return

    await state.update_data(body_type=body)
    data = await state.get_data()
    await ask_trim(message, data)
    await state.set_state(ListingFlow.trim)


@router.message(ListingFlow.trim)
async def on_trim(message: Message, state: FSMContext) -> None:
    if await deny_if_no_access(message):
        return
    if await maybe_cancel(message, state):
        return

    data = await state.get_data()
    txt = (message.text or "").strip()

    if is_edit_mode(data) and is_keep(txt):
        trim = str(data.get("trim") or "").strip()
    elif is_skip(txt):
        trim = ""
    else:
        trim = txt
        if trim and len(trim) < 2:
            await message.answer("Слишком короткая комплектация. Введите еще раз или «Пропустить».")
            return

    await state.update_data(trim=trim)
    data = await state.get_data()
    market = str(data.get("market") or "")
    if market == "japan":
        await ask_auction_grade(message, data)
        await state.set_state(ListingFlow.auction_grade)
        return

    await ask_price(message, data)
    await state.set_state(ListingFlow.price)


@router.message(ListingFlow.auction_grade)
async def on_auction_grade(message: Message, state: FSMContext) -> None:
    if await deny_if_no_access(message):
        return
    if await maybe_cancel(message, state):
        return

    data = await state.get_data()
    txt = (message.text or "").strip()

    if is_edit_mode(data) and is_keep(txt):
        auction_grade = str(data.get("auction_grade") or "").strip()
    elif is_skip(txt):
        auction_grade = ""
    else:
        auction_grade = txt
        if len(auction_grade) > 32:
            await message.answer("Слишком длинная оценка. Введите короче (до 32 символов).")
            return

    await state.update_data(auction_grade=auction_grade)
    data = await state.get_data()
    await ask_price(message, data)
    await state.set_state(ListingFlow.price)


@router.message(ListingFlow.price)
async def on_price(message: Message, state: FSMContext) -> None:
    if await deny_if_no_access(message):
        return
    if await maybe_cancel(message, state):
        return

    data = await state.get_data()
    txt = (message.text or "").strip()

    if is_edit_mode(data) and is_keep(txt):
        price_dec = parse_decimal(str(data.get("price") or ""))
        if price_dec is None or price_dec <= 0:
            await message.answer("Текущее значение пустое/некорректное. Введите цену.")
            return
    else:
        price_dec = parse_decimal(txt)
        if price_dec is None or price_dec <= 0:
            await message.answer("Цена должна быть числом больше 0.")
            return

    await state.update_data(price=format_decimal_text(price_dec), photo_file_ids=[])
    data = await state.get_data()
    await ask_photos(message, data)
    await state.set_state(ListingFlow.photos)


@router.message(ListingFlow.photos, F.photo)
async def on_photo(message: Message, state: FSMContext) -> None:
    if await deny_if_no_access(message):
        return

    file_id = extract_image_file_id(message)
    if not file_id:
        await message.answer("Фото не найдено, отправьте еще раз.")
        return

    await add_photo_file_id(message, state, file_id)


@router.message(ListingFlow.photos, F.document)
async def on_photo_document(message: Message, state: FSMContext) -> None:
    if await deny_if_no_access(message):
        return

    file_id = extract_image_file_id(message)
    if not file_id:
        await message.answer("Файл не похож на изображение. Пришлите JPG, PNG или WEBP.")
        return

    await add_photo_file_id(message, state, file_id)


@router.message(ListingFlow.photos)
async def on_photos_text(message: Message, state: FSMContext) -> None:
    if await deny_if_no_access(message):
        return
    if await maybe_cancel(message, state):
        return

    file_id = extract_image_file_id(message)
    if file_id:
        await add_photo_file_id(message, state, file_id)
        return

    data = await state.get_data()
    txt = (message.text or "").strip().lower()
    edit_mode = is_edit_mode(data)

    if edit_mode and txt == "оставить фото":
        await state.update_data(replace_photos=False, photo_file_ids=[])
        payload = await state.get_data()
        await message.answer(summarize_payload(payload), reply_markup=CONFIRM_KB)
        await state.set_state(ListingFlow.confirm)
        return

    if txt != "готово":
        if not txt:
            await message.answer(
                "Не смог распознать файл как фото. "
                f"Диагностика: {describe_message_payload(message)}. "
                "Пришлите JPG, PNG или WEBP как файл."
            )
            return
        await message.answer(
            "Пришлите фото или нажмите «Готово»." if not edit_mode else "Пришлите фото, нажмите «Оставить фото» или «Готово»."
        )
        return

    file_ids = list(data.get("photo_file_ids", []))
    if file_ids:
        await state.update_data(replace_photos=True)
    elif edit_mode:
        await state.update_data(replace_photos=False)
    else:
        await message.answer("Нужно загрузить минимум одно фото.")
        return

    payload = await state.get_data()
    await message.answer(summarize_payload(payload), reply_markup=CONFIRM_KB)
    await state.set_state(ListingFlow.confirm)


@router.message(ListingFlow.confirm)
async def on_confirm(message: Message, state: FSMContext, bot: Bot) -> None:
    if await deny_if_no_access(message):
        return
    if await maybe_cancel(message, state):
        return

    cmd = (message.text or "").strip().lower()

    if cmd == "добавить фото":
        data = await state.get_data()
        await state.update_data(replace_photos=True)
        await ask_photos(message, data)
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
        await message.answer(f"Ошибка отправки: {format_exception_message(exc)}")
        return

    if not ok:
        await message.answer(f"Сервер вернул ошибку:\n{backend_text}")
        return

    await state.clear()
    await send_main_menu(message, "Карточка успешно сохранена. Выберите действие:")


@router.message()
async def fallback(message: Message) -> None:
    if await deny_if_no_access(message):
        return
    await send_main_menu(
        message,
        "Выберите действие кнопками ниже.\n"
        "Можно также переслать публикацию с карточкой и фото.\n"
        "Команды: /new, /edit, /delete, /recent, /cancel",
    )


async def main() -> None:
    global CONFIG
    CONFIG = load_config()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    bot = Bot(token=CONFIG.token)
    dispatcher_kwargs = {"storage": MemoryStorage()}
    if SimpleEventIsolation is not None:
        dispatcher_kwargs["events_isolation"] = SimpleEventIsolation()
    dp = Dispatcher(**dispatcher_kwargs)
    dp.include_router(router)

    logging.info("manager-listings-bot started version=%s", APP_VERSION)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
