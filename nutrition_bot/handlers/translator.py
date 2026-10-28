import html
import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Filter
from aiogram.fsm.context import FSMContext

from ..database import get_user_mode, get_translator_settings, set_translator_settings
from ..translator_service import translate_text_fast, translate_image_ocr, LANGUAGES, STYLES
from ..keyboards import (
    get_translator_menu_keyboard,
    get_languages_inline_keyboard,
    get_styles_inline_keyboard
)

logger = logging.getLogger(__name__)

router = Router()

class IsTranslatorMode(Filter):
    async def __call__(self, message: Message) -> bool:
        mode = await get_user_mode(message.from_user.id)
        return mode == "translator"

@router.message(F.text == "🌐 Выбрать язык", IsTranslatorMode())
async def btn_choose_lang(message: Message):
    settings = await get_translator_settings(message.from_user.id)
    cur_lang = LANGUAGES.get(settings["target_lang"], settings["target_lang"])
    await message.answer(
        f"🌐 <b>Текущий язык перевода:</b> <b>{cur_lang}</b>\n\n"
        "Выберите новый целевой язык из списка ниже:",
        reply_markup=get_languages_inline_keyboard(),
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("set_lang:"))
async def callback_set_lang(callback: CallbackQuery):
    lang_code = callback.data.split(":")[1]
    await set_translator_settings(callback.from_user.id, target_lang=lang_code)
    lang_name = LANGUAGES.get(lang_code, lang_code)
    await callback.message.edit_text(
        f"✅ Язык перевода изменен на: <b>{lang_name}</b>!\n\n"
        "Теперь отправьте любой текст или фото для перевода.",
        parse_mode="HTML"
    )
    await callback.answer()

@router.message(F.text == "🎭 Стиль перевода", IsTranslatorMode())
async def btn_choose_style(message: Message):
    settings = await get_translator_settings(message.from_user.id)
    cur_style = STYLES.get(settings["style"], settings["style"])
    await message.answer(
        f"🎭 <b>Текущий стиль:</b> <b>{cur_style}</b>\n\n"
        "Выберите желаемый тон текста:",
        reply_markup=get_styles_inline_keyboard(),
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("set_style:"))
async def callback_set_style(callback: CallbackQuery):
    style_code = callback.data.split(":")[1]
    await set_translator_settings(callback.from_user.id, style=style_code)
    style_name = STYLES.get(style_code, style_code)
    await callback.message.edit_text(
        f"✅ Стиль перевода изменен на: <b>{style_name}</b>!\n\n"
        "Отправьте текст для стилизованного перевода.",
        parse_mode="HTML"
    )
    await callback.answer()

@router.message(F.text == "📸 Перевод по фото", IsTranslatorMode())
async def btn_prompt_photo_translate(message: Message):
    await message.answer(
        "📸 <b>Пришлите фото с текстом!</b>\n\n"
        "ИИ распознает надписи (вывески, документы, меню, этикетки) и мгновенно переведет их на ваш язык.",
        parse_mode="HTML"
    )

from .meals import select_optimal_photo

@router.message(F.photo, IsTranslatorMode())
async def handle_translate_photo(message: Message):
    status_msg = await message.answer("🔍 <i>Распознаю текст на фото и перевожу...</i>", parse_mode="HTML")
    try:
        photo = select_optimal_photo(message.photo)
        file_io = await message.bot.download(photo)
        if hasattr(file_io, "getvalue"):
            image_bytes = file_io.getvalue()
        else:
            file_io.seek(0)
            image_bytes = file_io.read()

        settings = await get_translator_settings(message.from_user.id)
        target_lang = settings["target_lang"]
        style = settings["style"]

        res = await translate_image_ocr(image_bytes, target_lang=target_lang, style=style)

        if not res.get("has_text", False):
            await status_msg.edit_text("ℹ️ <b>На этом изображении не обнаружен читаемый текст.</b>", parse_mode="HTML")
            return

        orig = html.escape(res.get("original_text", ""))
        trans = html.escape(res.get("translated_text", ""))
        lang_name = LANGUAGES.get(target_lang, target_lang)

        response_text = (
            f"🌐 <b>Перевод с фото ({lang_name}):</b>\n\n"
            f"<b>Перевод:</b>\n{trans}\n\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📝 <b>Исходный текст:</b>\n<i>{orig}</i>"
        )
        await status_msg.edit_text(response_text, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Ошибка перевода фото: {e}")
        await status_msg.edit_text(f"❌ Ошибка перевода: <code>{html.escape(str(e))}</code>", parse_mode="HTML")

@router.message(F.text, IsTranslatorMode())
async def handle_translate_text(message: Message):
    txt = message.text.strip()
    if txt.startswith("/") or txt in [
        "🌐 выбрать язык", "🎭 стиль перевода", "📸 перевод по фото", "🔙 главное меню",
        "🥗 афзал нутрициолог", "🌐 афзал переводчик", "💵 афзал валютчик", "ℹ️ о боте"
    ]:
        return

    settings = await get_translator_settings(message.from_user.id)
    target_lang = settings["target_lang"]
    style = settings["style"]

    try:
        res = await translate_text_fast(txt, target_lang=target_lang, style=style)
        trans_safe = html.escape(res["translated_text"])
        target_name = LANGUAGES.get(target_lang, target_lang)

        reply_text = (
            f"🌐 <b>Перевод ({target_name}):</b>\n\n"
            f"{trans_safe}"
        )
        await message.reply(reply_text, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Ошибка перевода текста: {e}")
        await message.reply(f"❌ Ошибка перевода: <code>{html.escape(str(e))}</code>", parse_mode="HTML")

