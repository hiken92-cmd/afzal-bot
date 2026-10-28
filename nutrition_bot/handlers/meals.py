import uuid
import html
import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from ..database import (
    get_user_mode,
    set_user_mode,
    add_meal,
    get_today_stats,
    get_user_profile,
    delete_last_meal
)
from ..ai_service import analyze_food_image, analyze_meal_text, format_nutrition_result
from ..keyboards import get_meal_confirm_keyboard, get_nutrition_menu_keyboard

logger = logging.getLogger(__name__)

router = Router()

# Временное хранилище черновиков блюд
_meal_drafts = {}

class MealStates(StatesGroup):
    waiting_meal_text = State()

@router.message(F.text == "📸 Распознать по фото")
async def btn_prompt_photo(message: Message):
    await set_user_mode(message.from_user.id, "nutrition")
    await message.answer(
        "📸 <b>Пришлите фото вашего блюда!</b>\n\n"
        "💡 <i>Советы для максимальной точности:</i>\n"
        "• Фотографируйте сверху под хорошим освещением.\n"
        "• Если в блюде есть нюансы, добавьте их в подпись к фото (например: <i>«жарено на оливковом масле»</i> или <i>«съел половину»</i>).",
        parse_mode="HTML"
    )

@router.message(F.text == "✍️ Описать текстом")
async def btn_prompt_text(message: Message, state: FSMContext):
    await set_user_mode(message.from_user.id, "nutrition")
    await state.set_state(MealStates.waiting_meal_text)
    await message.answer(
        "✍️ <b>Опишите ваш прием пищи текстом:</b>\n\n"
        "Примеры:\n"
        "• <i>Овсяная каша 200г с бананом и столовой ложкой меда</i>\n"
        "• <i>2 вареных яйца, тост с авокадо и капучино без сахара</i>\n"
        "• <i>Гречка 150г, куриная грудка на гриле 120г и свежий огурец</i>\n\n"
        "Напишите сообщение ниже:",
        parse_mode="HTML"
    )

@router.message(MealStates.waiting_meal_text)
async def handle_meal_text_input(message: Message, state: FSMContext):
    await state.clear()
    
    if message.text in ["🔙 Главное меню", "📸 Распознать по фото", "📊 Дневник и статистика", "🎯 Моя норма КБЖУ"]:
        return

    status_msg = await message.answer("⚡️ <i>Рассчитываю состав и КБЖУ блюда...</i>", parse_mode="HTML")
    try:
        data = await analyze_meal_text(message.text)
        if not data.get("is_food", True):
            await status_msg.edit_text(format_nutrition_result(data), parse_mode="HTML")
            return

        draft_id = str(uuid.uuid4())[:8]
        _meal_drafts[draft_id] = {
            "user_id": message.from_user.id,
            "data": data,
            "orig_data": dict(data)
        }

        text = format_nutrition_result(data)
        text += "\n\n⚙️ <i>Вы можете скорректировать порцию кнопками ниже или сразу записать в дневник:</i>"
        
        await status_msg.edit_text(text, reply_markup=get_meal_confirm_keyboard(draft_id), parse_mode="HTML")
    except Exception as e:
        logger.error(f"Ошибка анализа текста блюда: {e}")
        await status_msg.edit_text(f"❌ Ошибка анализа: <code>{html.escape(str(e))}</code>", parse_mode="HTML")


def select_optimal_photo(photos):
    """
    Выбирает оптимальный PhotoSize из message.photo:
    - Ищет размер с max(width, height) от 600 до 1280 px (вес ~50-90 КБ).
    - Скачивание занимает 0.15с вместо 18-20 секунд гигантского оригинала!
    """
    if not photos:
        return None
    for p in reversed(photos):
        dim = max(p.width, p.height)
        if 600 <= dim <= 1280:
            return p
    if len(photos) >= 3:
        return photos[-2]
    return photos[-1]

