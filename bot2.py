import asyncio
import logging
import requests
import matplotlib.pyplot as plt
import io
from aiogram import Bot, Dispatcher, Router, types
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import State, StatesGroup

# Токены для Telegram-бота и OpenWeather API

# Инициализация роутера и логирования
router = Router()
logging.basicConfig(level=logging.INFO)

# Создание экземпляров бота и диспетчера
bot = Bot(token=API_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Словарь для хранения данных пользователей
users = {}

# Главное меню бота
main_menu = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Настроить профиль", callback_data="set_profile")],
    [InlineKeyboardButton(text="Записать воду", callback_data="log_water")],
    [InlineKeyboardButton(text="Записать еду", callback_data="log_food")],
    [InlineKeyboardButton(text="Записать тренировку", callback_data="log_workout")],
    [InlineKeyboardButton(text="Посмотреть прогресс", callback_data="check_progress")],
    [InlineKeyboardButton(text="Команды", callback_data="show_commands")],
    [InlineKeyboardButton(text="Получить рекомендации", callback_data="get_recommendations")]
])

# Определение состояний для настройки профиля
class ProfileSetup(StatesGroup):
    """Класс для управления состояниями пользователя при настройке профиля."""
    weight = State()  # Состояние для ввода веса
    height = State()  # Состояние для ввода роста
    age = State()  # Состояние для ввода возраста
    activity = State()  # Состояние для ввода активности
    city = State()  # Состояние для ввода города
    food_quantity = State()  # Состояние для ввода количества съеденной пищи

