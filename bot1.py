import asyncio
import logging
import requests
from aiogram import Bot, Dispatcher, Router, types
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import State, StatesGroup

API_TOKEN = '7576506747:AAEDxUV5Vj6XmLgn9WAYyTPmKwh7Aa4_xNw'
OPENWEATHER_API_KEY = 'afb6147ee48eace31b567b026d07535e'

router = Router()

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

users = {}

main_menu = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Настроить профиль", callback_data="set_profile")],
    [InlineKeyboardButton(text="Записать воду", callback_data="log_water")],
    [InlineKeyboardButton(text="Записать еду", callback_data="log_food")],
    [InlineKeyboardButton(text="Записать тренировку", callback_data="log_workout")],
    [InlineKeyboardButton(text="Посмотреть прогресс", callback_data="check_progress")],
    [InlineKeyboardButton(text="Команды", callback_data="show_commands")]
])


class ProfileSetup(StatesGroup):
    weight = State()
    height = State()
    age = State()
    activity = State()
    city = State()
    food_quantity = State()

def calculate_water_goal(weight, activity, temperature):
    base = weight * 30
    activity_bonus = (activity // 30) * 500
    weather_bonus = 500 if temperature > 25 else 0
    return base + activity_bonus + weather_bonus

def calculate_calorie_goal(weight, height, age, activity):
    base = 10 * weight + 6.25 * height - 5 * age
    activity_bonus = (activity // 30) * 50
    return base + activity_bonus

def get_weather(city):
    url = f'http://api.openweathermap.org/data/2.5/weather?q={city}&appid={OPENWEATHER_API_KEY}&units=metric'
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        return data['main']['temp']
    return None

def get_food_info(product_name):
    url = f"https://world.openfoodfacts.org/cgi/search.pl?action=process&search_terms={product_name}&json=true"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        products = data.get('products', [])
        if products:
            first_product = products[0]
            return {
                'name': first_product.get('product_name', 'Неизвестно'),
                'calories': first_product.get('nutriments', {}).get('energy-kcal_100g', 0)
            }
    return


@router.message(Command("start"))
async def start(message: Message):
    await message.reply("Привет! Я помогу тебе рассчитать нормы воды и калорий, а также вести трекинг активности. Начни с команды /set_profile.",
                        reply_markup=main_menu)


@router.callback_query(lambda c: c.data == 'show_commands')
async def show_commands(callback_query: types.CallbackQuery):
    commands = (
        "/set_profile - Настроить профиль\n"
        "/log_water - Записать количество выпитой воды\n"
        "/log_food - Записать количество съеденной пищи\n"
        "/log_workout - Записать тренировку\n"
        "/check_progress - Посмотреть прогресс"
    )
    await callback_query.message.answer(commands)


@router.callback_query()
async def handle_menu(callback_query: types.CallbackQuery, state: FSMContext):
    if callback_query.data == "set_profile":
        await state.set_state("set_profile")
        await callback_query.message.answer("Введите ваш вес (в кг):")
    elif callback_query.data == "log_water":
        await callback_query.message.answer("Введите количество выпитой воды (в мл) с командой /log_water <количество>.")
    elif callback_query.data == "log_food":
        await callback_query.message.answer("Введите название продукта с командой /log_food <название продукта>.")
    elif callback_query.data == "log_workout":
        await callback_query.message.answer("Введите тип тренировки и время (например: /log_workout бег 30).")
    elif callback_query.data == "check_progress":
        user_id = callback_query.from_user.id
        if user_id in users:
            user = users[user_id]
            water_progress = f"Выпито: {user['logged_water']} мл из {user['water_goal']} мл."
            calorie_progress = (f"Потреблено: {user['logged_calories']} ккал из {user['calorie_goal']} ккал.\n"
                                f"Сожжено: {user['burned_calories']} ккал.")
            await callback_query.message.answer(f"📊 Прогресс:\n\n"
                                                f"Вода:\n{water_progress}\n\n"
                                                f"Калории:\n{calorie_progress}")
        else:
            await callback_query.message.answer("Сначала настройте профиль с помощью команды /set_profile.")


@router.callback_query(lambda c: c.data == 'set_profile')
async def set_profile(callback_query: types.CallbackQuery, state: FSMContext):
    await state.set_state(ProfileSetup.weight)
    await callback_query.message.answer("Введите ваш вес (в кг):")

@router.callback_query(lambda c: c.data == 'log_water')
async def log_water(callback_query: types.CallbackQuery):
    await callback_query.message.answer("Введите количество выпитой воды (в мл) с командой /log_water <количество>.")


@router.callback_query(lambda c: c.data == 'log_food')
async def log_food(callback_query: types.CallbackQuery):
    await callback_query.message.answer("Введите название продукта с командой /log_food <название продукта>.")

@router.callback_query(lambda c: c.data == 'log_workout')
async def log_workout(callback_query: types.CallbackQuery):
    await callback_query.message.answer("Введите тип тренировки и время (например: /log_workout бег 30).")

@router.callback_query(lambda c: c.data == 'check_progress')
async def check_progress(callback_query: types.CallbackQuery, state: FSMContext):
    user_id = callback_query.from_user.id
    if user_id in users:
        user = users[user_id]
        water_progress = f"Выпито: {user['logged_water']} мл из {user['water_goal']} мл."
        calorie_progress = (f"Потреблено: {user['logged_calories']} ккал из {user['calorie_goal']} ккал.\n"
                            f"Сожжено: {user['burned_calories']} ккал.")
        await callback_query.message.answer(f"📊 Прогресс:\n\n"
                                            f"Вода:\n{water_progress}\n\n"
                                            f"Калории:\n{calorie_progress}")
    else:
        await callback_query.message.answer("Сначала настройте профиль с помощью команды /set_profile.")



@router.message(Command("set_profile"))
async def set_profile(message: Message, state: FSMContext):
    await state.set_state(ProfileSetup.weight)
    await message.reply("Введите ваш вес (в кг):")

async def process_weight(message: Message, state: FSMContext):
    try:
        await state.update_data(weight=int(message.text))
        await state.set_state(ProfileSetup.height)
        await message.reply("Введите ваш рост (в см):")
    except ValueError:
        await message.reply("Пожалуйста, введите корректное число для веса.")

async def process_height(message: Message, state: FSMContext):
    try:
        await state.update_data(height=int(message.text))
        await state.set_state(ProfileSetup.age)
        await message.reply("Введите Ваш возраст:")
    except ValueError:
        await message.reply("Пожалуйста, введите корректное число для роста.")

async def process_age(message: Message, state: FSMContext):
    try:
        await state.update_data(age=int(message.text))
        await state.set_state(ProfileSetup.activity)
        await message.reply("Сколько минут активности у вас в день?")
    except ValueError:
        await message.reply("Пожалуйста, введите корректное число для возраста.")

async def process_activity(message: Message, state: FSMContext):
    try:
        await state.update_data(activity=int(message.text))
        await state.set_state(ProfileSetup.city)
        await message.reply("В каком городе вы находитесь?")
    except ValueError:
        await message.reply("Пожалуйста, введите корректное число для активности.")

async def process_city(message: Message, state: FSMContext):
    data = await state.get_data()
    data['city'] = message.text
    user_id = message.from_user.id

    temperature = get_weather(data['city'])
    if temperature is None:
        await message.reply("Не удалось получить данные о погоде. Попробуйте снова позже.")
        await state.clear()
        return

    water_goal = calculate_water_goal(data['weight'], data['activity'], temperature)
    calorie_goal = calculate_calorie_goal(data['weight'], data['height'], data['age'], data['activity'])

    users[user_id] = {
        "weight": data['weight'],
        "height": data['height'],
        "age": data['age'],
        "activity": data['activity'],
        "city": data['city'],
        "water_goal": water_goal,
        "calorie_goal": calorie_goal,
        "logged_water": 0,
        "logged_calories": 0,
        "burned_calories": 0
    }

    await message.reply(f"Профиль сохранён!\n\nНорма воды: {water_goal} мл\nНорма калорий: {calorie_goal} ккал", parse_mode=ParseMode.HTML)
    await state.clear()


@router.message(Command("log_water"))
async def log_water(message: Message):
    try:
        command_parts = message.text.split()
        if len(command_parts) != 2:
            await message.reply("Пожалуйста, укажите количество воды в миллилитрах (например: /log_water 100).")
            return

        amount = int(command_parts[1])
        user_id = message.from_user.id
        if user_id in users:
            users[user_id]['logged_water'] += amount
            water_left = users[user_id]['water_goal'] - users[user_id]['logged_water']
            await message.reply(f"Записано: {amount} мл воды. Осталось: {max(0, water_left)} мл.")
        else:
            await message.reply("Сначала настройте профиль с помощью команды /set_profile.")
    except ValueError:
        await message.reply("Пожалуйста, укажите корректное количество воды в миллилитрах.")


@router.message(Command("log_food"))
async def log_food(message: Message, state: FSMContext):
    command_parts = message.text.split(maxsplit=1)
    if len(command_parts) < 2:
        await message.reply("Пожалуйста, укажите название продукта.")
        return

    product_name = command_parts[1]
    food_info = get_food_info(product_name)
    if food_info:
        calories_per_100g = food_info['calories']
        await state.update_data(product_name=food_info['name'], calories_per_100g=calories_per_100g)
        await message.reply(f"{food_info['name']} — {calories_per_100g} ккал на 100 г. Сколько грамм вы съели?")
        await state.set_state(ProfileSetup.food_quantity)

    else:
        await message.reply("Не удалось найти информацию о продукте. Попробуйте другое название.")



@router.message(Command("log_workout"))
async def log_workout(message: Message):
    try:
        command_parts = message.text.split()
        if len(command_parts) != 3:
            await message.reply("Пожалуйста, укажите тип тренировки и время (например: /log_workout бег 30).")
            return

        workout_type = command_parts[1].lower()
        workout_time = int(command_parts[2])

        if workout_time <= 0:
            await message.reply("Время тренировки должно быть больше нуля.")
            return

        workout_calories = 0
        water_needed = 0
        if workout_type == "бег":
            workout_calories = workout_time * 10
            water_needed = (workout_time // 30) * 200
        elif workout_type == "плавание":
            workout_calories = workout_time * 8
            water_needed = (workout_time // 30) * 200
        elif workout_type == "велоспорт":
            workout_calories = workout_time * 7
            water_needed = (workout_time // 30) * 200
        else:
            await message.reply("Неизвестный тип тренировки. Попробуйте 'бег', 'плавание' или 'велоспорт'.")
            return

        user_id = message.from_user.id
        if user_id in users:
            users[user_id]['burned_calories'] += workout_calories
            users[user_id]['logged_water'] += water_needed
            remaining_water = users[user_id]['water_goal'] - users[user_id]['logged_water']
            await message.reply(f"🏃‍♂️ Тренировка ({workout_type}) на {workout_time} минут — {workout_calories} ккал.\n"
                                f"Дополнительно: выпейте {water_needed} мл воды.\n"
                                f"Осталось: {max(0, remaining_water)} мл воды.")
        else:
            await message.reply("Сначала настройте профиль с помощью команды /set_profile.")

    except ValueError:
        await message.reply("Пожалуйста, введите корректное количество минут для тренировки.")


@router.message(Command("check_progress"))
async def check_progress(message: Message):
    user_id = message.from_user.id
    if user_id in users:
        user = users[user_id]

        water_progress = f"Выпито: {user['logged_water']} мл из {user['water_goal']} мл."
        remaining_water = user['water_goal'] - user['logged_water']

        calorie_progress = (f"Потреблено: {user['logged_calories']} ккал из {user['calorie_goal']} ккал.\n"
                            f"Сожжено: {user['burned_calories']} ккал.")
        balance_calories = user['logged_calories'] - user['burned_calories']

        await message.reply(f"📊 Прогресс:\n\n"
                            f"Вода:\n"
                            f"{water_progress}\n"
                            f"Осталось: {max(0, remaining_water)} мл.\n\n"
                            f"Калории:\n"
                            f"{calorie_progress}\n"
                            f"Баланс: {balance_calories} ккал.")
    else:
        await message.reply("Сначала настройте профиль с помощью команды /set_profile.")


async def process_food_quantity(message: Message, state: FSMContext):
    try:
        grams = int(message.text)
        data = await state.get_data()
        calories_per_100g = data['calories_per_100g']
        consumed_calories = (calories_per_100g * grams) / 100

        user_id = message.from_user.id
        if user_id in users:
            users[user_id]['logged_calories'] += consumed_calories
            await message.reply(
                f"Записано: {consumed_calories:.2f} ккал. Общая сумма потребленных калорий: {users[user_id]['logged_calories']:.2f} ккал.")
        else:
            await message.reply("Сначала настройте профиль с помощью команды /set_profile.")

        await state.clear()

    except ValueError:
        await message.reply("Пожалуйста, введите корректное количество грамм.")



dp.message.register(start, Command("start"))
dp.message.register(set_profile, Command("set_profile"))
dp.message.register(log_water, Command("log_water"))
dp.message.register(log_food, Command("log_food"))
dp.message.register(log_workout, Command("log_workout"))
dp.message.register(check_progress, Command("check_progress"))
dp.message.register(process_weight, ProfileSetup.weight)
dp.message.register(process_height, ProfileSetup.height)
dp.message.register(process_age, ProfileSetup.age)
dp.message.register(process_activity, ProfileSetup.activity)
dp.message.register(process_city, ProfileSetup.city)
dp.message.register(process_food_quantity, ProfileSetup.food_quantity)


def setup_handlers(dp):
    dp.include_router(router)

if __name__ == "__main__":

    async def main():
        setup_handlers(dp)
        await dp.start_polling(bot)

    asyncio.run(main())
