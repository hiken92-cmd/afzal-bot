from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Filter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from ..database import get_user_mode, get_user_profile, set_user_goals
from ..keyboards import get_nutrition_menu_keyboard

router = Router()

class IsNutritionMode(Filter):
    async def __call__(self, message: Message) -> bool:
        mode = await get_user_mode(message.from_user.id)
        return mode == "nutrition"

class ProfileStates(StatesGroup):
    waiting_gender = State()
    waiting_age = State()
    waiting_weight = State()
    waiting_height = State()
    waiting_activity = State()
    waiting_goal = State()

def get_profile_info_text(profile: dict) -> str:
    cal = profile.get("daily_calories", 2000.0)
    p = profile.get("daily_proteins", 100.0)
    f = profile.get("daily_fats", 70.0)
    c = profile.get("daily_carbs", 250.0)
    w = profile.get("weight", 70.0)
    h = profile.get("height", 175.0)
    a = profile.get("age", 25)
    g = "Мужской" if profile.get("gender") == "male" else "Женский"
    
    act_map = {
        "sedentary": "Сидячий / малоподвижный",
        "light": "Легкая активность (1-3 раза в нед)",
        "moderate": "Умеренная активность (3-5 раз в нед)",
        "high": "Высокая активность (тренировки ежедневно)"
    }
    act_str = act_map.get(profile.get("activity_level"), "Умеренная")

    goal_map = {
        "lose": "📉 Похудение / сброс веса (-15%)",
        "maintain": "⚖️ Поддержание формы",
        "gain": "📈 Набор мышечной массы (+15%)"
    }
    goal_str = goal_map.get(profile.get("goal"), "Поддержание формы")

    return (
        "🎯 <b>Ваша индивидуальная суточная норма КБЖУ:</b>\n\n"
        f"🔥 Калории: <b>{cal:,.0f} ккал</b>\n"
        f"🥩 Белки: <b>{p:.0f} г</b>  |  🥑 Жиры: <b>{f:.0f} г</b>  |  🍞 Углеводы: <b>{c:.0f} г</b>\n\n"
        "📋 <b>Ваши параметры:</b>\n"
        f" • Пол: <b>{g}</b>\n"
        f" • Возраст: <b>{a} лет</b>  |  Вес: <b>{w} кг</b>  |  Рост: <b>{h} см</b>\n"
        f" • Активность: <b>{act_str}</b>\n"
        f" • Цель: <b>{goal_str}</b>\n\n"
        "💡 <i>Расчет выполнен по международной медицинской формуле Миффлина-Сан Жеора. "
        "Вы можете пересчитать норму в любой момент.</i>".replace(",", " ")
    )

def get_calc_goal_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="⚙️ Пересчитать мою норму", callback_data="start_calc_goals")
            ]
        ]
    )

@router.message(F.text == "🎯 Моя норма КБЖУ")
async def show_user_goals(message: Message):
    from ..database import set_user_mode
    await set_user_mode(message.from_user.id, "nutrition")
    profile = await get_user_profile(message.from_user.id)
    text = get_profile_info_text(profile)
    await message.answer(text, reply_markup=get_calc_goal_keyboard(), parse_mode="HTML")

@router.callback_query(F.data == "start_calc_goals")
async def start_goals_wizard(callback: CallbackQuery, state: FSMContext):
    await state.set_state(ProfileStates.waiting_gender)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="👨 Мужской", callback_data="gender:male"),
                InlineKeyboardButton(text="👩 Женский", callback_data="gender:female")
            ]
        ]
    )
    await callback.message.edit_text("1️⃣ <b>Укажите ваш биологический пол:</b>", reply_markup=kb, parse_mode="HTML")
    await callback.answer()

@router.callback_query(ProfileStates.waiting_gender, F.data.startswith("gender:"))
async def step_gender(callback: CallbackQuery, state: FSMContext):
    gender = callback.data.split(":")[1]
    await state.update_data(gender=gender)
    await state.set_state(ProfileStates.waiting_age)
    await callback.message.edit_text("2️⃣ <b>Введите ваш возраст (полных лет):</b>\nНапример: <code>28</code>", parse_mode="HTML")
    await callback.answer()

@router.message(ProfileStates.waiting_age)
async def step_age(message: Message, state: FSMContext):
    try:
        age = int(message.text.strip())
        if not (10 <= age <= 100):
            raise ValueError()
        await state.update_data(age=age)
        await state.set_state(ProfileStates.waiting_weight)
        await message.answer("3️⃣ <b>Введите ваш текущий вес (в кг):</b>\nНапример: <code>74.5</code>", parse_mode="HTML")
    except ValueError:
        await message.answer("⚠️ Пожалуйста, введите корректный возраст от 10 до 100:")