# Обработка фото: ВСЕ фото (кроме тех, что отправлены в режиме переводчика) направляются нутрициологу!
@router.message(F.photo)
async def handle_food_photo(message: Message, state: FSMContext):
    await state.clear()
    # Автоматически переводим пользователя в режим нутрициолога при отправке фото еды
    await set_user_mode(message.from_user.id, "nutrition")

    status_msg = await message.answer("⚡️ <i>Определяю блюдо, ингредиенты и рассчитываю КБЖУ...</i>", parse_mode="HTML")
    
    try:
        # Скачиваем оптимальный размер фото молниеносно (за 0.15с)
        photo = select_optimal_photo(message.photo)
        file_io = await message.bot.download(photo)
        
        # Надежное извлечение байтов
        if hasattr(file_io, "getvalue"):
            image_bytes = file_io.getvalue()
        else:
            file_io.seek(0)
            image_bytes = file_io.read()

        if not image_bytes or len(image_bytes) < 100:
            await status_msg.edit_text("⚠️ <i>Не удалось получить фото. Пожалуйста, отправьте его еще раз.</i>", parse_mode="HTML")
            return

        user_caption = message.caption or ""
        data = await analyze_food_image(image_bytes, user_note=user_caption)

        if not data.get("is_food", True):
            await status_msg.edit_text(format_nutrition_result(data), parse_mode="HTML")
            return

        draft_id = str(uuid.uuid4())[:8]
        _meal_drafts[draft_id] = {
            "user_id": message.from_user.id,
            "data": data,
            "orig_data": dict(data)
        }

        text = format_nutrition_result(data)
        text += "\n\n⚙️ <i>Вы можете скорректировать порцию кнопками ниже или сразу записать в дневник:</i>"

        await status_msg.edit_text(text, reply_markup=get_meal_confirm_keyboard(draft_id), parse_mode="HTML")

    except Exception as e:
        logger.error(f"Ошибка анализа фото: {e}")
        await status_msg.edit_text(f"❌ Ошибка распознавания: <code>{html.escape(str(e))}</code>", parse_mode="HTML")


# Интерактивные корректировки порции
@router.callback_query(F.data.startswith("adj:"))
async def callback_adjust_meal(callback: CallbackQuery):
    parts = callback.data.split(":")
    action = parts[1]
    draft_id = parts[2]

    draft = _meal_drafts.get(draft_id)
    if not draft or draft["user_id"] != callback.from_user.id:
        await callback.answer("⚠️ Черновик устарел. Отправьте фото заново.", show_alert=True)
        return

    data = draft["data"]

    if action == "plus":
        # +25% к весу и макросам
        factor = 1.25
        data["total_calories"] = round(data["total_calories"] * factor)
        data["total_proteins"] = round(data["total_proteins"] * factor, 1)
        data["total_fats"] = round(data["total_fats"] * factor, 1)
        data["total_carbs"] = round(data["total_carbs"] * factor, 1)
        data["estimated_weight_g"] = round(data["estimated_weight_g"] * factor)
        await callback.answer("Порция увеличена на 25% (+)")

    elif action == "minus":
        # -25% к весу и макросам
        factor = 0.75
        data["total_calories"] = max(10, round(data["total_calories"] * factor))
        data["total_proteins"] = max(0.5, round(data["total_proteins"] * factor, 1))
        data["total_fats"] = max(0.5, round(data["total_fats"] * factor, 1))
        data["total_carbs"] = max(0.5, round(data["total_carbs"] * factor, 1))
        data["estimated_weight_g"] = max(20, round(data["estimated_weight_g"] * factor))
        await callback.answer("Порция уменьшена на 25% (-)")

    elif action == "no_oil":
        # Убрать масло (-100 ккал, -11г жира)
        data["total_calories"] = max(20, data["total_calories"] - 100)
        data["total_fats"] = max(0.0, round(data["total_fats"] - 11.0, 1))
        data["cooking_method"] = "Без добавленного масла / на сухой сковороде"
        await callback.answer("Убрано добавленное масло (-100 ккал)")

    elif action == "bread":
        # Добавить кусок хлеба (+150 ккал, +4г белка, +30г углей)
        data["total_calories"] += 150
        data["total_proteins"] = round(data["total_proteins"] + 4.0, 1)
        data["total_carbs"] = round(data["total_carbs"] + 30.0, 1)
        data["estimated_weight_g"] += 50
        await callback.answer("Добавлен хлеб (+150 ккал)")

    text = format_nutrition_result(data)
    text += "\n\n⚙️ <i>Параметры обновлены. Нажмите «Записать в дневник»:</i>"
    
    try:
        await callback.message.edit_text(text, reply_markup=get_meal_confirm_keyboard(draft_id), parse_mode="HTML")
    except Exception:
        pass


