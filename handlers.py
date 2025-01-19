import requests
from aiogram import types
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from states import ProfileSetup
from config import OPENWEATHER_API_KEY

users = {}

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
    return None

async def start(message: types.Message):
    await message.reply("Привет! Я помогу тебе рассчитать нормы воды и калорий, а также вести трекинг активности. Начни с команды /set_profile.")

async def set_profile(message: types.Message, state: FSMContext):
    await state.set_state(ProfileSetup.weight)
    await message.reply("Введите ваш вес (в кг):")

async def process_weight(message: types.Message, state: FSMContext):
    try:
        await state.update_data(weight=int(message.text))
        await state.set_state(ProfileSetup.height)
        await message.reply("Введите ваш рост (в см):")
    except ValueError:
        await message.reply("Пожалуйста, введите корректное число для веса.")

async def process_height(message: types.Message, state: FSMContext):
    try:
        await state.update_data(height=int(message.text))
        await state.set_state(ProfileSetup.age)
        await message.reply("Введите Ваш возраст:")
    except ValueError:
        await message.reply("Пожалуйста, введите корректное число для роста.")

async def process_age(message: types.Message, state: FSMContext):
    try:
        await state.update_data(age=int(message.text))
        await state.set_state(ProfileSetup.activity)
        await message.reply("Сколько минут активности у вас в день?")
    except ValueError:
        await message.reply("Пожалуйста, введите корректное число для возраста.")

async def process_activity(message: types.Message, state: FSMContext):
    try:
        await state.update_data(activity=int(message.text))
        await state.set_state(ProfileSetup.city)
        await message.reply("В каком городе вы находитесь?")
    except ValueError:
        await message.reply("Пожалуйста, введите корректное число для активности.")

async def process_city(message: types.Message, state: FSMContext):
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

async def log_water(message: Message):
    try:
        command_parts = message.text.split()
        if len(command_parts) != 2:
            await message.reply("Пожалуйста, укажите количество воды в миллилитрах (например: /log_water 200).")
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


async def log_food(message: Message, state: FSMContext):
    command_parts = message.text.split(maxsplit=1)
    if len(command_parts) < 2:
        await message.reply("Пожалуйста, укажите название продукта.")
        return

    product_name = command_parts[1]
    food_info = get_food_info(product_name)
    if food_info:
        calories_per_100g = food_info['calories']
        # Сохраняем информацию о продукте и его калориях
        await state.update_data(product_name=food_info['name'], calories_per_100g=calories_per_100g)

        # Запросим у пользователя, сколько грамм он съел
        await message.reply(f"{food_info['name']} — {calories_per_100g} ккал на 100 г. Сколько грамм вы съели?")
        # Переходим в состояние для ввода количества грамм
        await state.set_state(ProfileSetup.food_quantity)

    else:
        await message.reply("Не удалось найти информацию о продукте. Попробуйте другое название.")


async def log_workout(message: Message):
    try:
        # Разбиваем команду на части: тип тренировки и время
        command_parts = message.text.split()
        if len(command_parts) != 3:
            await message.reply("Пожалуйста, укажите тип тренировки и время (например: /log_workout бег 30).")
            return

        workout_type = command_parts[1].lower()  # Приводим тип тренировки к нижнему регистру
        workout_time = int(command_parts[2])  # Время тренировки в минутах

        if workout_time <= 0:
            await message.reply("Время тренировки должно быть больше нуля.")
            return

        # Определим коэффициенты для различных типов тренировок
        workout_calories = 0
        water_needed = 0
        if workout_type == "бег":
            workout_calories = workout_time * 10  # 10 калорий на минуту для бега
            water_needed = (workout_time // 30) * 200  # 200 мл воды за каждые 30 минут
        elif workout_type == "плавание":
            workout_calories = workout_time * 8  # 8 калорий на минуту для плавания
            water_needed = (workout_time // 30) * 200
        elif workout_type == "велоспорт":
            workout_calories = workout_time * 7  # 7 калорий на минуту для велоспорта
            water_needed = (workout_time // 30) * 200
        else:
            await message.reply("Неизвестный тип тренировки. Попробуйте 'бег', 'плавание' или 'велоспорт'.")
            return

        # Сохраняем информацию о тренировке в данных пользователя
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
        grams = int(message.text)  # Получаем количество съеденных грамм
        data = await state.get_data()
        calories_per_100g = data['calories_per_100g']

        # Рассчитываем потребленные калории
        consumed_calories = (calories_per_100g * grams) / 100

        user_id = message.from_user.id
        if user_id in users:
            users[user_id]['logged_calories'] += consumed_calories
            await message.reply(
                f"Записано: {consumed_calories:.2f} ккал. Общая сумма потребленных калорий: {users[user_id]['logged_calories']:.2f} ккал.")
        else:
            await message.reply("Сначала настройте профиль с помощью команды /set_profile.")

        # После ввода количества грамм очищаем состояние
        await state.clear()

    except ValueError:
        await message.reply("Пожалуйста, введите корректное количество грамм.")