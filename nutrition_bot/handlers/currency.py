import re
import html
import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Filter

from ..database import get_user_mode, set_user_mode
from ..keyboards import (
    get_currency_menu_keyboard,
    get_usd_quick_keyboard,
    get_uzs_quick_keyboard
)
from ..currency_service import (
    get_cbu_rates,
    get_bank_rates,
    generate_currency_infographic_bytes,
    convert_usd_to_uzs,
    convert_uzs_to_usd
)

logger = logging.getLogger(__name__)

router = Router()

class IsCurrencyMode(Filter):
    async def __call__(self, message: Message) -> bool:
        mode = await get_user_mode(message.from_user.id)
        return mode == "currency"

class CurrencyStates(StatesGroup):
    waiting_usd_amount = State()
    waiting_uzs_amount = State()

def make_rates_caption(force_refresh: bool = False) -> str:
    banks, best_buy, best_sell, cbu_data = get_bank_rates(force_refresh=force_refresh)
    cbu_usd = cbu_data["usd"]["rate"]
    cbu_diff = cbu_data["usd"]["diff"]
    cbu_date = cbu_data["usd"]["date"]
    diff_sign = "+" if cbu_diff >= 0 else ""

    eur_rate = cbu_data["eur"]["rate"]
    rub_rate = cbu_data["rub"]["rate"]

    best_buy_bank = html.escape(next((b["name"] for b in banks if b["buy"] == best_buy), ""))
    best_sell_bank = html.escape(next((b["name"] for b in banks if b["sell"] == best_sell), ""))

    lines = [
        f"💵 <b>Курсы валют в банках Узбекистана ({cbu_date})</b>\n",
        f"🏛 <b>ЦБ РУз:</b> 1 USD = <b>{cbu_usd:,.2f} UZS</b> ({diff_sign}{cbu_diff:,.2f})".replace(",", " "),
        f"💶 1 EUR = {eur_rate:,.2f} UZS  |  🪙 1 RUB = {rub_rate:,.2f} UZS\n".replace(",", " "),
        f"🟢 <b>Лучший курс покупки (сдать USD):</b>\n └ <code>{best_buy:,.0f} UZS</code> — <b>{best_buy_bank}</b>\n".replace(",", " "),
        f"🔴 <b>Лучший курс продажи (купить USD):</b>\n └ <code>{best_sell:,.0f} UZS</code> — <b>{best_sell_bank}</b>\n".replace(",", " "),
        "💡 <i>Отправьте любую сумму (например: <code>100$</code> или <code>2 000 000 сум</code>), и я мгновенно посчитаю обмен!</i>"
    ]
    return "\n".join(lines)


@router.message(F.text == "💵 Афзал Валютчик")
async def enter_currency_mode(message: Message, state: FSMContext):
    await state.clear()
    await set_user_mode(message.from_user.id, "currency")
    
    status_msg = await message.answer("⏳ <i>Формирую инфографику курсов в банках...</i>", parse_mode="HTML")
    try:
        img_bytes = generate_currency_infographic_bytes(force_refresh=False)
        caption = make_rates_caption(force_refresh=False)
        
        photo_file = BufferedInputFile(img_bytes, filename="currency_banks_uz.jpg")
        await message.answer_photo(
            photo=photo_file,
            caption=caption,
            reply_markup=get_currency_menu_keyboard(),
            parse_mode="HTML"
        )
        await status_msg.delete()
    except Exception as e:
        logger.error(f"Ошибка инфографики: {e}")
        await status_msg.edit_text(f"❌ Ошибка генерации инфографики: <code>{html.escape(str(e))}</code>")

@router.message(F.text.in_({"📊 Курсы в банках (Инфографика)", "🔄 Обновить курс"}))
async def send_infographic(message: Message):
    status_msg = await message.answer("🔄 <i>Обновляю котировки...</i>", parse_mode="HTML")
    try:
        img_bytes = generate_currency_infographic_bytes(force_refresh=True)
        caption = make_rates_caption(force_refresh=False)
        photo_file = BufferedInputFile(img_bytes, filename="currency_banks_uz.jpg")
        await message.answer_photo(
            photo=photo_file,
            caption=caption,
            reply_markup=get_currency_menu_keyboard(),
            parse_mode="HTML"
        )
        await status_msg.delete()
    except Exception as e:
        logger.error(f"Ошибка обновления инфографики: {e}")
        await status_msg.edit_text(f"❌ Ошибка: {html.escape(str(e))}")

@router.message(F.text == "🇺🇸 USD ➔ 🇺🇿 UZS")
async def prompt_usd_to_uzs(message: Message, state: FSMContext):
    await state.set_state(CurrencyStates.waiting_usd_amount)
    await message.answer(
        "🇺🇸 <b>Конвертер USD ➔ UZS (Доллары в Сумы)</b>\n\n"
        "Выберите быструю сумму кнопками ниже или напишите любое число в чат (например: <code>150</code> или <code>2500</code>):",
        reply_markup=get_usd_quick_keyboard(),
        parse_mode="HTML"
    )

