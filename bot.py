import random
import logging
import requests
import matplotlib
import matplotlib.pyplot as plt
import io
import os
from aiogram import Bot, Dispatcher, Router, types
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from googletrans import Translator
from aiohttp import web
from config import API_TOKEN, OPENWEATHER_API_KEY, NUTRITIONIX_API_KEY, NUTRITIONIX_APP_ID, WEBHOOK_URL
from states import ProfileSetup

router = Router()
translator = Translator()

logging.basicConfig(level=logging.INFO)
matplotlib.use('Agg')
bot = Bot(token=API_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
WEBHOOK_URL = f"https://hse-apy-tg-bot.onrender.com/webhook"

users = {}


async def on_startup(app):
    await bot.set_webhook(WEBHOOK_URL)
    logging.info(f"Webhook установлен на {WEBHOOK_URL}")


async def on_shutdown(app):
    logging.info("Удаление Webhook...")
    await bot.delete_webhook()
    await bot.session.close()


async def handle_webhook(request):
    body = await request.json()
    update = types.Update(**body)
    await dp.feed_update(bot, update)
    return web.Response()


app = web.Application()
app.router.add_post("/webhook", handle_webhook)
app.on_startup.append(on_startup)
app.on_shutdown.append(on_shutdown)


main_menu = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Настроить профиль", callback_data="set_profile")],
    [InlineKeyboardButton(text="Записать воду", callback_data="log_water")],
    [InlineKeyboardButton(text="Записать еду", callback_data="log_food")],
    [InlineKeyboardButton(text="Записать тренировку", callback_data="log_workout")],
    [InlineKeyboardButton(text="Посмотреть прогресс", callback_data="check_progress")],
    [InlineKeyboardButton(text="Команды", callback_data="show_commands")],
    [InlineKeyboardButton(text="Получить рекомендации", callback_data="get_recommendations")]
])


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
    url = f'https://api.openweathermap.org/data/2.5/weather?q={city}&appid={OPENWEATHER_API_KEY}&units=metric'
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


def translate_to_english(text):
    translation = translator.translate(text, src='ru', dest='en')
    return translation.text


async def get_nutrition_info_from_nutritionix(product_name):
    translated_name = translate_to_english(product_name)

    url = "https://trackapi.nutritionix.com/v2/natural/nutrients"
    headers = {
        'x-app-id': NUTRITIONIX_APP_ID,
        'x-app-key': NUTRITIONIX_API_KEY,
        'Content-Type': 'application/json'
    }
    body = {
        "query": translated_name
    }

    response = requests.post(url, headers=headers, json=body)

    if response.status_code == 200:
        data = response.json()
        if 'foods' in data:
            food = data['foods'][0]
            product_name = food['food_name']
            calories_per_100g = food['nf_calories']
            return {
                'name': product_name,
                'calories': calories_per_100g
            }
    return None


@router.message(Command("start"))
async def start(message: Message):
    await message.reply("Привет! Я помогу тебе рассчитать нормы воды и калорий, а также вести трекинг активности. "
                        "Начни с команды /set_profile. Или ознакомься с полным списком команд /show_commands",
                        reply_markup=main_menu)


@router.callback_query()
async def handle_menu(callback_query: types.CallbackQuery, state: FSMContext):
    user_id = callback_query.from_user.id
    if callback_query.data == "set_profile":
        await state.set_state("set_profile")
        await callback_query.message.answer("Введите ваш вес (в кг):")

    elif callback_query.data == "log_water":
        await callback_query.message.answer(
            "Введите количество выпитой воды (в мл) с командой /log_water <количество>. (например: /log_water 100)")

    elif callback_query.data == "log_food":
        await callback_query.message.answer(
            "Введите название продукта с командой /log_food <название продукта>. (например: /log_food банан)")

    elif callback_query.data == "log_workout":
        await callback_query.message.answer("Введите тип тренировки и время (например: /log_workout бег 30).")

    elif callback_query.data == "check_progress":
        if user_id in users:
            user = users[user_id]
            water_progress = f"Выпито: {user['logged_water']} мл из {user['water_goal']} мл."
            calorie_progress = (f"Потреблено: {user['logged_calories']} ккал из {user['calorie_goal']} ккал.\n"
                                f"Сожжено: {user['burned_calories']} ккал.")
            progress_chart = create_progress_chart(user)
            progress_chart_bytes = progress_chart.getvalue()
            photo = BufferedInputFile(progress_chart_bytes, filename="progress_chart.png")
            await callback_query.message.answer(f"📊 Прогресс:\n\n{water_progress}\n\n{calorie_progress}")
            await callback_query.message.answer_photo(photo=photo)
        else:
            await callback_query.message.answer("Сначала настройте профиль с помощью команды /set_profile.")
    elif callback_query.data == "get_recommendations":
        await get_recommendations(callback_query.message)
    elif callback_query.data == "show_commands":
        commands = (
            "/start - Приветствие и кнопки\n"
            "/show_commands - Список команд\n"
            "/set_profile - Настроить профиль\n"
            "/log_water - Записать количество выпитой воды\n"
            "/log_food - Записать количество съеденной пищи\n"
            "/log_workout - Записать тренировку\n"
            "/check_progress - Посмотреть прогресс\n"
            "/get_recommendations - Получить рекомендации\n"
            "/preset_profile - Заполненный профиль\n"
        )
        await callback_query.message.answer(commands)


