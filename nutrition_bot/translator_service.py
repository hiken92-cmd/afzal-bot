import logging
import asyncio
import json
from typing import Dict, Any, Optional
from google import genai
from google.genai import types

from .config import get_gemini_api_key, get_gemini_model
from .ai_service import optimize_image_for_vision

logger = logging.getLogger(__name__)

LANGUAGES = {
    "ru": "Русский",
    "en": "English",
    "uz": "O'zbekcha",
    "es": "Español",
    "de": "Deutsch",
    "fr": "Français",
    "tr": "Türkçe",
    "zh": "中文 (Китайский)",
    "ar": "العربية (Арабский)",
    "ja": "日本語 (Японский)",
    "ko": "한국어 (Корейский)",
    "it": "Italiano"
}

STYLES = {
    "general": "Естественный, грамотный и точный перевод",
    "business": "Строгий деловой, официальный и дипломатичный стиль (для деловой переписки и документов)",
    "casual": "Живой разговорный, дружеский стиль со сленгом и естественными идиомами",
    "literary": "Богатый художественный и литературный стиль с красивыми речевыми оборотами"
}

_gemini_client: Optional[genai.Client] = None

def get_client() -> genai.Client:
    global _gemini_client
    if _gemini_client is None:
        api_key = get_gemini_api_key()
        if not api_key:
            raise ValueError("API-ключ Google Gemini не настроен!")
        _gemini_client = genai.Client(api_key=api_key)
    return _gemini_client

async def translate_text_fast(text: str, target_lang: str = "ru", style: str = "general") -> Dict[str, Any]:
    """
    Высокоточный нейроперевод текста нового поколения через Gemini 3.5 Flash-lite.
    Учитывает контекст, идиомы, профессиональную терминологию и выбранный стиль.
    """
    client = get_client()
    target_name = LANGUAGES.get(target_lang, target_lang)
    style_desc = STYLES.get(style, STYLES["general"])

    system_instruction = (
        "Ты — выдающийся синхронный переводчик и профессиональный лингвист высшей категории.\n"
        "Твоя задача — переводить тексты с глубоким пониманием контекста, идиоматических выражений, "
        "культурологических нюансов и сленга.\n"
        "ПРАВИЛА:\n"
        "1. Переводи точно, естественно и красиво, передавая истинный смысл, а не дословный машинный подстрочник.\n"
        "2. Строго соблюдай требуемый стиль речи.\n"
        "3. Выводи ИСКЛЮЧИТЕЛЬНО готовый переведенный текст. Никаких вступительных слов, пояснений, кавычек или примечаний."
    )

    prompt = (
        f"Целевой язык перевода: {target_name}\n"
        f"Требуемый стиль: {style_desc}\n\n"
        f"Исходный текст для перевода:\n{text}"
    )

    config = types.GenerateContentConfig(
        system_instruction=system_instruction,
        temperature=0.2
    )

    models_to_try = ["gemini-3.5-flash-lite", "gemini-3.5-flash", "gemini-3.1-pro-preview"]
    last_err = None

    for model_name in models_to_try:
        try:
            res = await asyncio.to_thread(
                client.models.generate_content,
                model=model_name,
                contents=prompt,
                config=config
            )
            if res and res.text:
                translated_text = res.text.strip()
                return {
                    "translated_text": translated_text,
                    "detected_lang": "auto",
                    "target_lang": target_lang
                }
        except Exception as e:
            logger.warning(f"Ошибка перевода на модели {model_name}: {e}")
            last_err = e
            continue

    raise RuntimeError(f"Не удалось выполнить перевод: {last_err}")

async def translate_image_ocr(image_bytes: bytes, target_lang: str = "ru", style: str = "general") -> Dict[str, Any]:
    """
    Сверхточное оптическое распознавание (OCR) и перевод текста с фото через мультимодальный Gemini 3.5 Flash-lite.
    """
    client = get_client()
    optimized_bytes = await asyncio.to_thread(optimize_image_for_vision, image_bytes)

    lang_name = LANGUAGES.get(target_lang, target_lang)
    style_desc = STYLES.get(style, STYLES["general"])

    prompt = f"""Внимательно распознай весь текст на изображении (вывески, документы, надписи, меню, чеки).
Определи исходный язык и переведи текст на {lang_name} с сохранением точного контекста.
Стиль перевода: {style_desc}.

Верни результат СТРОГО в формате JSON:
{{
  "has_text": true,
  "original_text": "распознанный исходный текст",
  "translated_text": "высокоточный литературный перевод",
  "detected_lang": "исходный язык"
}}
Если на изображении нет читаемого текста, верни: {{"has_text": false}}
"""

    models_to_try = ["gemini-3.5-flash-lite", "gemini-3.5-flash"]
    last_err = None

    for m in models_to_try:
        try:
            response = await asyncio.to_thread(
                client.models.generate_content,
                model=m,
                contents=[
                    types.Part.from_bytes(data=optimized_bytes, mime_type="image/jpeg"),
                    prompt
                ],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.1
                )
            )
            data = json.loads(response.text.strip())
            return data
        except Exception as e:
            logger.warning(f"Ошибка OCR перевода {m}: {e}")
            last_err = e
            continue

    raise RuntimeError(f"Не удалось перевести текст с фото: {last_err}")