@router.message(F.text == "🇺🇿 UZS ➔ 🇺🇸 USD")
async def prompt_uzs_to_usd(message: Message, state: FSMContext):
    await state.set_state(CurrencyStates.waiting_uzs_amount)
    await message.answer(
        "🇺🇿 <b>Конвертер UZS ➔ USD (Сумы в Доллары)</b>\n\n"
        "Выберите быструю сумму кнопками ниже или напишите сумму в сумах (например: <code>1500000</code> или <code>3000000</code>):",
        reply_markup=get_uzs_quick_keyboard(),
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("calc_usd:"))
async def callback_calc_usd(callback: CallbackQuery):
    amount = float(callback.data.split(":")[1])
    res = convert_usd_to_uzs(amount)
    text = (
        f"💵 <b>${amount:,.0f} в узбекских сумах:</b>\n\n"
        f"🏛 <b>По курсу ЦБ РУз:</b> <code>{res['cbu_total_formatted']} UZS</code>\n"
        f"🟢 <b>В лучшем банке (покупка):</b> <code>{res['bank_total_formatted']} UZS</code>\n\n"
        f"<i>(Курс лучшей покупки: {res['best_buy_rate']:,.0f} UZS за $1)</i>".replace(",", " ")
    )
    await callback.message.reply(text, parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data.startswith("calc_uzs:"))
async def callback_calc_uzs(callback: CallbackQuery):
    amount = float(callback.data.split(":")[1])
    res = convert_uzs_to_usd(amount)
    text = (
        f"🇺🇿 <b>{res['amount_uzs_formatted']} UZS в долларах:</b>\n\n"
        f"🏛 <b>По курсу ЦБ РУз:</b> <code>${res['cbu_usd']:,.2f}</code>\n"
        f"🔴 <b>Купить в банке (продажа):</b> <code>${res['bank_usd']:,.2f}</code>\n\n"
        f"<i>(Курс лучшей продажи: {res['best_sell_rate']:,.0f} UZS за $1)</i>".replace(",", " ")
    )
    await callback.message.reply(text, parse_mode="HTML")
    await callback.answer()

@router.message(CurrencyStates.waiting_usd_amount)
async def handle_input_usd(message: Message, state: FSMContext):
    clean = re.sub(r"[^\d.,]", "", message.text).replace(",", ".")
    try:
        amount = float(clean)
        res = convert_usd_to_uzs(amount)
        text = (
            f"💵 <b>${amount:,.2f} в узбекских сумах:</b>\n\n"
            f"🏛 <b>По курсу ЦБ РУз:</b> <code>{res['cbu_total_formatted']} UZS</code>\n"
            f"🟢 <b>В лучшем банке (покупка):</b> <code>{res['bank_total_formatted']} UZS</code>\n\n"
            f"<i>(Курс лучшей покупки: {res['best_buy_rate']:,.0f} UZS за $1)</i>".replace(",", " ")
        )
        await state.clear()
        await message.answer(text, reply_markup=get_currency_menu_keyboard(), parse_mode="HTML")
    except ValueError:
        await message.answer("⚠️ Введите число (например: <code>100</code> или <code>250.5</code>):", parse_mode="HTML")

@router.message(CurrencyStates.waiting_uzs_amount)
async def handle_input_uzs(message: Message, state: FSMContext):
    clean = re.sub(r"[^\d.,]", "", message.text).replace(",", ".")
    try:
        amount = float(clean)
        res = convert_uzs_to_usd(amount)
        text = (
            f"🇺🇿 <b>{res['amount_uzs_formatted']} UZS в долларах:</b>\n\n"
            f"🏛 <b>По курсу ЦБ РУз:</b> <code>${res['cbu_usd']:,.2f}</code>\n"
            f"🔴 <b>Купить в банке (продажа):</b> <code>${res['bank_usd']:,.2f}</code>\n\n"
            f"<i>(Курс лучшей продажи: {res['best_sell_rate']:,.0f} UZS за $1)</i>".replace(",", " ")
        )
        await state.clear()
        await message.answer(text, reply_markup=get_currency_menu_keyboard(), parse_mode="HTML")
    except ValueError:
        await message.answer("⚠️ Введите сумму сумов числом (например: <code>1000000</code>):", parse_mode="HTML")

# Автоматический парсинг чисел, когда пользователь в режиме валютчика
@router.message(F.text, IsCurrencyMode())
async def handle_auto_currency_input(message: Message):
    txt = message.text.lower().strip()
    if txt.startswith("/") or txt in [
        "📊 курсы в банках (инфографика)", "🔄 обновить курс",
        "🇺🇸 usd ➔ 🇺🇿 uzs", "🇺🇿 uzs ➔ 🇺🇸 usd", "🔙 главное меню",
        "🥗 афзал нутрициолог", "🌐 афзал переводчик", "💵 афзал валютчик", "ℹ️ о боте"
    ]:
        return

    is_usd = any(s in txt for s in ["$", "usd", "дол"])
    clean = re.sub(r"[^\d.,]", "", txt).replace(",", ".")

    try:
        val = float(clean)
        if val <= 0:
            return

        if is_usd or val <= 10000:
            res = convert_usd_to_uzs(val)
            text = (
                f"💵 <b>Расчет для ${val:,.2f}:</b>\n\n"
                f"🏛 <b>По курсу ЦБ РУз:</b> <code>{res['cbu_total_formatted']} UZS</code>\n"
                f"🟢 <b>В банке (сдать USD):</b> <code>{res['bank_total_formatted']} UZS</code>"
            )
        else:
            res = convert_uzs_to_usd(val)
            text = (
                f"🇺🇿 <b>Расчет для {res['amount_uzs_formatted']} UZS:</b>\n\n"
                f"🏛 <b>По курсу ЦБ РУз:</b> <code>${res['cbu_usd']:,.2f}</code>\n"
                f"🔴 <b>Купить в банке (USD):</b> <code>${res['bank_usd']:,.2f}</code>"
            )

        await message.answer(text, parse_mode="HTML")
    except ValueError:
        pass

