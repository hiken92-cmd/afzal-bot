import io
import re
import json
import html
import logging
import asyncio
from typing import Dict, Any, Optional
from PIL import Image
from google import genai
from google.genai import types

from .config import get_gemini_api_key, get_gemini_model

logger = logging.getLogger(__name__)

PRIMARY_MODELS = [
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-3.8-flash"
]

_client: Optional[genai.Client] = None

def get_client() -> genai.Client:
    """Переиспользование HTTP/SSL сессии клиента genai для минимальной задержки."""
    global _client
    if _client is None:
        api_key = get_gemini_api_key()
        if not api_key:
            raise ValueError("API-ключ Google Gemini не настроен!")
        _client = genai.Client(api_key=api_key)
    return _client

def extract_json(raw_text: str) -> dict:
    """Извлекает валидный JSON даже если модель обернула его в markdown блоки или добавила пояснения."""
    clean = raw_text.strip()
    if clean.startswith("```"):
        clean = re.sub(r"^```(?:json)?\s*", "", clean)
        clean = re.sub(r"\s*```$", "", clean)
    clean = clean.strip()
    
    first_brace = clean.find("{")
    last_brace = clean.rfind("}")
    if first_brace != -1 and last_brace != -1:
        clean = clean[first_brace:last_brace+1]
    
    return json.loads(clean)

def optimize_image_for_vision(image_bytes: bytes, max_dim: int = 1024, quality: int = 85) -> bytes:
    """
    Молниеносная проверка и оптимизация фото перед отправкой в Gemini:
    - Если фото уже компактное (до 1024px и до 250 КБ), отдается мгновенно без перекодирования.
    - Иначе быстро масштабируется через BILINEAR.
    """
    if not image_bytes or len(image_bytes) < 100:
        return image_bytes

    try:
        with Image.open(io.BytesIO(image_bytes)) as img:
            w, h = img.size
            if max(w, h) <= max_dim and len(image_bytes) <= 300 * 1024 and img.format == "JPEG" and img.mode == "RGB":
                return image_bytes

            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            
            if max(w, h) > max_dim:
                if w > h:
                    new_w = max_dim
                    new_h = int(h * (max_dim / w))
                else:
                    new_h = max_dim
                    new_w = int(w * (max_dim / h))
                img = img.resize((new_w, new_h), Image.Resampling.BILINEAR)
            
            out_buf = io.BytesIO()
            img.save(out_buf, format="JPEG", quality=quality, optimize=False)
            return out_buf.getvalue()
    except Exception as e:
        logger.warning(f"Сжатие фото пропущено: {e}. Используем оригинал.")
        return image_bytes

NUTRITIONIST_SYSTEM_PROMPT = """Ты — ведущий профессиональный ИИ-нутрициолог. Оценивай блюдо молниеносно и точно.

ПРАВИЛА:
1. ЛЮБАЯ ЕДА = is_food: true (блюдо, продукт, ингредиент, выпечка, фрукт, овощ, напиток, перекус).
2. ОЦЕНКА МАСШТАБА: стандартная тарелка ~25 см, порция мяса ~100-120г, гарнир ~150-180г.
3. СКРЫТЫЕ КАЛОРИИ: учитывай масло при жарке (+70-130 ккал впитанного жира), соусы, сыр.
4. ДЕКОМПОЗИЦИЯ: разбей блюдо на 2-5 ключевых ингредиентов с весом (в граммах) и КБЖУ.
5. УТОЧНЕНИЯ: если есть комментарий пользователя (например: 'съел половину', 'без масла'), строго пересчитай под него!

ОТВЕТ ТОЛЬКО В JSON:
{
  "is_food": true,
  "dish_name": "Название блюда на русском",
  "estimated_weight_g": 350,
  "total_calories": 480,
  "total_proteins": 28.5,
  "total_fats": 18.0,
  "total_carbs": 52.0,
  "confidence_score": 95,
  "cooking_method": "Жарка / тушение / варка / запекание",
  "portion_notes": "Характеристика порции",
  "hidden_calories_alert": "Замечание о скрытом масле/сахаре или 'Скрытых калорий не обнаружено'",
  "ingredients": [
    {
      "name": "Ингредиент",
      "weight_g": 150,
      "calories": 200,
      "proteins": 15.0,
      "fats": 5.0,
      "carbs": 24.0
    }
  ],
  "nutritionist_advice": "Краткий полезный совет нутрициолога."
}
"""

