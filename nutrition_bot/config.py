import os
from dotenv import load_dotenv

# Загрузка переменных окружения из .env
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")

PORT = int(os.getenv("PORT", "8080"))
HOST = os.getenv("HOST", "0.0.0.0")

# URL для Telegram Web App (Mini App)
# Для локального теста можно использовать ngrok или локальный адрес
WEB_APP_URL = os.getenv("WEB_APP_URL", "http://localhost:8080")

def get_gemini_api_key() -> str:
    return os.getenv("GEMINI_API_KEY", GEMINI_API_KEY)

def get_gemini_model() -> str:
    return os.getenv("GEMINI_MODEL", GEMINI_MODEL)

def get_web_app_url() -> str:
    return os.getenv("WEB_APP_URL", WEB_APP_URL)
