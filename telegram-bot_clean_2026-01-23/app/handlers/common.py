from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from app.keyboards.start_kb import get_start_keyboard

router = Router()

@router.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "🏎 Рады приветствовать вас в компании ПРИМКОМ! Мы привозим авто прямиком из Азии.\n\n"
        "В данном боте вы можете ознакомиться с нашими услугами, а также оставить заявку для быстрого просчета авто.\n"
        "Чтобы начать просто нажмите 'Старт'",
        reply_markup=get_start_keyboard()
    )

@router.message(Command("id"))
async def cmd_id(message: Message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    
    text = f"👤 Ваш личный ID: `{user_id}`\n"
    
    if chat_id != user_id:
        text += f"📢 ID этой группы: `{chat_id}`\n"
        text += "(Используйте ID группы для настройки уведомлений в общий чат)"
    
    text += "\nСкопируйте нужный ID и вставьте в файл .env в поле ADMIN_IDS"
    
    await message.answer(text)

