import logging
import re

from aiogram import Bot, F, Router
from aiogram.filters import CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

import config
from iiko_client import IikoError, client as iiko
from keyboards import (
    cart_kb,
    categories_kb,
    confirm_kb,
    item_card_kb,
    items_kb,
    main_menu_kb,
    main_menu_with_webapp,
    method_kb,
    webapp_kb,
)
from menu_data import CATEGORIES, get_item
from storage import (
    add_item,
    cart_lines,
    cart_total,
    change_qty,
    clear_cart,
    next_order_id,
)

router = Router()
logger = logging.getLogger(__name__)

PHONE_RE = re.compile(r"^\+?\d[\d\s\-()]{8,18}$")

INFO_TEXT = (
    "📍 <b>Чебурек и Пицца</b>\n"
    "ул. Ленина, 1\n\n"
    "🕘 Ежедневно 10:00–22:00\n"
    "📞 +7 900 000-00-00\n\n"
    "🥟 Готовим чебуреки и пиццу с любовью!"
)

ADDRESS_TEXT = "Самовывоз по адресу: ул. Ленина, 1 (🕘 10:00–22:00)"


class Order(StatesGroup):
    name = State()
    phone = State()
    method = State()
    address = State()
    confirm = State()


def categories_view() -> tuple[str, object]:
    return "<b>🍽 Меню</b>\nВыберите категорию:", categories_kb()


def category_view(ci: int) -> tuple[str, object]:
    return f"<b>{CATEGORIES[ci]}</b>\nНажмите на позицию:", items_kb(ci)


def item_view(ci: int, ii: int) -> tuple[str, object]:
    _, item = get_item(ci, ii)
    parts = [f"<b>{item['name']}</b>"]
    if desc := item.get("desc"):
        parts.append(desc)
    parts.append(f"Цена: <b>{item['price']} ₽</b>")
    return "\n\n".join(parts), item_card_kb(ci, ii)


def cart_view(user_id: int) -> tuple[str, object | None]:
    lines = cart_lines(user_id)
    if not lines:
        return "🛒 Корзина пуста.\nЗагляните в 🍽 Меню!", None
    body = "\n".join(f"{l['qty']} × {l['name']} — {l['sum']} ₽" for l in lines)
    text = (
        f"<b>🛒 Ваша корзина</b>\n\n{body}\n\n💰 Итого: <b>{cart_total(user_id)} ₽</b>"
    )
    return text, cart_kb(lines)


async def interrupted(state: FSMContext) -> str:
    was_active = await state.get_state() is not None
    await state.clear()
    return "⛔️ Оформление заказа прервано.\n\n" if was_active else ""


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    # Клавиатура с WebApp если настроен WEBAPP_URL
    reply_kb = main_menu_with_webapp() if config.WEBAPP_URL else main_menu_kb()
    inline_kb = webapp_kb()
    text = "Добро пожаловать в «Чебурек и Пицца»! 🥟🍕\n\n"
    if config.WEBAPP_URL:
        text += "Нажмите 🥟 Открыть приложение — меню как у Яндекс Еды прямо в Телеге!\nИли выберите раздел:"
    else:
        text += "Выберите раздел:"
    await message.answer(text, reply_markup=reply_kb)
    if inline_kb:
        await message.answer("Быстрый доступ:", reply_markup=inline_kb)


@router.message(F.text == "ℹ️ Инфо")
async def info_handler(message: Message, state: FSMContext):
    prefix = await interrupted(state)
    await message.answer(prefix + INFO_TEXT)


@router.message(F.text == "🍽 Меню")
async def menu_handler(message: Message, state: FSMContext):
    prefix = await interrupted(state)
    text, kb = categories_view()
    await message.answer(prefix + text, reply_markup=kb)


@router.message(F.text == "🛒 Корзина")
async def cart_handler(message: Message, state: FSMContext):
    prefix = await interrupted(state)
    text, kb = cart_view(message.from_user.id)
    await message.answer(prefix + text, reply_markup=kb)


@router.message(F.text == "✅ Оформить заказ")
async def checkout_handler(message: Message, state: FSMContext):
    await state.clear()
    if not cart_lines(message.from_user.id):
        await message.answer("Корзина пуста — сначала выберите что-нибудь в 🍽 Меню.")
        return
    await state.set_state(Order.name)
    await message.answer("Как вас зовут?")


@router.callback_query(F.data == "noop")
async def noop_handler(cb: CallbackQuery):
    await cb.answer()


@router.callback_query(F.data == "cats")
async def cb_cats(cb: CallbackQuery):
    text, kb = categories_view()
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()


