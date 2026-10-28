import asyncio
import io
import logging
import os
import sys

# Настройка UTF-8 для вывода в консоль Windows
if sys.platform == "win32":
    if sys.stdout and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    if sys.stderr and sys.stderr.encoding.lower() != "utf-8":
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# Добавляем родительский каталог в sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(BASE_DIR)
if PARENT_DIR not in sys.path:
    sys.path.insert(0, PARENT_DIR)

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.types import MenuButtonWebApp, MenuButtonDefault, WebAppInfo

from nutrition_bot.config import BOT_TOKEN, PORT, HOST, WEB_APP_URL
from nutrition_bot.database import init_db
from nutrition_bot.handlers import common, currency, translator, meals, stats, profile
from nutrition_bot.web_server import create_web_app

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

async def start_web_server():
    """Запуск встроенного веб-сервера aiohttp."""
    app = create_web_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host=HOST, port=PORT)
    await site.start()
    logger.info(f"🌐 Веб-сервер интерфейса успешно запущен на http://{HOST}:{PORT}")
    return runner

async def main():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN не установлен в переменных окружения!")
        return

    # 1. Инициализация базы данных SQLite
    await init_db()
    logger.info("База данных SQLite инициализирована.")

    # 2. Запуск встроенного веб-сервера для Web App сайта
    runner = await start_web_server()

    # 3. Настройка бота
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher(storage=MemoryStorage())

    # Регистрация роутеров в строгом порядке
    dp.include_router(common.router)
    dp.include_router(currency.router)
    dp.include_router(translator.router)
    dp.include_router(meals.router)
    dp.include_router(stats.router)
    dp.include_router(profile.router)

    me = await bot.get_me()
    logger.info(f"Запущен бот @{me.username} (ID: {me.id})")

    # Настройка кнопки постоянного меню в Telegram
    try:
        if WEB_APP_URL.startswith("https://"):
            await bot.set_chat_menu_button(
                menu_button=MenuButtonWebApp(
                    text="📱 Веб-сайт",
                    web_app=WebAppInfo(url=WEB_APP_URL)
                )
            )
        else:
            await bot.set_chat_menu_button(menu_button=MenuButtonDefault())
    except Exception as e:
        logger.warning(f"Не удалось настроить MenuButton: {e}")

    # Сбрасываем старые накопившиеся вебхуки и запускаем поллинг
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        await runner.cleanup()
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен.")