async def analyze_food_image(image_bytes: bytes, user_note: str = "") -> Dict[str, Any]:
    """
    Сверхточный и быстрый анализ блюда по фото с помощью Google Gemini.
    """
    if not image_bytes or len(image_bytes) < 100:
        raise ValueError("Файл фото пустой или не был загружен. Пожалуйста, отправьте фото еще раз.")

    client = get_client()

    # Быстрая оптимизация размера фото
    optimized_bytes = await asyncio.to_thread(optimize_image_for_vision, image_bytes)

    prompt = "Определи блюдо на фото, его вес, раскладку КБЖУ по ингредиентам и совет."
    if user_note and user_note.strip():
        prompt += f"\nУТОЧНЕНИЕ ПОЛЬЗОВАТЕЛЯ: «{user_note.strip()}». Учти при расчете!"

    last_error = None
    for model_name in PRIMARY_MODELS:
        try:
            response = await asyncio.to_thread(
                client.models.generate_content,
                model=model_name,
                contents=[
                    types.Part.from_bytes(data=optimized_bytes, mime_type="image/jpeg"),
                    prompt
                ],
                config=types.GenerateContentConfig(
                    system_instruction=NUTRITIONIST_SYSTEM_PROMPT,
                    response_mime_type="application/json",
                    temperature=0.1
                )
            )
            
            raw_text = response.text.strip()
            data = extract_json(raw_text)
            
            # Если есть калории или ингредиенты — это гарантированно еда
            if data.get("total_calories", 0) > 0 or data.get("ingredients"):
                data["is_food"] = True

            if not data.get("is_food", True):
                return {
                    "is_food": False,
                    "dish_name": "Не еда",
                    "nutritionist_advice": "На фото не обнаружено блюдо или напиток. Пожалуйста, сфотографируйте вашу еду!"
                }
            
            # Нормализация чисел
            data["total_calories"] = round(float(data.get("total_calories", 0)))
            data["total_proteins"] = round(float(data.get("total_proteins", 0)), 1)
            data["total_fats"] = round(float(data.get("total_fats", 0)), 1)
            data["total_carbs"] = round(float(data.get("total_carbs", 0)), 1)
            data["estimated_weight_g"] = round(float(data.get("estimated_weight_g", 0)))
            data["confidence_score"] = int(data.get("confidence_score", 95))
            data["is_food"] = True
            
            return data

        except Exception as e:
            logger.warning(f"Ошибка Gemini ({model_name}): {e}")
            last_error = e
            continue

    raise RuntimeError(f"Сбой анализа фото через ИИ: {last_error}")


async def analyze_meal_text(text: str) -> Dict[str, Any]:
    """
    Сверхточный анализ блюда по текстовому описанию.
    """
    client = get_client()
    prompt = f"Рассчитай точный состав, вес и КБЖУ для приема пищи: «{text}»."

    for model_name in PRIMARY_MODELS:
        try:
            response = await asyncio.to_thread(
                client.models.generate_content,
                model=model_name,
                contents=[prompt],
                config=types.GenerateContentConfig(
                    system_instruction=NUTRITIONIST_SYSTEM_PROMPT,
                    response_mime_type="application/json",
                    temperature=0.1
                )
            )
            
            raw_text = response.text.strip()
            data = extract_json(raw_text)
            
            if data.get("total_calories", 0) > 0 or data.get("ingredients"):
                data["is_food"] = True

            if not data.get("is_food", True):
                return {
                    "is_food": False,
                    "dish_name": "Не еда",
                    "nutritionist_advice": "В тексте не найдено описания еды или напитков. Напишите, что вы съели!"
                }

            data["total_calories"] = round(float(data.get("total_calories", 0)))
            data["total_proteins"] = round(float(data.get("total_proteins", 0)), 1)
            data["total_fats"] = round(float(data.get("total_fats", 0)), 1)
            data["total_carbs"] = round(float(data.get("total_carbs", 0)), 1)
            data["estimated_weight_g"] = round(float(data.get("estimated_weight_g", 0)))
            data["confidence_score"] = int(data.get("confidence_score", 95))
            data["is_food"] = True

            return data

        except Exception as e:
            logger.warning(f"Сбой текстового анализа {model_name}: {e}")
            continue

    raise RuntimeError("Не удалось проанализировать описание блюда.")


def format_nutrition_result(data: Dict[str, Any]) -> str:
    """
    Форматирует результат нутрициолога в красивый Telegram HTML текст.
    """
    if not data.get("is_food", True):
        adv = html.escape(data.get('nutritionist_advice', 'Пожалуйста, пришлите фото блюда.'))
        return f"⚠️ <b>Это не похоже на еду!</b>\n\n{adv}"

    name = html.escape(data.get("dish_name", "Блюдо"))
    cals = data.get("total_calories", 0)
    p = data.get("total_proteins", 0)
    f = data.get("total_fats", 0)
    c = data.get("total_carbs", 0)
    weight = data.get("estimated_weight_g", 0)
    conf = data.get("confidence_score", 95)
    method = html.escape(data.get("cooking_method", ""))
    hidden = html.escape(data.get("hidden_calories_alert", ""))
    advice = html.escape(data.get("nutritionist_advice", ""))
    ingredients = data.get("ingredients", [])

    lines = [
        f"🥗 <b>{name}</b>",
        f"⚖️ Вес порции: ~<b>{weight} г</b>  |  🎯 Точность: <b>{conf}%</b>\n",
        "📊 <b>Энергетическая ценность (КБЖУ):</b>",
        f" 🔥 Калории: <b>{cals} ккал</b>",
        f" 🥩 Белки: <b>{p} г</b>",
        f" 🥑 Жиры: <b>{f} г</b>",
        f" 🍞 Углеводы: <b>{c} г</b>\n"
    ]

    if method:
        lines.append(f"🍳 <b>Способ приготовления:</b> {method}")

    if hidden and "не обнаружено" not in hidden.lower():
        lines.append(f"⚠️ <b>Внимание (скрытые калории):</b> {hidden}\n")
    else:
        lines.append("")

    if ingredients:
        lines.append("🔍 <b>Состав и ингредиенты:</b>")
        for ing in ingredients[:5]:
            i_name = html.escape(ing.get("name", ""))
            i_w = ing.get("weight_g", 0)
            i_cal = ing.get("calories", 0)
            lines.append(f" • {i_name} (~{i_w} г) — <i>{i_cal} ккал</i>")
        lines.append("")

    if advice:
        lines.append(f"💡 <b>Совет нутрициолога:</b>\n<i>{advice}</i>")

    return "\n".join(lines)
