import os
import re
import base64
import json
import asyncio
import logging
from aiohttp import web

from .ai_service import analyze_food_image, analyze_meal_text
from .translator_service import translate_text_fast
from .currency_service import get_bank_rates, generate_currency_infographic_bytes

logger = logging.getLogger(__name__)

WEB_DIR = os.path.join(os.path.dirname(__file__), "web")

# Middleware для поддержки CORS и Telegram Web
@web.middleware
async def cors_middleware(request, handler):
    if request.method == "OPTIONS":
        response = web.Response(status=200)
    else:
        try:
            response = await handler(request)
        except web.HTTPException as ex:
            response = ex
        except Exception as e:
            logger.error(f"Необработанная ошибка запроса {request.path}: {e}")
            response = web.json_response({"error": str(e)}, status=500)

    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Requested-With"
    return response

async def handle_index(request):
    """Отдает главную страницу веб-интерфейса Telegram WebApp."""
    index_path = os.path.join(WEB_DIR, "index.html")
    return web.FileResponse(index_path)

async def handle_health(request):
    """Быстрый health-check для Render и keep-alive."""
    return web.json_response({"status": "ok"})


async def api_analyze_food(request):
    """API анализа еды по фото (base64) или по тексту с поддержкой выбора точности."""
    try:
        data = await request.json()
        precision = data.get("precision", "expert")
        if precision not in ("expert", "fast"):
            precision = "expert"

        # Анализ по фото
        if "image_base64" in data and data["image_base64"]:
            b64_str = re.sub(r"^data:image/[^;]+;base64,", "", str(data["image_base64"]))
            img_bytes = base64.b64decode(b64_str)
            user_note = str(data.get("note", ""))
            res = await analyze_food_image(img_bytes, user_note=user_note, precision=precision)
            return web.json_response(res)

        # Анализ по тексту
        elif "text" in data and str(data["text"]).strip():
            res = await analyze_meal_text(str(data["text"]).strip(), precision=precision)
            return web.json_response(res)

        return web.json_response({"error": "Отсутствует фото или текст"}, status=400)
    except Exception as e:
        logger.error(f"Ошибка API analyze_food: {e}")
        return web.json_response({"error": str(e)}, status=500)


async def api_translate(request):
    """API перевода текста."""
    try:
        data = await request.json()
        text = str(data.get("text", "")).strip()
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
    """API актуальных курсов валют (без блокировки event loop)."""
    try:
        banks, best_buy, best_sell, cbu_data = await asyncio.to_thread(get_bank_rates)
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
    """Отдает картинку инфографики курсов валют (без блокировки event loop)."""
    try:
        img_bytes = await asyncio.to_thread(generate_currency_infographic_bytes)
        return web.Response(body=img_bytes, content_type="image/jpeg")
    except Exception as e:
        return web.Response(text=str(e), status=500)


def create_web_app() -> web.Application:
    """
    Создает приложение aiohttp для Web App с увеличенным лимитом загрузки фото (до 20 МБ)
    и поддержкой CORS.
    """
    app = web.Application(
        client_max_size=20 * 1024 * 1024,  # 20 МБ для фото высокого разрешения
        middlewares=[cors_middleware]
    )

    # Роуты API
    app.router.add_get("/", handle_index)
    app.router.add_get("/health", handle_health)
    app.router.add_post("/api/analyze-food", api_analyze_food)
    app.router.add_post("/api/translate", api_translate)
    app.router.add_get("/api/currency", api_currency)
    app.router.add_get("/api/currency/infographic", api_currency_infographic)

    # Статические файлы (style.css, app.js)
    app.router.add_static("/", WEB_DIR)

    return app
