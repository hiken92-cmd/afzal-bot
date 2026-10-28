import urllib.request
import urllib.parse
import json
import logging
import asyncio
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
    "general": "Обычный / Нейтральный",
    "business": "Деловой / Официальный",
    "casual": "Разговорный / Дружеский",
    "literary": "Художественный / Литературный"
}

def fast_translate_text(text: str, target_lang: str = "ru") -> Dict[str, Any]:
    """
    Сверхбыстрый нейроперевод текста через Google Translate API (0.2-0.4 сек).
    """
    encoded_text = urllib.parse.quote(text)
    url = f"https://translate.googleapis.com/translate_a/single?client=dict-chrome-ex&sl=auto&tl={target_lang}&dt=t&q={encoded_text}"
    
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    })
    
    with urllib.request.urlopen(req, timeout=5) as response:
        data = json.loads(response.read().decode("utf-8"))
        
        # Сборка предложений
        translated_parts = []
        if data and len(data) > 0 and data[0]:
            for sentence in data[0]:
                if sentence and len(sentence) > 0 and sentence[0]:
                    translated_parts.append(sentence[0])
        
        translated_text = "".join(translated_parts).strip()
        detected_lang = data[2] if len(data) > 2 else "auto"
        
        return {
            "translated_text": translated_text,
            "detected_lang": detected_lang,
            "target_lang": target_lang
        }

async def translate_text_fast(text: str, target_lang: str = "ru", style: str = "general") -> Dict[str, Any]:
    """
    Асинхронная обертка для быстрого перевода.
    Если выбран специализированный стиль, адаптирует текст.
    """
    res = await asyncio.to_thread(fast_translate_text, text, target_lang)
    
    # Если стиль не general и длина текста приличная, можно быстро адаптировать через Gemini
    if style != "general" and len(text) > 10:
        try:
            api_key = get_gemini_api_key()
            if api_key:
                client = genai.Client(api_key=api_key)
                prompt = (
                    f"Стилизуй следующий перевод в {STYLES.get(style, style)} стиль. "
                    f"Сохраняй точный смысл, верни ТОЛЬКО готовый перевод без вступительных слов:\n\n"
                    f"{res['translated_text']}"
                )
                gem_res = await asyncio.to_thread(
                    client.models.generate_content,
                    model="gemini-3.5-flash-lite",
                    contents=[prompt]
                )
                if gem_res.text:
                    res["translated_text"] = gem_res.text.strip()
        except Exception as e:
            logger.warning(f"Ошибка стилизации перевода: {e}")
            
    return res

async def translate_image_ocr(image_bytes: bytes, target_lang: str = "ru", style: str = "general") -> Dict[str, Any]:
    """
    Сверхбыстрое оптическое распознавание (OCR) и перевод текста с фото через Gemini 3.5 Flash-lite.
    """
    api_key = get_gemini_api_key()
    if not api_key:
        raise ValueError("API-ключ Google Gemini не настроен!")

    optimized_bytes = await asyncio.to_thread(optimize_image_for_vision, image_bytes)
    client = genai.Client(api_key=api_key)

    lang_name = LANGUAGES.get(target_lang, target_lang)
    style_name = STYLES.get(style, "нейтральный")

    prompt = f"""Найди весь текст на изображении, определи его исходный язык и переведи на {lang_name}.
Стиль перевода: {style_name}.

Верни ответ ТОЛЬКО в формате JSON:
{{
  "has_text": true,
  "original_text": "распознанный исходный текст",
  "translated_text": "переведенный текст",
  "detected_lang": "исходный язык"
}}
Если на изображении нет текста, верни: {{"has_text": false}}
"""

    for m in ["gemini-3.5-flash-lite", "gemini-3.1-flash-lite", "gemini-3.8-flash"]:
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
            continue

    raise RuntimeError("Не удалось перевести текст с фото.")

