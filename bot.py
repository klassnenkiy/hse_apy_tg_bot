import logging
import asyncio
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from config import API_TOKEN
from handlers import start, set_profile, log_water, log_food, log_workout, check_progress, process_weight, process_height, process_age, process_activity, process_city, process_food_quantity


logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

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
    async def main():
        await dp.start_polling(bot)

    asyncio.run(main())
