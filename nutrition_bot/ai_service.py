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

def optimize_image_for_vision(image_bytes: bytes, max_dim: int = 1200, quality: int = 88) -> bytes:
    """
    Проверка и оптимизация фото перед отправкой в Gemini:
    - Сохраняет высокую четкость для детального разбора блюда.
    - Масштабирует до оптимальных 1200px.
    """
    if not image_bytes or len(image_bytes) < 100:
        return image_bytes

    try:
        with Image.open(io.BytesIO(image_bytes)) as img:
            w, h = img.size
            if max(w, h) <= max_dim and len(image_bytes) <= 400 * 1024 and img.format == "JPEG" and img.mode == "RGB":
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

# ЭКСПЕРТНЫЙ СИСТЕМНЫЙ ПРОМПТ (Chain-of-Thought глубинного анализа)
NUTRITIONIST_EXPERT_PROMPT = """Ты — ведущий эксперт клинической диетологии, шеф-повар высшей категории и специалист по компьютерному зрению.
Твоя цель — рассчитать реальный вес порции и КБЖУ с максимальной физической и научной точностью (до 95%), а не выдавать абстрактные шаблонные цифры.

МЕТОДОЛОГИЯ ГЛУБОКОГО АНАЛИЗА (Chain-of-Thought перед выдачей цифр):
1. ВИЗУАЛЬНЫЙ АУДИТ МАСШТАБА И ОБЪЕМА:
   - Найди ориентиры: диаметр тарелки (стандартная обеденная 24-26 см, десертная 18-20 см, пиала/супница 12-16 см), вилка (~19 см), ложка, край стола, пальцы.
   - Оцени высоту горки и насыпную плотность: рис и крупы ~0.8 г/см³, свежая зелень ~0.2 г/см³, цельное мясо/рыба ~1.0-1.1 г/см³, супы ~1.0 г/см³.
2. АУДИТ ТЕРМООБРАБОТКИ И СКРЫТЫХ ЖИРОВ (Критически важно!):
   - Оцени поверхность: масляный глянец, золотистая корочка, фритюр, следы обжарки в казане/сковороде.
   - Если блюдо жарилось (плов, картофель, жареная рыба/мясо, лагман, яичница): продукт впитывает от 7% до 15% растительного или животного жира от своей массы! Это дает +80...+180 ккал неучтенных скрытых жиров.
   - Оцени заправки и соусы: майонез, сливочные соусы (+70-130 ккал), растительное масло в салате (1 ст. ложка = ~110-120 ккал).
3. ДЕКОМПОЗИЦИЯ И БАЛАНС:
   - Разложи блюдо на 2-6 конкретных ингредиентов с реальной массой каждого в граммах.
   - Сумма весов ингредиентов должна физически соответствовать общему весу порции.
4. ПОПРАВКИ И УТОЧНЕНИЯ:
   - Если пользователь передал комментарий (например: 'съел половину', 'без масла', 'сметана 2 ложки', 'без хлеба') — строго пересчитай КБЖУ под его факт!

ФОРМАТ ОТВЕТА (СТРОГО JSON):
{
  "is_food": true,
  "dish_name": "Точное кулинарное название блюда на русском",
  "estimated_weight_g": 360,
  "total_calories": 520,
  "total_proteins": 26.5,
  "total_fats": 22.0,
  "total_carbs": 54.0,
  "confidence_score": 95,
  "cooking_method": "Жарка / тушение / запекание / варка",
  "visual_audit": "Оценка масштаба: тарелка ~25см, порция средняя, заметен масляный глянец на гарнире",
  "hidden_calories_alert": "Учтено ~12г масла, впитанного при обжарке (+108 ккал)",
  "ingredients": [
    {
      "name": "Ингредиент",
      "weight_g": 180,
      "calories": 240,
      "proteins": 5.0,
      "fats": 7.0,
      "carbs": 40.0
    }
  ],
  "nutritionist_advice": "Профессиональный совет нутрициолога по балансу БЖУ, сытости и гликемическому индексу."
}
"""

# БЫСТРЫЙ СИСТЕМНЫЙ ПРОМПТ (для экспресс-оценки простых перекусов)
NUTRITIONIST_FAST_PROMPT = """Ты — быстрый ИИ-нутрициолог. Оцени блюдо кратко и емко.
ОТВЕТ ТОЛЬКО В JSON:
{
  "is_food": true,
  "dish_name": "Название блюда на русском",
  "estimated_weight_g": 300,
  "total_calories": 400,
  "total_proteins": 20.0,
  "total_fats": 15.0,
  "total_carbs": 45.0,
  "confidence_score": 90,
  "cooking_method": "Варка / запекание",
  "visual_audit": "Экспресс-оценка порции",
  "hidden_calories_alert": "Скрытых жиров не обнаружено",
  "ingredients": [
    {
      "name": "Ингредиент",
      "weight_g": 150,
      "calories": 200,
      "proteins": 10.0,
      "fats": 5.0,
      "carbs": 25.0
    }
  ],
  "nutritionist_advice": "Краткий совет по приему пищи."
}
"""