@router.message(ProfileStates.waiting_weight)
async def step_weight(message: Message, state: FSMContext):
    try:
        w_str = message.text.replace(",", ".").strip()
        weight = float(w_str)
        if not (30 <= weight <= 250):
            raise ValueError()
        await state.update_data(weight=weight)
        await state.set_state(ProfileStates.waiting_height)
        await message.answer("4️⃣ <b>Введите ваш рост (в сантиметрах):</b>\nНапример: <code>178</code>", parse_mode="HTML")
    except ValueError:
        await message.answer("⚠️ Введите корректный вес в кг (например: 70 или 82.5):")

@router.message(ProfileStates.waiting_height)
async def step_height(message: Message, state: FSMContext):
    try:
        height = float(message.text.replace(",", ".").strip())
        if not (120 <= height <= 230):
            raise ValueError()
        await state.update_data(height=height)
        await state.set_state(ProfileStates.waiting_activity)

        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🛋 Малоподвижный / Сидячий", callback_data="act:sedentary")],
                [InlineKeyboardButton(text="🚶 Легкая (1-3 раза в нед)", callback_data="act:light")],
                [InlineKeyboardButton(text="🏃 Умеренная (3-5 раз в нед)", callback_data="act:moderate")],
                [InlineKeyboardButton(text="⚡️ Высокая (каждый день)", callback_data="act:high")]
            ]
        )
        await message.answer("5️⃣ <b>Выберите уровень вашей физической активности:</b>", reply_markup=kb, parse_mode="HTML")
    except ValueError:
        await message.answer("⚠️ Введите рост числом в см (например: 175):")

@router.callback_query(ProfileStates.waiting_activity, F.data.startswith("act:"))
async def step_activity(callback: CallbackQuery, state: FSMContext):
    act = callback.data.split(":")[1]
    await state.update_data(activity=act)
    await state.set_state(ProfileStates.waiting_goal)

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📉 Похудение (-15% калорий)", callback_data="goal:lose")],
            [InlineKeyboardButton(text="⚖️ Поддержание веса", callback_data="goal:maintain")],
            [InlineKeyboardButton(text="📈 Набор массы (+15% калорий)", callback_data="goal:gain")]
        ]
    )
    await callback.message.edit_text("6️⃣ <b>Какова ваша основная цель?</b>", reply_markup=kb, parse_mode="HTML")
    await callback.answer()

@router.callback_query(ProfileStates.waiting_goal, F.data.startswith("goal:"))
async def step_finish_goals(callback: CallbackQuery, state: FSMContext):
    goal = callback.data.split(":")[1]
    data = await state.get_data()
    await state.clear()

    gender = data.get("gender", "male")
    age = data.get("age", 25)
    weight = data.get("weight", 70.0)
    height = data.get("height", 175.0)
    act = data.get("activity", "moderate")

    # Формула Миффлина-Сан Жеора
    if gender == "male":
        bmr = 10 * weight + 6.25 * height - 5 * age + 5
    else:
        bmr = 10 * weight + 6.25 * height - 5 * age - 161

    act_multipliers = {
        "sedentary": 1.2,
        "light": 1.375,
        "moderate": 1.55,
        "high": 1.725
    }
    tdee = bmr * act_multipliers.get(act, 1.55)

    if goal == "lose":
        target_calories = round(tdee * 0.85)
    elif goal == "gain":
        target_calories = round(tdee * 1.15)
    else:
        target_calories = round(tdee)

    # Макросы: Белки 25-30%, Жиры 25-30%, Углеводы 45-50%
    target_proteins = round((target_calories * 0.25) / 4.0)
    target_fats = round((target_calories * 0.28) / 9.0)
    target_carbs = round((target_calories - (target_proteins * 4 + target_fats * 9)) / 4.0)

    await set_user_goals(
        user_id=callback.from_user.id,
        calories=target_calories,
        proteins=target_proteins,
        fats=target_fats,
        carbs=target_carbs,
        weight=weight,
        height=height,
        age=age,
        gender=gender,
        activity=act,
        goal=goal
    )

    profile = await get_user_profile(callback.from_user.id)
    text = "🎉 <b>Ваша норма успешно рассчитана и сохранена!</b>\n\n" + get_profile_info_text(profile)
    await callback.message.edit_text(text, reply_markup=get_calc_goal_keyboard(), parse_mode="HTML")
    await callback.answer("Готово!")

