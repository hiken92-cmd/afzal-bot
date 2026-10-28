from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Filter

from ..database import (
    get_user_mode,
    get_today_meals,
    get_today_stats,
    get_user_profile,
    clear_today_meals
)
from ..keyboards import get_stats_actions_keyboard, get_nutrition_menu_keyboard

router = Router()

class IsNutritionMode(Filter):
    async def __call__(self, message: Message) -> bool:
        mode = await get_user_mode(message.from_user.id)
        return mode == "nutrition"

def make_progress_bar(current: float, target: float, length: int = 10) -> str:
    if target <= 0:
        return "░" * length + " 0%"
    pct = min(150, int((current / target) * 100))
    filled = min(length, int((current / target) * length))
    bar = "█" * filled + "░" * (length - filled)
    return f"[{bar}] {pct}%"

@router.message(F.text == "📊 Дневник и статистика")
async def show_diary_stats(message: Message):
    user_id = message.from_user.id
    from ..database import set_user_mode
    await set_user_mode(user_id, "nutrition")
    stats = await get_today_stats(user_id)
    meals = await get_today_meals(user_id)
    profile = await get_user_profile(user_id)

    target_cal = profile.get("daily_calories", 2000.0)
    target_p = profile.get("daily_proteins", 100.0)
    target_f = profile.get("daily_fats", 70.0)
    target_c = profile.get("daily_carbs", 250.0)

    cal_bar = make_progress_bar(stats["calories"], target_cal)
    p_bar = make_progress_bar(stats["proteins"], target_p)
    f_bar = make_progress_bar(stats["fats"], target_f)
    c_bar = make_progress_bar(stats["carbs"], target_c)

    rem_cal = target_cal - stats["calories"]
    rem_str = f"Осталось: <b>{rem_cal:,.0f} ккал</b>" if rem_cal >= 0 else f"Превышение: <b>{abs(rem_cal):,.0f} ккал</b>"

    lines = [
        "📊 <b>Ваш дневник питания за сегодня:</b>\n",
        f"🔥 <b>Калории:</b> {stats['calories']:,.0f} / {target_cal:,.0f} ккал",
        f"└ {cal_bar}  •  {rem_str}\n",
        f"🥩 <b>Белки:</b> {stats['proteins']:.1f} / {target_p:.0f} г",
        f"└ {p_bar}\n",
        f"🥑 <b>Жиры:</b> {stats['fats']:.1f} / {target_f:.0f} г",
        f"└ {f_bar}\n",
        f"🍞 <b>Углеводы:</b> {stats['carbs']:.1f} / {target_c:.0f} г",
        f"└ {c_bar}\n".replace(",", " "),
        "━━━━━━━━━━━━━━━━━━"
    ]

    if not meals:
        lines.append("<i>Сегодня вы еще не добавляли приемы пищи. Отправьте фото вашего блюда!</i>")
        reply_markup = None
    else:
        lines.append(f"🍽 <b>История приемов пищи ({len(meals)}):</b>")
        for idx, m in enumerate(meals[:10], start=1):
            time_str = m["created_at"].split()[1][:5] if " " in m["created_at"] else ""
            lines.append(
                f"{idx}. <b>{m['meal_name']}</b> (~{m['weight_g']:.0f}г) <i>[{time_str}]</i>\n"
                f"   └ <b>{m['calories']:.0f} ккал</b> (Б:{m['proteins']:.1f}г | Ж:{m['fats']:.1f}г | У:{m['carbs']:.1f}г)"
            )
        reply_markup = get_stats_actions_keyboard()

    await message.answer("\n".join(lines), reply_markup=reply_markup, parse_mode="HTML")


@router.callback_query(F.data == "clear_today_diary")
async def callback_clear_diary(callback: CallbackQuery):
    count = await clear_today_meals(callback.from_user.id)
    await callback.message.edit_text(
        f"🗑 <b>Дневник за сегодня очищен!</b> Удалено записей: <b>{count}</b>.",
        parse_mode="HTML"
    )
    await callback.answer("Дневник очищен!")

