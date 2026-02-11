from aiogram.fsm.state import State, StatesGroup

class Survey(StatesGroup):
    name = State()
    car_category = State()
    steering_wheel = State()
    budget = State()
    contact = State()
