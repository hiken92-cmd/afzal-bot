from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext

from ..database import get_or_create_user, set_user_mode
from ..config import get_web_app_url
from ..keyboards import (
    get_root_menu_keyboard,
    get_nutrition_menu_keyboard,
    get_translator_menu_keyboard,
    get_currency_menu_keyboard,
    get_web_app_inline_keyboard
)

router = Router()

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await get_or_create_user(message.from_user.id, message.from_user.username)
    await set_user_mode(message.from_user.id, "root")
    
    welcome_text = (
        f"👋 <b>Здравствуйте, {message.from_user.first_name}!</b>\n\n"
        "Добро пожаловать в персонального ИИ-помощника Афзала.\n\n"
        "🌟 <b>Выберите нужный раздел в меню или откройте веб-сайт:</b>\n"
        "🥗 <b>Афзал Нутрициолог</b> — счетчик калорий (КБЖУ) по фото, декомпозиция ингредиентов и дневник.\n"
        "🌐 <b>Афзал Переводчик</b> — перевод текстов (0.3с) и фото на все языки мира.\n"
        "💵 <b>Афзал Валютчик</b> — онлайн-курсы валют банков Узбекистана и конвертер.\n\n"
        "📱 <b>Веб-интерфейс:</b> доступен в виде удобного веб-приложения!"
    )
    await message.answer(
        welcome_text,
        reply_markup=get_root_menu_keyboard(),
        parse_mode="HTML"
    )

@router.message(F.text.in_({"📱 Веб-интерфейс (Сайт)", "📱 Открыть Веб-приложение"}))
@router.message(Command("webapp", "app", "web"))
async def btn_open_webapp(message: Message):
    text = (
        "🌐 <b>Веб-интерфейс бота Афзала</b>\n\n"
        "Вам доступен интерактивный веб-сайт с полным функционалом в едином окне:\n"
        "• 🥗 <b>Нутрициолог:</b> камера/галерея, мгновенный расчет КБЖУ и скрытых калорий\n"
        "• 🌐 <b>Переводчик:</b> мгновенный переводчик с выбором тональности и стиля\n"
        "• 💵 <b>Валютчик:</b> живая таблица котировок банков Ташкента и калькулятор сумов\n\n"
        "👇 Нажмите кнопку ниже для запуска веб-интерфейса:"
    )
    await message.answer(text, reply_markup=get_web_app_inline_keyboard(), parse_mode="HTML")

@router.message(F.text == "🔙 Главное меню")
async def btn_back_to_main(message: Message, state: FSMContext):
    await state.clear()
    await set_user_mode(message.from_user.id, "root")
    await message.answer("🏠 Вы вернулись в <b>Главное меню</b>. Выберите раздел:",
                         reply_markup=get_root_menu_keyboard(), parse_mode="HTML")

@router.message(F.text == "🥗 Афзал Нутрициолог")
async def btn_enter_nutrition(message: Message, state: FSMContext):
    await state.clear()
    await set_user_mode(message.from_user.id, "nutrition")
    
    text = (
        "🥗 <b>Раздел «Афзал Нутрициолог» активирован!</b>\n\n"
        "⚡️ <i>Обновленный движок: скорость анализа ~1 сек, точность расчета порций и скрытых калорий до 95%!</i>\n\n"
        "📸 <b>Как пользоваться:</b>\n"
        "1. Просто <b>отправьте фото блюда</b> в этот чат (можно с подписью, например: <i>«съел половину»</i>).\n"
        "2. Или нажмите <b>«✍️ Описать текстом»</b> и перечислите съеденное.\n"
        "3. После расчета вы сможете скорректировать порцию в один клик и сохранить ее в дневник питания!\n\n"
        "Жду фото вашего приема пищи!"
    )
    await message.answer(text, reply_markup=get_nutrition_menu_keyboard(), parse_mode="HTML")

@router.message(F.text == "🌐 Афзал Переводчик")
async def btn_enter_translator(message: Message, state: FSMContext):
    await state.clear()
    await set_user_mode(message.from_user.id, "translator")
    
    text = (
        "🌐 <b>Раздел «Афзал Переводчик» активирован!</b>\n\n"
        "⚡️ Скорость перевода: <b>0.3 секунды</b>.\n"
        "🌍 Поддержка всех языков мира и фото OCR.\n\n"
        "📝 Просто отправьте текст или фото для перевода!"
    )
    await message.answer(text, reply_markup=get_translator_menu_keyboard(), parse_mode="HTML")

@router.message(F.text == "ℹ️ О боте")
async def btn_about(message: Message):
    about_text = (
        "🤖 <b>О многофункциональном боте Афзала:</b>\n\n"
        "1. 🥗 <b>Афзал Нутрициолог:</b>\n"
        "   • Компьютерное зрение и нейросети для распознавания блюд по фото за 1 секунду.\n"
        "   • Оценка граммовок, раскладка КБЖУ по ингредиентам, учет скрытых калорий и масел.\n"
        "   • Личный дневник питания и расчет нормы по формуле Миффлина-Сан Жеора.\n\n"
        "2. 🌐 <b>Афзал Переводчик:</b>\n"
        "   • Нейросетевой перевод текстов за 0.3с и распознавание текста с фото (OCR).\n\n"
        "3. 💵 <b>Афзал Валютчик:</b>\n"
        "   • Реальные курсы ЦБ РУз и коммерческих банков Узбекистана.\n"
        "   • Инфографика лучших курсов покупки/продажи и удобный конвертер USD ⇄ UZS.\n\n"
        "4. 📱 <b>Веб-интерфейс (Сайт):</b>\n"
        "   • Запуск полноэкранного интерфейса в один клик!"
    )
    await message.answer(about_text, reply_markup=get_root_menu_keyboard(), parse_mode="HTML")

@router.message(Command("help"))
async def cmd_help(message: Message):
    help_text = (
        "📖 <b>Справка по боту:</b>\n\n"
        "• Для подсчета калорий перейдите в <b>«🥗 Афзал Нутрициолог»</b> и пришлите фото или текст блюда.\n"
        "• Для перевода перейдите в <b>«🌐 Афзал Переводчик»</b> и отправьте текст или картинку с текстом.\n"
        "• Для курсов валют откройте <b>«💵 Афзал Валютчик»</b>.\n"
        "• Нажмите <b>«📱 Веб-интерфейс (Сайт)»</b> для запуска приложения в виде сайта.\n\n"
        "Команда /start возвращает вас к выбору режима."
    )
    await message.answer(help_text, parse_mode="HTML")