async def analyze_food_image(image_bytes: bytes, user_note: str = "", precision: str = "expert") -> Dict[str, Any]:
    """
    Анализ блюда по фото с выбором режима точности:
    - expert: Gemini 3.5 Flash с глубоким визуальным анализом масштаба, посуды и жиров.
    - fast: Gemini 3.5 Flash-lite для молниеносного ответа.
    """
    if not image_bytes or len(image_bytes) < 100:
        raise ValueError("Файл фото пустой или не был загружен. Пожалуйста, отправьте фото еще раз.")

    client = get_client()
    optimized_bytes = await asyncio.to_thread(optimize_image_for_vision, image_bytes)

    if precision == "expert":
        system_instruction = NUTRITIONIST_EXPERT_PROMPT
        models_to_try = ["gemini-3.5-flash", "gemini-3.5-flash-lite"]
        prompt = "Проведи глубокий визуальный аудит блюда: оцени размер тарелки, высоту порции, метод термообработки, скрытое масло и рассчитай точный вес и КБЖУ."
    else:
        system_instruction = NUTRITIONIST_FAST_PROMPT
        models_to_try = ["gemini-3.5-flash-lite", "gemini-3.5-flash"]
        prompt = "Быстро определи блюдо, его вес и КБЖУ."

    if user_note and user_note.strip():
        prompt += f"\nУТОЧНЕНИЕ ПОЛЬЗОВАТЕЛЯ: «{user_note.strip()}». Обязательно учти при расчете!"

    last_error = None
    for model_name in models_to_try:
        try:
            response = await asyncio.to_thread(
                client.models.generate_content,
                model=model_name,
                contents=[
                    types.Part.from_bytes(data=optimized_bytes, mime_type="image/jpeg"),
                    prompt
                ],
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    response_mime_type="application/json",
                    temperature=0.1
                )
            )
            
            if not response or not response.text:
                raise ValueError(f"Модель {model_name} вернула пустой ответ")
            raw_text = response.text.strip()
            data = extract_json(raw_text)
            
            if data.get("total_calories", 0) > 0 or data.get("ingredients"):
                data["is_food"] = True

            if not data.get("is_food", True):
                return {
                    "is_food": False,
                    "dish_name": "Не еда",
                    "nutritionist_advice": "На фото не обнаружено блюдо или напиток. Пожалуйста, сфотографируйте вашу еду!"
                }
            
            # Нормализация
            data["total_calories"] = round(float(data.get("total_calories", 0)))
            data["total_proteins"] = round(float(data.get("total_proteins", 0)), 1)
            data["total_fats"] = round(float(data.get("total_fats", 0)), 1)
            data["total_carbs"] = round(float(data.get("total_carbs", 0)), 1)
            data["estimated_weight_g"] = round(float(data.get("estimated_weight_g", 0)))
            data["confidence_score"] = int(data.get("confidence_score", 95))
            data["precision_mode"] = precision
            data["model_used"] = model_name
            data["is_food"] = True
            
            return data

        except Exception as e:
            logger.warning(f"Ошибка модели {model_name} при анализе фото: {e}")
            last_error = e
            continue

    raise RuntimeError(f"Сбой анализа фото через ИИ: {last_error}")

async def analyze_meal_text(text: str, precision: str = "expert") -> Dict[str, Any]:
    """
    Анализ блюда по тексту с поддержкой экспертного и быстрого режимов.
    """
    client = get_client()

    if precision == "expert":
        system_instruction = NUTRITIONIST_EXPERT_PROMPT
        models_to_try = ["gemini-3.5-flash", "gemini-3.5-flash-lite"]
        prompt = f"Рассчитай научно обоснованный состав, вес и КБЖУ с учетом типичного способа готовки и скрытых масел: «{text}»."
    else:
        system_instruction = NUTRITIONIST_FAST_PROMPT
        models_to_try = ["gemini-3.5-flash-lite", "gemini-3.5-flash"]
        prompt = f"Рассчитай вес и КБЖУ: «{text}»."

    last_error = None
    for model_name in models_to_try:
        try:
            response = await asyncio.to_thread(
                client.models.generate_content,
                model=model_name,
                contents=[prompt],
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    response_mime_type="application/json",
                    temperature=0.1
                )
            )
            
            if not response or not response.text:
                raise ValueError(f"Модель {model_name} вернула пустой ответ")
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
            data["precision_mode"] = precision
            data["model_used"] = model_name
            data["is_food"] = True

            return data

        except Exception as e:
            logger.warning(f"Сбой текстового анализа {model_name}: {e}")
            last_error = e
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
    audit = html.escape(data.get("visual_audit", ""))
    advice = html.escape(data.get("nutritionist_advice", ""))
    precision = data.get("precision_mode", "expert")
    ingredients = data.get("ingredients", [])

    badge = "🎯 <b>Экспертный режим (Gemini 3.5 Flash)</b>" if precision == "expert" else "⚡️ <b>Быстрый режим (Flash-Lite)</b>"

    lines = [
        f"🥗 <b>{name}</b>",
        f"⚖️ Порция: ~<b>{weight} г</b>  |  🎯 Точность: <b>{conf}%</b>",
        f"🔬 {badge}\n",
        "📊 <b>Энергетическая ценность (КБЖУ):</b>",
        f" 🔥 Калории: <b>{cals} ккал</b>",
        f" 🥩 Белки: <b>{p} г</b>",
        f" 🥑 Жиры: <b>{f} г</b>",
        f" 🍞 Углеводы: <b>{c} г</b>\n"
    ]

    if audit:
        lines.append(f"👁 <b>Визуальный аудит:</b> {audit}")

    if method:
        lines.append(f"🍳 <b>Термообработка:</b> {method}")

    if hidden and "не обнаружено" not in hidden.lower():
        lines.append(f"⚠️ <b>Скрытые калории:</b> {hidden}\n")
    else:
        lines.append("")

    if ingredients:
        lines.append("🔍 <b>Состав и ингредиенты:</b>")
        for ing in ingredients[:6]:
            i_name = html.escape(ing.get("name", ""))
            i_w = ing.get("weight_g", 0)
            i_cal = ing.get("calories", 0)
            lines.append(f" • {i_name} (~{i_w} г) — <i>{i_cal} ккал</i>")
        lines.append("")

    if advice:
        lines.append(f"💡 <b>Совет эксперта:</b>\n<i>{advice}</i>")

    return "\n".join(lines)