@router.message(Command("show_commands"))
async def show_commands(message: Message):
    commands = (
        "/start - Приветствие и кнопки\n"
        "/show_commands - Список команд\n"
        "/set_profile - Настроить профиль\n"
        "/log_water - Записать количество выпитой воды\n"
        "/log_food - Записать количество съеденной пищи\n"
        "/log_workout - Записать тренировку\n"
        "/check_progress - Посмотреть прогресс\n"
        "/get_recommendations - Получить рекомендации\n"
        "/preset_profile - Заполненный профиль\n"
    )
    await message.reply(commands)


@router.message(Command("set_profile"))
async def set_profile(message: Message, state: FSMContext):
    await state.set_state(ProfileSetup.weight)
    await message.answer("Введите Ваш вес (в кг):")


@router.message(ProfileSetup.weight)
async def process_weight(message: Message, state: FSMContext):
    try:
        await state.update_data(weight=int(message.text))
        await state.set_state(ProfileSetup.height)
        await message.reply("Введите Ваш рост (в см):")
    except ValueError:
        await message.reply("Пожалуйста, введите корректное число для веса.")


@router.message(ProfileSetup.height)
async def process_height(message: Message, state: FSMContext):
    try:
        await state.update_data(height=int(message.text))
        await state.set_state(ProfileSetup.age)
        await message.reply("Введите Ваш возраст:")
    except ValueError:
        await message.reply("Пожалуйста, введите корректное число для роста.")


@router.message(ProfileSetup.age)
async def process_age(message: Message, state: FSMContext):
    try:
        await state.update_data(age=int(message.text))
        await state.set_state(ProfileSetup.activity)
        await message.reply("Сколько минут активности у вас в день?")
    except ValueError:
        await message.reply("Пожалуйста, введите корректное число для возраста.")


@router.message(ProfileSetup.activity)
async def process_activity(message: Message, state: FSMContext):
    try:
        await state.update_data(activity=int(message.text))
        await state.set_state(ProfileSetup.city)
        await message.reply("В каком городе вы находитесь?")
    except ValueError:
        await message.reply("Пожалуйста, введите корректное число для активности.")


@router.message(ProfileSetup.city)
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

    await message.reply(f"Профиль сохранён!\n\nНорма воды: {water_goal} мл\nНорма калорий: {calorie_goal} ккал",
                        parse_mode=ParseMode.HTML)
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
        await message.reply("Пожалуйста, укажите название продукта. (например: /log_food банан)")
        return
    product_name = command_parts[1]
    food_info = await get_nutrition_info_from_nutritionix(product_name)

    if food_info:
        calories_per_100g = food_info['calories']
        await state.update_data(product_name=food_info['name'], calories_per_100g=calories_per_100g)
        await message.reply(f"🍌 {food_info['name']} — {calories_per_100g} ккал на 100 г. Сколько грамм вы съели?")
        await state.set_state(ProfileSetup.food_quantity)
    else:
        await message.reply("Не удалось найти информацию о продукте. Попробуйте другое название.")


@router.message(ProfileSetup.food_quantity)
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
                f"Записано: {consumed_calories:.2f} ккал. "
                f"Общая сумма потребленных калорий: {users[user_id]['logged_calories']:.2f} ккал."
            )
        else:
            await message.reply("Сначала настройте профиль с помощью команды /set_profile.")

        await state.clear()

    except ValueError:
        await message.reply("Пожалуйста, введите корректное количество грамм.")


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
        progress_chart = create_progress_chart(user)
        await message.reply(f"📊 Прогресс:\n\n"
                            f"Вода:\n"
                            f"{water_progress}\n"
                            f"Осталось: {max(0, remaining_water)} мл.\n\n"
                            f"Калории:\n"
                            f"{calorie_progress}\n"
                            f"Баланс: {balance_calories} ккал.")
        photo = BufferedInputFile(progress_chart.getvalue(), filename="progress_chart.png")
        await message.answer_photo(photo=photo)

    else:
        await message.reply("Сначала настройте профиль с помощью команды /set_profile.")


