import os
from dotenv import load_dotenv

load_dotenv()

API_TOKEN = os.getenv("API_TOKEN")
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
NUTRITIONIX_API_KEY = os.getenv("NUTRITIONIX_API_KEY")
NUTRITIONIX_APP_ID = os.getenv("NUTRITIONIX_APP_ID")

if not API_TOKEN:
    raise ValueError("Переменная окружения API_TOKEN не установлена!")

if not OPENWEATHER_API_KEY:
    raise ValueError("Переменная окружения OPENWEATHER_API_KEY не установлена!")

if not NUTRITIONIX_API_KEY:
    raise ValueError("Переменная окружения NUTRITIONIX_API_KEY не установлена!")

if not NUTRITIONIX_APP_ID:
    raise ValueError("Переменная окружения NUTRITIONIX_APP_ID не установлена!")