@router.callback_query(F.data.startswith("save_meal:"))
async def callback_save_meal(callback: CallbackQuery):
    draft_id = callback.data.split(":")[1]
    draft = _meal_drafts.get(draft_id)

    if not draft or draft["user_id"] != callback.from_user.id:
        await callback.answer("⚠️ Черновик устарел.", show_alert=True)
        return

    data = draft["data"]
    user_id = callback.from_user.id

    await add_meal(
        user_id=user_id,
        meal_name=data.get("dish_name", "Блюдо"),
        calories=data.get("total_calories", 0),
        proteins=data.get("total_proteins", 0),
        fats=data.get("total_fats", 0),
        carbs=data.get("total_carbs", 0),
        weight_g=data.get("estimated_weight_g", 0),
        confidence=data.get("confidence_score", 90),
        advice=data.get("nutritionist_advice", "")
    )

    del _meal_drafts[draft_id]

    # Актуальная статистика и прогресс
    stats = await get_today_stats(user_id)
    profile = await get_user_profile(user_id)
    goal_cal = profile.get("daily_calories", 2000.0)

    rem_cal = max(0.0, goal_cal - stats["calories"])
    pct = min(100, int((stats["calories"] / goal_cal) * 100)) if goal_cal > 0 else 0

    success_text = (
        f"✅ <b>Блюдо записано в ваш дневник!</b>\n\n"
        f"🍽 <b>{html.escape(data.get('dish_name', 'Блюдо'))}</b> (+{data.get('total_calories')} ккал)\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📈 <b>Итог за сегодня ({stats['count']} приемов):</b>\n"
        f"🔥 <b>{stats['calories']:,.0f}</b> из <b>{goal_cal:,.0f} ккал</b> ({pct}% нормы)\n"
        f"🥩 Б: {stats['proteins']:.1f}г  |  🥑 Ж: {stats['fats']:.1f}г  |  🍞 У: {stats['carbs']:.1f}г\n"
        f"⏳ Осталось до нормы: <b>{rem_cal:,.0f} ккал</b>".replace(",", " ")
    )

    await callback.message.edit_text(success_text, parse_mode="HTML")
    await callback.answer("✅ Успешно сохранено!")


@router.callback_query(F.data.startswith("cancel_meal:"))
async def callback_cancel_meal(callback: CallbackQuery):
    draft_id = callback.data.split(":")[1]
    if draft_id in _meal_drafts:
        del _meal_drafts[draft_id]
    await callback.message.edit_text("❌ Запись блюда отменена.", parse_mode="HTML")
    await callback.answer()


@router.message(F.text == "🗑 Удалить последний прием")
async def btn_delete_last(message: Message):
    ok = await delete_last_meal(message.from_user.id)
    if ok:
        stats = await get_today_stats(message.from_user.id)
        await message.answer(
            f"🗑 <b>Последний прием пищи успешно удален!</b>\n\n"
            f"Текущий итог за сегодня: <b>{stats['calories']:,.0f} ккал</b> ({stats['count']} приемов).".replace(",", " "),
            reply_markup=get_nutrition_menu_keyboard(),
            parse_mode="HTML"
        )
    else:
        await message.answer("⚠️ В вашем дневнике за сегодня пока нет записей.",
                             reply_markup=get_nutrition_menu_keyboard(), parse_mode="HTML")


# Свободный текстовый ввод блюда в режиме нутрициолога
@router.message(F.text)
async def handle_nutrition_free_text(message: Message):
    txt = message.text.strip()
    if txt.startswith("/") or txt in [
        "📸 распознать по фото", "✍️ описать текстом", "📊 дневник и статистика",
        "🎯 моя норма кбжу", "🗑 удалить последний прием", "🔙 главное меню",
        "🥗 афзал нутрициолог", "🌐 афзал переводчик", "💵 афзал валютчик", "ℹ️ о боте"
    ]:
        return

    mode = await get_user_mode(message.from_user.id)
    if mode != "nutrition":
        return

    # Если пользователь в режиме нутрициолога просто написал блюдо текстом
    status_msg = await message.answer("⚡️ <i>Рассчитываю состав и КБЖУ блюда...</i>", parse_mode="HTML")
    try:
        data = await analyze_meal_text(txt)
        if not data.get("is_food", True):
            await status_msg.edit_text(format_nutrition_result(data), parse_mode="HTML")
            return

        draft_id = str(uuid.uuid4())[:8]
        _meal_drafts[draft_id] = {
            "user_id": message.from_user.id,
            "data": data,
            "orig_data": dict(data)
        }

        text = format_nutrition_result(data)
        text += "\n\n⚙️ <i>Вы можете скорректировать порцию кнопками ниже или сразу записать в дневник:</i>"
        await status_msg.edit_text(text, reply_markup=get_meal_confirm_keyboard(draft_id), parse_mode="HTML")
    except Exception as e:
        logger.error(f"Ошибка свободного текста: {e}")
        await status_msg.edit_text(f"❌ Ошибка анализа: <code>{html.escape(str(e))}</code>", parse_mode="HTML")
