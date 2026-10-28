from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    WebAppInfo
)
from typing import Dict, Any
from .config import get_web_app_url

def get_root_menu_keyboard() -> ReplyKeyboardMarkup:
    """Главное меню верхнего уровня с 3 основными направлениями и кнопкой Web App."""
    url = get_web_app_url()
    
    rows = [
        [
            KeyboardButton(text="🥗 Афзал Нутрициолог"),
            KeyboardButton(text="🌐 Афзал Переводчик")
        ],
        [
            KeyboardButton(text="💵 Афзал Валютчик"),
            KeyboardButton(text="ℹ️ О боте")
        ]
    ]

    # Если настроен HTTPS, добавляем прямую нативную кнопку Telegram WebApp
    if url.startswith("https://"):
        rows.insert(0, [
            KeyboardButton(text="📱 Открыть Веб-приложение", web_app=WebAppInfo(url=url))
        ])
    else:
        rows.insert(0, [
            KeyboardButton(text="📱 Веб-интерфейс (Сайт)")
        ])

    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)

def get_web_app_inline_keyboard() -> InlineKeyboardMarkup:
    """Инлайн-кнопка для моментального открытия веб-интерфейса."""
    url = get_web_app_url()
    if url.startswith("https://"):
        btn = InlineKeyboardButton(text="🚀 Запустить Веб-интерфейс", web_app=WebAppInfo(url=url))
    else:
        btn = InlineKeyboardButton(text="🌐 Открыть в браузере", url=url)
    return InlineKeyboardMarkup(inline_keyboard=[[btn]])

def get_nutrition_menu_keyboard() -> ReplyKeyboardMarkup:
    """Меню раздела нутрициолога."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="📸 Распознать по фото"),
                KeyboardButton(text="✍️ Описать текстом")
            ],
            [
                KeyboardButton(text="📊 Дневник и статистика"),
                KeyboardButton(text="🎯 Моя норма КБЖУ")
            ],
            [
                KeyboardButton(text="🗑 Удалить последний прием"),
                KeyboardButton(text="🔙 Главное меню")
            ]
        ],
        resize_keyboard=True
    )

def get_meal_confirm_keyboard(draft_id: str) -> InlineKeyboardMarkup:
    """Интерактивные кнопки точной подстройки и записи блюда."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="➕ Порция (+25%)", callback_data=f"adj:plus:{draft_id}"),
                InlineKeyboardButton(text="➖ Порция (-25%)", callback_data=f"adj:minus:{draft_id}")
            ],
            [
                InlineKeyboardButton(text="🍳 Без масла (-100 ккал)", callback_data=f"adj:no_oil:{draft_id}"),
                InlineKeyboardButton(text="🥖 +Хлеб (+150 ккал)", callback_data=f"adj:bread:{draft_id}")
            ],
            [
                InlineKeyboardButton(text="✅ Записать в дневник", callback_data=f"save_meal:{draft_id}"),
                InlineKeyboardButton(text="❌ Отмена", callback_data=f"cancel_meal:{draft_id}")
            ]
        ]
    )

def get_translator_menu_keyboard() -> ReplyKeyboardMarkup:
    """Меню переводчика."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="🌐 Выбрать язык"),
                KeyboardButton(text="🎭 Стиль перевода")
            ],
            [
                KeyboardButton(text="📸 Перевод по фото"),
                KeyboardButton(text="🔙 Главное меню")
            ]
        ],
        resize_keyboard=True
    )

def get_languages_inline_keyboard() -> InlineKeyboardMarkup:
    """Инлайн-выбор популярных языков перевода."""
    buttons = [
        [
            InlineKeyboardButton(text="🇷🇺 Русский", callback_data="set_lang:ru"),
            InlineKeyboardButton(text="🇺🇸 English", callback_data="set_lang:en")
        ],
        [
            InlineKeyboardButton(text="🇺🇿 O'zbekcha", callback_data="set_lang:uz"),
            InlineKeyboardButton(text="🇪🇸 Español", callback_data="set_lang:es")
        ],
        [
            InlineKeyboardButton(text="🇩🇪 Deutsch", callback_data="set_lang:de"),
            InlineKeyboardButton(text="🇫🇷 Français", callback_data="set_lang:fr")
        ],
        [
            InlineKeyboardButton(text="🇹🇷 Türkçe", callback_data="set_lang:tr"),
            InlineKeyboardButton(text="🇨🇳 中文 (Китайский)", callback_data="set_lang:zh")
        ],
        [
            InlineKeyboardButton(text="🇸🇦 العربية", callback_data="set_lang:ar"),
            InlineKeyboardButton(text="🇯🇵 日本語 (Японский)", callback_data="set_lang:ja")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_styles_inline_keyboard() -> InlineKeyboardMarkup:
    """Инлайн-выбор стиля перевода."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🔹 Обычный / Нейтральный", callback_data="set_style:general")
            ],
            [
                InlineKeyboardButton(text="💼 Деловой / Официальный", callback_data="set_style:business")
            ],
            [
                InlineKeyboardButton(text="☕️ Разговорный / Дружеский", callback_data="set_style:casual")
            ],
            [
                InlineKeyboardButton(text="📚 Художественный", callback_data="set_style:literary")
            ]
        ]
    )

def get_currency_menu_keyboard() -> ReplyKeyboardMarkup:
    """Меню валютчика."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="📊 Курсы в банках (Инфографика)"),
                KeyboardButton(text="🔄 Обновить курс")
            ],
            [
                KeyboardButton(text="🇺🇸 USD ➔ 🇺🇿 UZS"),
                KeyboardButton(text="🇺🇿 UZS ➔ 🇺🇸 USD")
            ],
            [
                KeyboardButton(text="🔙 Главное меню")
            ]
        ],
        resize_keyboard=True
    )

def get_usd_quick_keyboard() -> InlineKeyboardMarkup:
    """Быстрые суммы USD."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="$50", callback_data="calc_usd:50"),
                InlineKeyboardButton(text="$100", callback_data="calc_usd:100"),
                InlineKeyboardButton(text="$200", callback_data="calc_usd:200")
            ],
            [
                InlineKeyboardButton(text="$500", callback_data="calc_usd:500"),
                InlineKeyboardButton(text="$1 000", callback_data="calc_usd:1000"),
                InlineKeyboardButton(text="$2 000", callback_data="calc_usd:2000")
            ]
        ]
    )

def get_uzs_quick_keyboard() -> InlineKeyboardMarkup:
    """Быстрые суммы UZS."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="500 тыс сум", callback_data="calc_uzs:500000"),
                InlineKeyboardButton(text="1 млн сум", callback_data="calc_uzs:1000000")
            ],
            [
                InlineKeyboardButton(text="2 млн сум", callback_data="calc_uzs:2000000"),
                InlineKeyboardButton(text="5 млн сум", callback_data="calc_uzs:5000000")
            ],
            [
                InlineKeyboardButton(text="10 млн сум", callback_data="calc_uzs:10000000"),
                InlineKeyboardButton(text="20 млн сум", callback_data="calc_uzs:20000000")
            ]
        ]
    )

def get_stats_actions_keyboard() -> InlineKeyboardMarkup:
    """Действия в дневнике питания."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🗑 Очистить дневник за сегодня", callback_data="clear_today_diary")
            ]
        ]
    )
