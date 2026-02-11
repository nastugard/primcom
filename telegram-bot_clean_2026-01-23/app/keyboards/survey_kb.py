from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, KeyboardButtonPollType
from aiogram.utils.keyboard import ReplyKeyboardBuilder

def get_car_categories_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    categories = [
        "Седан", "Внедорожник", 
        "Хэтчбек", "Универсал",
        "Минивэн", "Кроссовер",
        "Спорткар", "Другое"
    ]
    for cat in categories:
        builder.button(text=cat)
    builder.adjust(2) # 2 columns
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=True)

def get_steering_wheel_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.button(text="Слева")
    builder.button(text="Справа")
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=True)

def get_budget_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    budgets = [
        "до 1 млн руб.",
        "1-1.5 млн руб.",
        "1.5-2 млн руб.",
        "2-3 млн руб.",
        "более 3 млн руб."
    ]
    for b in budgets:
        builder.button(text=b)
    builder.adjust(1) # 1 column for long text
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=True)

def get_contact_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.button(text="ПОДЕЛИТЬСЯ КОНТАКТОМ", request_contact=True)
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=True)