@router.callback_query(F.data.startswith("cat:"))
async def cb_cat(cb: CallbackQuery):
    ci = int(cb.data.split(":")[1])
    text, kb = category_view(ci)
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()


@router.callback_query(F.data.startswith("item:"))
async def cb_item(cb: CallbackQuery):
    _, ci, ii = cb.data.split(":")
    text, kb = item_view(int(ci), int(ii))
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()


@router.callback_query(F.data.startswith("add:"))
async def cb_add(cb: CallbackQuery):
    _, ci, ii = cb.data.split(":")
    add_item(cb.from_user.id, int(ci), int(ii))
    await cb.answer("Добавлено в корзину 🛒")


async def render_cart_message(message: Message, user_id: int):
    text, kb = cart_view(user_id)
    if kb is None:
        await message.edit_text(text)
        await message.edit_reply_markup(reply_markup=None)
    else:
        await message.edit_text(text, reply_markup=kb)


@router.callback_query(F.data.startswith(("inc:", "dec:")))
async def cb_qty(cb: CallbackQuery):
    action, ci, ii = cb.data.split(":")
    change_qty(cb.from_user.id, int(ci), int(ii), 1 if action == "inc" else -1)
    await render_cart_message(cb.message, cb.from_user.id)
    await cb.answer()


@router.callback_query(F.data == "clear")
async def cb_clear(cb: CallbackQuery):
    clear_cart(cb.from_user.id)
    await render_cart_message(cb.message, cb.from_user.id)
    await cb.answer("Корзина очищена")


@router.callback_query(F.data == "cart")
async def cb_cart(cb: CallbackQuery):
    await render_cart_message(cb.message, cb.from_user.id)
    await cb.answer()


@router.callback_query(F.data == "checkout")
async def cb_checkout(cb: CallbackQuery, state: FSMContext):
    if not cart_lines(cb.from_user.id):
        await cb.answer("Корзина пуста", show_alert=True)
        return
    await state.set_state(Order.name)
    await cb.message.answer("Как вас зовут?")
    await cb.answer()


async def send_summary(message: Message, user_id: int, state: FSMContext):
    data = await state.get_data()
    lines = cart_lines(user_id)
    delivery = (
        "🚶 Самовывоз"
        if data["method"] == "pickup"
        else f"🚚 Доставка, адрес: {data['address']}"
    )
    body = "\n".join(f"• {l['qty']} × {l['name']} — {l['sum']} ₽" for l in lines)
    text = (
        "<b>Проверьте заказ:</b>\n\n"
        f"👤 {data['name']}\n"
        f"📞 {data['phone']}\n"
        f"{delivery}\n\n"
        f"{body}\n\n"
        f"💰 Итого: <b>{cart_total(user_id)} ₽</b>"
    )
    await message.answer(text, reply_markup=confirm_kb())


@router.message(StateFilter(Order.name))
async def st_name(message: Message, state: FSMContext):
    name = (message.text or "").strip()
    if len(name) < 2:
        await message.answer("Введите имя (минимум 2 символа):")
        return
    await state.update_data(name=name)
    await state.set_state(Order.phone)
    await message.answer(f"Приятно познакомиться, {name}! Отправьте номер телефона:")


@router.message(StateFilter(Order.phone))
async def st_phone(message: Message, state: FSMContext):
    raw = (message.text or "").strip()
    if not PHONE_RE.match(raw):
        await message.answer("Похоже, это не телефон. Пример: +7 900 123-45-67")
        return
    await state.update_data(phone=raw)
    await state.set_state(Order.method)
    await message.answer("Как удобно получить заказ?", reply_markup=method_kb())


@router.callback_query(StateFilter(Order.method), F.data.startswith("m:"))
async def cb_method(cb: CallbackQuery, state: FSMContext):
    method = cb.data.split(":")[1]
    await state.update_data(method=method)
    if method == "pickup":
        await state.set_state(Order.confirm)
        await cb.message.answer(ADDRESS_TEXT)
        await send_summary(cb.message, cb.from_user.id, state)
    else:
        await state.set_state(Order.address)
        await cb.message.answer("Введите адрес доставки (улица, дом, квартира):")
    await cb.answer()


@router.message(StateFilter(Order.address))
async def st_address(message: Message, state: FSMContext):
    address = (message.text or "").strip()
    if len(address) < 5:
        await message.answer("Укажите адрес подробнее:")
        return
    await state.update_data(address=address)
    await state.set_state(Order.confirm)
    await send_summary(message, message.from_user.id, state)


