import os
import base64
import json
import logging
from aiohttp import web

from .ai_service import analyze_food_image, analyze_meal_text
from .translator_service import translate_text_fast
from .currency_service import get_bank_rates, generate_currency_infographic_bytes

logger = logging.getLogger(__name__)

WEB_DIR = os.path.join(os.path.dirname(__file__), "web")

async def handle_index(request):
    """Отдает главную страницу веб-интерфейса Telegram WebApp."""
    index_path = os.path.join(WEB_DIR, "index.html")
    return web.FileResponse(index_path)

async def api_analyze_food(request):
    """API анализа еды по фото (base64) или по тексту."""
    try:
        data = await request.json()
        
        # Анализ по фото
        if "image_base64" in data and data["image_base64"]:
            img_bytes = base64.b64decode(data["image_base64"])
            user_note = data.get("note", "")
            res = await analyze_food_image(img_bytes, user_note=user_note)
            return web.json_response(res)
            
        # Анализ по тексту
        elif "text" in data and data["text"]:
            res = await analyze_meal_text(data["text"])
            return web.json_response(res)
            
        return web.json_response({"error": "Отсутствует фото или текст"}, status=400)
    except Exception as e:
        logger.error(f"Ошибка API analyze_food: {e}")
        return web.json_response({"error": str(e)}, status=500)

async def api_translate(request):
    """API перевода текста."""
    try:
        data = await request.json()
        text = data.get("text", "")
        target_lang = data.get("target_lang", "ru")
        style = data.get("style", "general")

        if not text:
            return web.json_response({"error": "Текст не передан"}, status=400)

        res = await translate_text_fast(text, target_lang=target_lang, style=style)
        return web.json_response(res)
    except Exception as e:
        logger.error(f"Ошибка API translate: {e}")
        return web.json_response({"error": str(e)}, status=500)

async def api_currency(request):
    """API актуальных курсов валют."""
    try:
        banks, best_buy, best_sell, cbu_data = get_bank_rates()
        return web.json_response({
            "cbu": cbu_data,
            "best_buy": best_buy,
            "best_sell": best_sell,
            "banks": banks
        })
    except Exception as e:
        logger.error(f"Ошибка API currency: {e}")
        return web.json_response({"error": str(e)}, status=500)

async def api_currency_infographic(request):
    """Отдает картинку инфографики курсов валют."""
    try:
        img_bytes = generate_currency_infographic_bytes()
        return web.Response(body=img_bytes, content_type="image/jpeg")
    except Exception as e:
        return web.Response(text=str(e), status=500)

def create_web_app() -> web.Application:
    """Создает приложение aiohttp для Web App."""
    app = web.Application()
    
    # Роуты API
    app.router.add_get("/", handle_index)
    app.router.add_post("/api/analyze-food", api_analyze_food)
    app.router.add_post("/api/translate", api_translate)
    app.router.add_get("/api/currency", api_currency)
    app.router.add_get("/api/currency/infographic", api_currency_infographic)
    
    # Статические файлы (style.css, app.js)
    app.router.add_static("/", WEB_DIR)
    
    return app