def create_progress_chart(user):
    water_progress = user['logged_water']
    water_goal = user['water_goal']
    calories_progress = user['logged_calories']
    calorie_goal = user['calorie_goal']
    fig, ax = plt.subplots(1, 2, figsize=(12, 6))
    ax[0].bar(['Выпито', 'Осталось'],
              [water_progress, water_goal - water_progress],
              color=['#1f77b4', '#ff7f0e'], edgecolor='black')
    ax[0].set_title(f'Прогресс по воде ({water_progress} мл из {water_goal} мл)', fontsize=14, fontweight='bold',
                    color='#1f77b4')
    ax[0].set_ylim(0, water_goal * 1.2)
    ax[0].set_facecolor('#f7f7f7')
    ax[1].bar(['Потреблено', 'Осталось'],
              [calories_progress, calorie_goal - calories_progress],
              color=['#ff6347', '#98c379'], edgecolor='black')
    ax[1].set_title(f'Прогресс по калориям ({calories_progress} ккал из {calorie_goal} ккал)', fontsize=14,
                    fontweight='bold', color='#ff6347')
    ax[1].set_ylim(0, calorie_goal * 1.2)
    ax[1].set_facecolor('#f7f7f7')
    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png")
    buf.seek(0)
    return buf


async def get_low_calorie_food():
    url = "https://trackapi.nutritionix.com/v2/search/instant/"
    headers = {
        "x-app-id": NUTRITIONIX_APP_ID,
        "x-app-key": NUTRITIONIX_API_KEY,
        "Content-Type": "application/json"
    }
    params = {
        "query": "low calorie"
    }
    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 200:
        data = response.json()
        food_items = data.get("common", [])
        if not food_items:
            return []
        low_calorie_foods = []
        for food in food_items:
            calories = food.get("nf_calories", 0)
            if calories <= 50:
                low_calorie_foods.append({
                    'name': food.get("food_name", 'Неизвестно'),
                    'calories': calories
                })
        if low_calorie_foods:
            recommendations = random.sample(low_calorie_foods, k=min(5, len(low_calorie_foods)))
            return recommendations
        else:
            return []

    else:
        return None


@router.message(Command("get_recommendations"))
async def get_recommendations(message: Message):
    products = await get_low_calorie_food()

    if products:
        response = "Рекомендованные продукты с низким содержанием калорий:\n"
        for product in products[:5]:
            response += f"{product['name']} — {product['calories']} ккал\n"
        await message.reply(response)
    else:
        await message.reply("Не удалось получить рекомендации.")


@router.message(Command("preset_profile"))
async def preset_profile(message: Message):
    user_id = message.from_user.id

    preset_data = {
        "weight": 70,
        "height": 175,
        "age": 25,
        "activity": 60,
        "city": "Moscow"
    }

    temperature = get_weather(preset_data['city'])
    if temperature is None:
        await message.reply("Не удалось получить данные о погоде. Попробуйте снова позже.")
        return

    water_goal = calculate_water_goal(preset_data['weight'], preset_data['activity'], temperature)
    calorie_goal = calculate_calorie_goal(preset_data['weight'], preset_data['height'], preset_data['age'],
                                          preset_data['activity'])

    users[user_id] = {
        "weight": preset_data['weight'],
        "height": preset_data['height'],
        "age": preset_data['age'],
        "activity": preset_data['activity'],
        "city": preset_data['city'],
        "water_goal": water_goal,
        "calorie_goal": calorie_goal,
        "logged_water": 0,
        "logged_calories": 0,
        "burned_calories": 0
    }

    await message.reply(f"Профиль успешно установлен!\n\n"
                        f"Вес: {preset_data['weight']} кг\n"
                        f"Рост: {preset_data['height']} см\n"
                        f"Возраст: {preset_data['age']} лет\n"
                        f"Активность: {preset_data['activity']} минут в день\n"
                        f"Город: {preset_data['city']}\n\n"
                        f"Норма воды: {water_goal} мл\n"
                        f"Норма калорий: {calorie_goal} ккал.")


def setup_handlers(dp):
    dp.include_router(router)
    dp.message.register(set_profile, Command("set_profile"))
    dp.callback_query.register(set_profile, lambda c: c.data == 'set_profile')


if __name__ == "__main__":
    import logging
    from aiohttp import web
    logging.basicConfig(level=logging.INFO)
    port = int(os.environ.get("PORT", 8080))
    setup_handlers(dp)
    web.run_app(app, host="0.0.0.0", port=port)