def build_order_text(order_id: int, data: dict, lines: list[dict], total: int, username: str | None, user_id: int) -> str:
    delivery = (
        "Самовывоз"
        if data["method"] == "pickup"
        else f"Доставка, адрес: {data['address']}"
    )
    digits = re.sub(r"[^\d+]", "", data["phone"])
    contact = f"@{username}" if username else f"id{user_id}"
    body = "\n".join(f"  • {l['qty']} × {l['name']} — {l['sum']} ₽" for l in lines)
    return (
        f"<b>🆕 Предзаказ №{order_id}</b>\n\n"
        f"👤 Имя: {data['name']}\n"
        f'📞 Телефон: <a href="tel:{digits}">{data["phone"]}</a>\n'
        f"📦 Получение: {delivery}\n\n"
        f"🧾 Состав:\n{body}\n\n"
        f"💰 Итого: <b>{total} ₽</b>\n"
        f"💬 Telegram: {contact}"
    )


def build_iiko_payload(order_id: int, data: dict, lines: list[dict]) -> dict:
    missing = [
        l["name"]
        for l in lines
        if not get_item(l["ci"], l["ii"])[1].get("iiko_id")
    ]
    if missing:
        raise IikoError(
            "в menu.json не заданы iiko_id для позиций: " + ", ".join(missing)
        )
    items = []
    for l in lines:
        item = get_item(l["ci"], l["ii"])[1]
        items.append(
            {
                "productId": item["iiko_id"],
                "type": "Product",
                "status": "Added",
                "amount": float(l["qty"]),
                "price": float(item["price"]),
            }
        )
    digits = re.sub(r"[^\d+]", "", data["phone"])
    delivery_line = (
        "Самовывоз"
        if data["method"] == "pickup"
        else f"ДОСТАВКА по адресу: {data['address']}"
    )
    comment = f"Предзаказ из Telegram-бота №{order_id}. {delivery_line}"
    return {
        "organizationId": config.IIKO_ORGANIZATION_ID,
        "terminalGroupId": config.IIKO_TERMINAL_GROUP_ID or None,
        "createOrderSettings": {"transportFrontendType": "Web"},
        "order": {
            "externalNumber": str(order_id),
            "phone": digits,
            "orderServiceType": "DeliveryPickUp",
            "customer": {
                "name": data["name"],
                "comment": comment,
            },
            "comment": comment,
            "payments": [],
            "items": items,
        },
    }


@router.callback_query(StateFilter(Order.confirm), F.data == "confirm")
async def cb_confirm(cb: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    user_id = cb.from_user.id
    lines = cart_lines(user_id)
    order_id = next_order_id()
    text = build_order_text(
        order_id,
        data,
        lines,
        cart_total(user_id),
        cb.from_user.username,
        user_id,
    )
    iiko_note = ""
    if config.IIKO_API_LOGIN:
        try:
            payload = build_iiko_payload(order_id, data, lines)
            await iiko.create_delivery_order(payload)
            iiko_note = "\n🟢 Заказ передан в iiko"
            logger.info("Заказ №%s передан в iiko", order_id)
        except Exception as e:
            logger.exception("Ошибка передачи заказа №%s в iiko", order_id)
            iiko_note = f"\n🔴 НЕ передан в iiko: {e}"
        text += iiko_note
    try:
        await bot.send_message(config.ADMIN_ID, text)
    except Exception:
        logger.exception("Не удалось отправить предзаказ админу")
        await state.clear()
        await cb.message.edit_text(
            "⚠️ Не удалось передать заказ. Позвоните нам: +7 900 000-00-00"
        )
        await cb.answer()
        return
    clear_cart(user_id)
    await state.clear()
    await cb.message.edit_text(
        f"✅ Предзаказ №{order_id} принят!\nМы позвоним вам для подтверждения. Спасибо! 🥟🍕"
    )
    await cb.answer()


@router.callback_query(F.data == "cancel")
async def cb_cancel(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await cb.message.edit_text("❌ Заказ отменён. Корзина сохранена — можно оформить позже.")
    await cb.answer()


@router.message(F.text == "🥟 Открыть приложение")
async def webapp_fallback(message: Message, state: FSMContext):
    prefix = await interrupted(state)
    if config.WEBAPP_URL:
        kb = webapp_kb()
        await message.answer(prefix + "Откройте приложение по кнопке ниже 👇", reply_markup=kb)
    else:
        await message.answer(prefix + "Mini App ещё не настроен. Задайте WEBAPP_URL в .env")


@router.message()
async def fallback_handler(message: Message):
    kb = main_menu_with_webapp() if config.WEBAPP_URL else main_menu_kb()
    await message.answer("Используйте кнопки ниже 👇", reply_markup=kb)