def calculate_water_goal(weight, activity, temperature):
    """Расчет нормы воды на день.

    Args:
        weight (int): Вес пользователя в кг.
        activity (int): Время активности в минутах.
        temperature (float): Температура окружающей среды.

    Returns:
        int: Рекомендуемое количество воды в мл.
    """
    base = weight * 30
    activity_bonus = (activity // 30) * 500
    weather_bonus = 500 if temperature > 25 else 0
    return base + activity_bonus + weather_bonus

def calculate_calorie_goal(weight, height, age, activity):
    """Расчет нормы калорий на день.

    Args:
        weight (int): Вес пользователя в кг.
        height (int): Рост пользователя в см.
        age (int): Возраст пользователя в годах.
        activity (int): Время активности в минутах.

    Returns:
        int: Рекомендуемое количество калорий.
    """
    base = 10 * weight + 6.25 * height - 5 * age
    activity_bonus = (activity // 30) * 50
    return base + activity_bonus

def get_weather(city):
    """Получение температуры в указанном городе с помощью OpenWeather API.

    Args:
        city (str): Название города.

    Returns:
        float or None: Температура в градусах Цельсия или None, если данные недоступны.
    """
    url = f'http://api.openweathermap.org/data/2.5/weather?q={city}&appid={OPENWEATHER_API_KEY}&units=metric'
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        return data['main']['temp']
    return None

def get_food_info(product_name):
    """Получение информации о продукте из OpenFoodFacts.

    Args:
        product_name (str): Название продукта.

    Returns:
        dict or None: Информация о продукте или None, если данные недоступны.
    """
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

@router.message(Command("start"))
async def start(message: Message):
    """Обработчик команды /start. Отправляет приветственное сообщение и главное меню.

    Args:
        message (Message): Сообщение пользователя.
    """
    await message.reply("Привет! Я помогу тебе рассчитать нормы воды и калорий, а также вести трекинг активности. Начни с команды /set_profile.",
                        reply_markup=main_menu)

@router.callback_query(lambda c: c.data == 'show_commands')
async def show_commands(callback_query: types.CallbackQuery):
    """Обработчик кнопки "Команды" в главном меню. Показывает список доступных команд.

    Args:
        callback_query (types.CallbackQuery): Вызов от пользователя.
    """
    commands = (
        "/set_profile - Настроить профиль\n"
        "/log_water - Записать количество выпитой воды\n"
        "/log_food - Записать количество съеденной пищи\n"
        "/log_workout - Записать тренировку\n"
        "/check_progress - Посмотреть прогресс\n"
        "/get_recommendations - Получить рекомендации\n"
    )
    await callback_query.message.answer(commands)

# Основной обработчик меню, который реагирует на выбор в меню (callback query).
@router.callback_query()
async def handle_menu(callback_query: types.CallbackQuery, state: FSMContext):
    """
    Обрабатывает выбор меню пользователем и направляет в соответствующий раздел.

    Args:
        callback_query (types.CallbackQuery): Объект callback-запроса от Telegram.
        state (FSMContext): Контекст состояния для хранения данных пользователя.
    """
    if callback_query.data == "set_profile":
        # Установка состояния для настройки профиля
        await state.set_state("set_profile")
        await callback_query.message.answer("Введите ваш вес (в кг):")
    elif callback_query.data == "log_water":
        # Инструкция по логированию воды
        await callback_query.message.answer(
            "Введите количество выпитой воды (в мл) с командой /log_water <количество>."
        )
    elif callback_query.data == "log_food":
        # Инструкция по логированию еды
        await callback_query.message.answer(
            "Введите название продукта с командой /log_food <название продукта>."
        )
    elif callback_query.data == "log_workout":
        # Инструкция по логированию тренировки
        await callback_query.message.answer(
            "Введите тип тренировки и время (например: /log_workout бег 30)."
        )
    elif callback_query.data == "check_progress":
        # Отображение прогресса пользователя
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
            # Если профиль не настроен
            await callback_query.message.answer(
                "Сначала настройте профиль с помощью команды /set_profile."
            )
    elif callback_query.data == "get_recommendations":
        # Рекомендации продуктов
        await get_recommendations(callback_query.message)

# Обработчик для настройки профиля через callback-запрос.
@router.callback_query(lambda c: c.data == 'set_profile')
async def set_profile(callback_query: types.CallbackQuery, state: FSMContext):
    """
    Инициирует процесс настройки профиля пользователя.

    Args:
        callback_query (types.CallbackQuery): Объект callback-запроса.
        state (FSMContext): Контекст состояния пользователя.
    """
    await state.set_state(ProfileSetup.weight)
    await callback_query.message.answer("Введите ваш вес (в кг):")

# Обработчик команды для записи потребления воды.
@router.message(Command("log_water"))
async def log_water(message: Message):
    """
    Логирует количество выпитой воды.

    Args:
        message (Message): Объект сообщения от Telegram.
    """
    try:
        command_parts = message.text.split()
        if len(command_parts) != 2:
            await message.reply(
                "Пожалуйста, укажите количество воды в миллилитрах (например: /log_water 100)."
            )
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

# Функция для получения рекомендаций продуктов с низким содержанием калорий.
def get_low_calorie_food():
    """
    Получает список продуктов с низким содержанием калорий с сайта OpenFoodFacts.

    Returns:
        list: Список продуктов в формате [{'name': str, 'calories': float}].
    """
    url = "https://world.openfoodfacts.org/cgi/search.pl?action=process&sort_by=calories&json=true"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        products = data.get('products', [])
        low_calorie_products = set()

        for product in products:
            calories = product.get('nutriments', {}).get('energy-kcal_100g', 0)
            if calories <= 50:
                low_calorie_products.add(
                    (product.get('product_name', 'Неизвестно'), calories)
                )

        return [{'name': name, 'calories': calories} for name, calories in low_calorie_products]
    return None

# Обработчик команды для проверки прогресса.
@router.message(Command("check_progress"))
async def check_progress(message: Message):
    """
    Показывает текущий прогресс пользователя по воде и калориям.

    Args:
        message (Message): Объект сообщения от Telegram.
    """
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
        graph = await plot_progress(user_id)
        if graph:
            await bot.send_photo(message.chat.id, types.InputFile(graph, filename="progress.png"))
        else:
            await message.reply("Не удалось построить график.")
    else:
        await message.reply("Сначала настройте профиль с помощью команды /set_profile.")


@router.callback_query(lambda c: c.data == 'get_recommendations')
async def get_recommendations_callback(callback_query: types.CallbackQuery):
    """
    Обрабатывает нажатие кнопки 'get_recommendations'.
    Предоставляет пользователю рекомендации по продуктам с низким содержанием калорий.

    Args:
        callback_query (types.CallbackQuery): Вызов коллбека от кнопки.

    Returns:
        None
    """
    products = get_low_calorie_food()

    if products:
        response = "Рекомендованные продукты с низким содержанием калорий:\n"
        for product in products[:5]:
            response += f"{product['name']} — {product['calories']} ккал на 100 г\n"
        await callback_query.message.answer(response)
    else:
        await callback_query.message.answer("Не удалось получить рекомендации.")


@router.message(Command("set_profile"))
async def set_profile(message: Message, state: FSMContext):
    """
    Начинает настройку профиля пользователя.
    Первый шаг — ввод веса.

    Args:
        message (Message): Сообщение пользователя.
        state (FSMContext): Контекст FSM для управления состояниями.

    Returns:
        None
    """
    await state.set_state(ProfileSetup.weight)
    await message.reply("Введите ваш вес (в кг):")


async def process_weight(message: Message, state: FSMContext):
    """
    Обрабатывает ввод веса пользователя и переходит к следующему шагу — рост.

    Args:
        message (Message): Сообщение с введённым весом.
        state (FSMContext): Контекст FSM для управления состояниями.

    Returns:
        None
    """
    try:
        await state.update_data(weight=int(message.text))
        await state.set_state(ProfileSetup.height)
        await message.reply("Введите ваш рост (в см):")
    except ValueError:
        await message.reply("Пожалуйста, введите корректное число для веса.")


async def process_height(message: Message, state: FSMContext):
    """
    Обрабатывает ввод роста пользователя и переходит к следующему шагу — возраст.

    Args:
        message (Message): Сообщение с введённым ростом.
        state (FSMContext): Контекст FSM для управления состояниями.

    Returns:
        None
    """
    try:
        await state.update_data(height=int(message.text))
        await state.set_state(ProfileSetup.age)
        await message.reply("Введите Ваш возраст:")
    except ValueError:
        await message.reply("Пожалуйста, введите корректное число для роста.")


async def process_age(message: Message, state: FSMContext):
    """
    Обрабатывает ввод возраста пользователя и переходит к следующему шагу — активность.

    Args:
        message (Message): Сообщение с введённым возрастом.
        state (FSMContext): Контекст FSM для управления состояниями.

    Returns:
        None
    """
    try:
        await state.update_data(age=int(message.text))
        await state.set_state(ProfileSetup.activity)
        await message.reply("Сколько минут активности у вас в день?")
    except ValueError:
        await message.reply("Пожалуйста, введите корректное число для возраста.")


async def process_activity(message: Message, state: FSMContext):
    """
    Обрабатывает ввод активности пользователя и переходит к следующему шагу — город.

    Args:
        message (Message): Сообщение с введённым количеством минут активности.
        state (FSMContext): Контекст FSM для управления состояниями.

    Returns:
        None
    """
    try:
        await state.update_data(activity=int(message.text))
        await state.set_state(ProfileSetup.city)
        await message.reply("В каком городе вы находитесь?")
    except ValueError:
        await message.reply("Пожалуйста, введите корректное число для активности.")


async def process_city(message: Message, state: FSMContext):
    """
    Завершает настройку профиля, рассчитывает цели пользователя на основе введённых данных.

    Args:
        message (Message): Сообщение с введённым городом.
        state (FSMContext): Контекст FSM для управления состояниями.

    Returns:
        None
    """
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

    # Сохранение данных профиля пользователя.
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


async def plot_progress(user_id):
    """
    Строит графики прогресса пользователя по воде и калориям.

    Args:
        user_id (int): ID пользователя.

    Returns:
        io.BytesIO: Буфер с изображением графика в формате PNG, либо None, если пользователь не найден.
    """
    user = users.get(user_id)
    if not user:
        return None

    # Определение данных для графиков
    days = ['День 1', 'День 2', 'День 3', 'День 4', 'День 5']
    water_progress = [user['logged_water'], user['logged_water'] + 200, user['logged_water'] + 400,
                      user['logged_water'] + 600, user['logged_water'] + 800]
    calorie_progress = [user['logged_calories'], user['logged_calories'] + 100, user['logged_calories'] + 200,
                        user['logged_calories'] + 300, user['logged_calories'] + 400]

    # Создание графиков
    fig, ax = plt.subplots(1, 2, figsize=(12, 6))

    # График прогресса по воде
    ax[0].plot(days, water_progress, marker='o', color='blue')
    ax[0].set_title('Прогресс по воде')
    ax[0].set_xlabel('Дни')
    ax[0].set_ylabel('Мл воды')

    # График прогресса по калориям
    ax[1].plot(days, calorie_progress, marker='o', color='green')
    ax[1].set_title('Прогресс по калориям')
    ax[1].set_xlabel('Дни')
    ax[1].set_ylabel('Ккал')

    # Сохранение графика в буфер
    buf = io.BytesIO()
    plt.savefig(buf, format="png")
    buf.seek(0)
    plt.close(fig)
    return buf


def get_low_calorie_food():
    """
    Получает список продуктов с низким содержанием калорий с OpenFoodFacts.

    Returns:
        list[dict] | None: Список продуктов в формате {'name': str, 'calories': float}, либо None, если произошла ошибка.
    """
    url = "https://world.openfoodfacts.org/cgi/search.pl?action=process&sort_by=calories&json=true"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        products = data.get('products', [])
        low_calorie_products = set()

        # Фильтрация продуктов с калорийностью <= 50 ккал на 100 г
        for product in products:
            calories = product.get('nutriments', {}).get('energy-kcal_100g', 0)
            if calories <= 50:
                low_calorie_products.add(
                    (product.get('product_name', 'Неизвестно'), calories)
                )

        # Форматирование результата
        return [{'name': name, 'calories': calories} for name, calories in low_calorie_products]
    return None


@router.message(Command("log_water"))
async def log_water(message: Message):
    """
    Обрабатывает команду /log_water для записи количества воды, выпитой пользователем.

    Ожидает сообщение с количеством воды в миллилитрах. Если количество воды указано некорректно,
    отправляется соответствующее сообщение об ошибке. Также проверяется, настроен ли профиль пользователя.

    Args:
        message (Message): Сообщение от пользователя с командой.
    """
    try:
        # Разделяем текст сообщения на части, ожидаем две части: команда и количество воды
        command_parts = message.text.split()
        if len(command_parts) != 2:
            await message.reply("Пожалуйста, укажите количество воды в миллилитрах (например: /log_water 100).")
            return

        # Преобразуем вторую часть в количество воды (в миллилитрах)
        amount = int(command_parts[1])
        user_id = message.from_user.id

        # Проверка, существует ли профиль пользователя
        if user_id in users:
            users[user_id]['logged_water'] += amount
            water_left = users[user_id]['water_goal'] - users[user_id]['logged_water']
            await message.reply(f"Записано: {amount} мл воды. Осталось: {max(0, water_left)} мл.")
        else:
            await message.reply("Сначала настройте профиль с помощью команды /set_profile.")
    except ValueError:
        # Ошибка при некорректном вводе
        await message.reply("Пожалуйста, укажите корректное количество воды в миллилитрах.")


@router.message(Command("log_food"))
async def log_food(message: Message, state: FSMContext):
    """
    Обрабатывает команду /log_food для записи съеденного продукта.

    Ожидает название продукта, после чего запрашивает количество съеденных граммов. Полученные данные
    сохраняются в состояние и добавляется информация о калориях на 100 грамм.

    Args:
        message (Message): Сообщение от пользователя с командой.
        state (FSMContext): Контекст состояний для хранения промежуточных данных.
    """
    command_parts = message.text.split(maxsplit=1)
    if len(command_parts) < 2:
        await message.reply("Пожалуйста, укажите название продукта.")
        return

    product_name = command_parts[1]
    food_info = get_food_info(product_name)
    if food_info:
        # Сохраняем информацию о продукте в состоянии
        calories_per_100g = food_info['calories']
        await state.update_data(product_name=food_info['name'], calories_per_100g=calories_per_100g)
        await message.reply(f"{food_info['name']} — {calories_per_100g} ккал на 100 г. Сколько грамм вы съели?")
        await state.set_state(ProfileSetup.food_quantity)
    else:
        await message.reply("Не удалось найти информацию о продукте. Попробуйте другое название.")


@router.message(Command("log_workout"))
async def log_workout(message: Message):
    """
    Обрабатывает команду /log_workout для записи тренировки.

    Ожидает тип тренировки (бег, плавание, велоспорт) и время тренировки в минутах. Рассчитывает
    количество сожженных калорий и необходимое количество воды в зависимости от типа тренировки.

    Args:
        message (Message): Сообщение от пользователя с командой.
    """
    try:
        command_parts = message.text.split()
        if len(command_parts) != 3:
            await message.reply("Пожалуйста, укажите тип тренировки и время (например: /log_workout бег 30).")
            return

        workout_type = command_parts[1].lower()
        workout_time = int(command_parts[2])

        # Проверка на корректность времени тренировки
        if workout_time <= 0:
            await message.reply("Время тренировки должно быть больше нуля.")
            return

        workout_calories = 0
        water_needed = 0
        # Определение калорий и потребности в воде в зависимости от типа тренировки
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
    """
    Обрабатывает команду /check_progress для получения прогресса пользователя по воде и калориям.

    Отправляет информацию о текущем потреблении воды и калорий, а также сожженных калориях.
    Строит график прогресса, если это возможно.

    Args:
        message (Message): Сообщение от пользователя с командой.
    """
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
        graph = await plot_progress(user_id)
        if graph:
            await bot.send_photo(message.chat.id, types.InputFile(graph, filename="progress.png"))
        else:
            await message.reply("Не удалось построить график.")
    else:
        await message.reply("Сначала настройте профиль с помощью команды /set_profile.")


@router.message(Command("get_recommendations"))
async def get_recommendations(message: Message):
    """
    Обрабатывает команду /get_recommendations для получения рекомендаций по продуктам с низким содержанием калорий.

    Отправляет список продуктов с наименьшим содержанием калорий на 100 г.

    Args:
        message (Message): Сообщение от пользователя с командой.
    """
    products = get_low_calorie_food()
    if products:
        response = "Рекомендованные продукты с низким содержанием калорий:\n"
        for product in products[:5]:
            response += f"{product['name']} — {product['calories']} ккал на 100 г\n"
        await message.reply(response)
    else:
        await message.reply("Не удалось получить рекомендации.")


async def process_food_quantity(message: Message, state: FSMContext):
    """
    Обрабатывает количество съеденных граммов для выбранного продукта.

    Рассчитывает потребленные калории на основе введенного количества и добавляет их в данные пользователя.

    Args:
        message (Message): Сообщение с количеством съеденных граммов.
        state (FSMContext): Контекст состояния, содержащий информацию о продукте.
    """
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


def setup_handlers(dp):
    """
    Регистрация всех обработчиков команд в диспетчере.

    Args:
        dp: Диспетчер для регистрации команд.
    """
    dp.include_router(router)
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


if __name__ == "__main__":
    # Настройка обработчиков и запуск бота
    setup_handlers(dp)
    asyncio.run(dp.start_polling(bot))
