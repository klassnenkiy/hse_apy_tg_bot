import os
from dotenv import load_dotenv

load_dotenv()

API_TOKEN = os.getenv("API_TOKEN")
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")

if not API_TOKEN:
    raise ValueError("Переменная окружения API_TOKEN не установлена!")