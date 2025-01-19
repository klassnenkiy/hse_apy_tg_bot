from aiogram.fsm.state import State, StatesGroup

class ProfileSetup(StatesGroup):
    weight = State()
    height = State()
    age = State()
    activity = State()
    city = State()
    food_quantity = State()
