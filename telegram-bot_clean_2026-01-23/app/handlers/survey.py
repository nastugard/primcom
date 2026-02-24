import os
from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from app.states.survey import Survey
from app.keyboards.survey_kb import (
    get_car_categories_keyboard,
    get_steering_wheel_keyboard,
    get_budget_keyboard,
    get_contact_keyboard
)

router = Router()

@router.message(F.text == "СТАРТ")
async def start_survey(message: Message, state: FSMContext):
    await message.answer(
        "👤 Для начала, как мы можем к вам обращаться?\n(Введите ваше имя)",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.set_state(Survey.name)

@router.message(Survey.name)
async def process_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer(
        "🚙 Теперь давайте подберем автомобиль по вашим предпочтениям!\nВыберите категорию автомобиля:",
        reply_markup=get_car_categories_keyboard()
    )
    await state.set_state(Survey.car_category)

@router.message(Survey.car_category)
async def process_category(message: Message, state: FSMContext):
    await state.update_data(car_category=message.text)
    await message.answer(
        "Супер! Выберите расположение руля.",
        reply_markup=get_steering_wheel_keyboard()
    )
    await state.set_state(Survey.steering_wheel)

@router.message(Survey.steering_wheel)
async def process_steering(message: Message, state: FSMContext):
    await state.update_data(steering_wheel=message.text)
    await message.answer(
        "💰 Отлично! Выберите диапазон бюджета для авто.",
        reply_markup=get_budget_keyboard()
    )
    await state.set_state(Survey.budget)

@router.message(Survey.budget)
async def process_budget(message: Message, state: FSMContext):
    await state.update_data(budget=message.text)
    data = await state.get_data()
    name = data.get("name", "Клиент")

    await message.answer(
        f"✅ Спасибо, {name}! Наша команда уже подбирает для вас самые крутые варианты.\n"
        "Чтобы мы могли связаться с вами нужно поделиться контактом ниже.",
        reply_markup=get_contact_keyboard()
    )
    await state.set_state(Survey.contact)

@router.message(Survey.contact, F.contact)
async def process_contact(message: Message, state: FSMContext):
    contact = message.contact
    data = await state.get_data()

    # Формируем заявку для админа
    admin_text = (
        f"🔥 <b>НОВАЯ ЗАЯВКА</b> 🔥\n\n"
        f"👤 <b>Имя:</b> {data.get('name')}\n"
        f"🚙 <b>Авто:</b> {data.get('car_category')}\n"
        f"🎡 <b>Руль:</b> {data.get('steering_wheel')}\n"
        f"💰 <b>Бюджет:</b> {data.get('budget')}\n"
        f"📱 <b>Телефон:</b> {contact.phone_number}\n"
        f"🔗 <b>Профиль:</b> @{message.from_user.username if message.from_user.username else 'Скрыт'}"
    )

    group_id = os.getenv("GROUP_ID")

    if not group_id:
        print("GROUP_ID не задан")
    else:
        try:
            await message.bot.send_message(
                chat_id=int(group_id),
                text=admin_text,
                parse_mode="HTML"
            )
            print(f"Отправлено в группу {group_id}")
        except Exception as e:
            print(f"Ошибка отправки в группу: {e}")

    # Формируем итоговое сообщение пользователю
    await message.answer(
        "📞 Наш специалист свяжется с вами в ближайшее время и ответит на все вопросы.\n\n"
        "📌 Пока вы ожидаете, предлагаем ознакомиться:\n"
        "• [Наш сайт](https://primcom.ru)\n"
        "• [2ГИС](https://go.2gis.com/w5jVZ)\n\n"
        "Спасибо, что выбрали ПРИМКОМ! 🚗",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove()
    )

    await state.clear()
