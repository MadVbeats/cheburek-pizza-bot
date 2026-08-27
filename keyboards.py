from aiogram.types import InlineKeyboardButton, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

import config
from menu_data import CATEGORIES, MENU


def main_menu_kb():
    kb = ReplyKeyboardBuilder()
    kb.button(text="🍽 Меню")
    kb.button(text="🛒 Корзина")
    kb.button(text="✅ Оформить заказ")
    kb.button(text="ℹ️ Инфо")
    kb.adjust(2, 2)
    return kb.as_markup(resize_keyboard=True)


def categories_kb():
    kb = InlineKeyboardBuilder()
    for ci, cat in enumerate(CATEGORIES):
        kb.row(InlineKeyboardButton(text=cat, callback_data=f"cat:{ci}"))
    return kb.as_markup()


def items_kb(ci: int):
    kb = InlineKeyboardBuilder()
    for ii, item in enumerate(MENU[CATEGORIES[ci]]):
        label = f"{item['name']} · {item['price']} ₽"
        kb.row(InlineKeyboardButton(text=label, callback_data=f"item:{ci}:{ii}"))
    kb.row(InlineKeyboardButton(text="◀️ Категории", callback_data="cats"))
    return kb.as_markup()


def item_card_kb(ci: int, ii: int):
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="➕ Добавить в корзину", callback_data=f"add:{ci}:{ii}")
    )
    kb.row(InlineKeyboardButton(text=f"◀️ {CATEGORIES[ci]}", callback_data=f"cat:{ci}"))
    kb.row(InlineKeyboardButton(text="🗂 Категории", callback_data="cats"))
    kb.row(InlineKeyboardButton(text="🛒 Корзина", callback_data="cart"))
    return kb.as_markup()


def cart_kb(lines: list[dict]):
    kb = InlineKeyboardBuilder()
    for line in lines:
        label = f"{line['qty']} шт · {line['name']}"
        kb.row(
            InlineKeyboardButton(text="➖", callback_data=f"dec:{line['ci']}:{line['ii']}"),
            InlineKeyboardButton(text=label, callback_data="noop"),
            InlineKeyboardButton(text="➕", callback_data=f"inc:{line['ci']}:{line['ii']}"),
        )
    kb.row(InlineKeyboardButton(text="🧹 Очистить", callback_data="clear"))
    kb.row(
        InlineKeyboardButton(text="✅ Оформить заказ", callback_data="checkout"),
        InlineKeyboardButton(text="🔄 Обновить", callback_data="cart"),
    )
    return kb.as_markup()


def method_kb():
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="🚶 Самовывоз", callback_data="m:pickup"),
        InlineKeyboardButton(text="🚚 Доставка", callback_data="m:delivery"),
    )
    return kb.as_markup()


def confirm_kb():
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="✅ Подтвердить", callback_data="confirm"),
        InlineKeyboardButton(text="❌ Отменить", callback_data="cancel"),
    )
    return kb.as_markup()


def webapp_kb():
    """Инлайн-клавиатура с кнопкой Mini App, если WEBAPP_URL задан."""
    if not config.WEBAPP_URL:
        return None
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="🥟 Открыть приложение", web_app=WebAppInfo(url=config.WEBAPP_URL)))
    kb.row(InlineKeyboardButton(text="🍽 Меню (кнопками)", callback_data="cats"))
    return kb.as_markup()


def main_menu_with_webapp():
    """Reply-кнопка с WebApp для быстрого доступа."""
    kb = ReplyKeyboardBuilder()
    if config.WEBAPP_URL:
        kb.button(text="🥟 Открыть приложение", web_app=WebAppInfo(url=config.WEBAPP_URL))
    kb.button(text="🍽 Меню")
    kb.button(text="🛒 Корзина")
    kb.button(text="✅ Оформить заказ")
    kb.button(text="ℹ️ Инфо")
    kb.adjust(2, 2)
    return kb.as_markup(resize_keyboard=True)
