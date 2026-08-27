import hashlib
import hmac
import logging
import re
import time
from pathlib import Path
from urllib.parse import parse_qsl, unquote

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import config
from menu_data import CATEGORIES, MENU, get_item
from storage import next_order_id, cart_total as _unused  # for order ids
from iiko_client import IikoError, client as iiko

logger = logging.getLogger(__name__)

app = FastAPI(title="Чебурек и Пицца Mini App API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

PHONE_RE = re.compile(r"^\+?\d[\d\s\-()]{8,18}$")

# --- Telegram WebApp initData validation ---
def validate_init_data(init_data: str) -> dict:
    """Validate Telegram WebApp initData, return parsed data or raise."""
    if not init_data:
        # Allow empty for local dev without Telegram
        if not config.BOT_TOKEN:
            return {}
        # In production we still allow but log warning - to not block dev
        logger.warning("initData пустой — пропускаем проверку (dev режим)")
        return {}
    try:
        parsed = dict(parse_qsl(init_data, keep_blank_values=True))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"initData parse error: {e}")
    received_hash = parsed.pop("hash", None)
    if not received_hash:
        raise HTTPException(status_code=400, detail="initData без hash")
    # Check auth_date freshness (24h)
    auth_date = parsed.get("auth_date")
    if auth_date:
        try:
            if time.time() - int(auth_date) > 86400:
                raise HTTPException(status_code=400, detail="initData устарел")
        except ValueError:
            pass
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))
    secret_key = hmac.new(b"WebAppData", config.BOT_TOKEN.encode(), hashlib.sha256).digest()
    calc_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    if calc_hash != received_hash:
        raise HTTPException(status_code=403, detail="Неверная подпись initData")
    # parse user JSON if present
    user_data = {}
    if "user" in parsed:
        import json
        try:
            user_data = json.loads(unquote(parsed["user"]))
        except Exception:
            user_data = {}
    return {"raw": parsed, "user": user_data}

# --- Models ---
class CartItem(BaseModel):
    ci: int
    ii: int
    qty: int

class OrderRequest(BaseModel):
    initData: str = ""
    name: str
    phone: str
    method: str  # pickup | delivery
    address: str = ""
    cart: list[CartItem]

def build_order_text(order_id: int, data: dict, lines: list[dict], total: int, username: str | None, user_id: int | None) -> str:
    delivery = "Самовывоз" if data["method"] == "pickup" else f"Доставка, адрес: {data['address']}"
    digits = re.sub(r"[^\d+]", "", data["phone"])
    contact = f"@{username}" if username else (f"id{user_id}" if user_id else "Mini App")
    body = "\n".join(f"  • {l['qty']} × {l['name']} — {l['sum']} ₽" for l in lines)
    return (
        f"<b>🆕 Предзаказ №{order_id} (Mini App)</b>\n\n"
        f"👤 Имя: {data['name']}\n"
        f'📞 Телефон: <a href="tel:{digits}">{data["phone"]}</a>\n'
        f"📦 Получение: {delivery}\n\n"
        f"🧾 Состав:\n{body}\n\n"
        f"💰 Итого: <b>{total} ₽</b>\n"
        f"💬 Telegram: {contact}"
    )

def build_iiko_payload(order_id: int, data: dict, lines: list[dict]) -> dict:
    missing = [l["name"] for l in lines if not get_item(l["ci"], l["ii"])[1].get("iiko_id")]
    if missing:
        raise IikoError("в menu.json не заданы iiko_id для позиций: " + ", ".join(missing))
    items = []
    for l in lines:
        item = get_item(l["ci"], l["ii"])[1]
        items.append({
            "productId": item["iiko_id"],
            "type": "Product",
            "amount": float(l["qty"]),
            "price": float(item["price"]),
        })
    digits = re.sub(r"[^\d+]", "", data["phone"])
    delivery_line = "Самовывоз" if data["method"] == "pickup" else f"ДОСТАВКА по адресу: {data['address']}"
    comment = f"Предзаказ из Mini App №{order_id}. {delivery_line}"
    return {
        "organizationId": config.IIKO_ORGANIZATION_ID,
        "terminalGroupId": config.IIKO_TERMINAL_GROUP_ID or None,
        "createOrderSettings": {"transportFrontendType": "Web"},
        "order": {
            "externalNumber": str(order_id),
            "phone": digits,
            "orderServiceType": "DeliveryPickUp",
            "customer": {"name": data["name"], "comment": comment},
            "comment": comment,
            "payments": [],
            "items": items,
        },
    }

# --- API ---
@app.get("/api/menu")
async def api_menu():
    return {"categories": CATEGORIES, "menu": MENU}

@app.get("/api/health")
async def health():
    return {"ok": True}

@app.post("/api/order")
async def api_order(req: OrderRequest):
    # validate fields
    name = req.name.strip()
    if len(name) < 2:
        raise HTTPException(status_code=400, detail="Имя слишком короткое")
    if not PHONE_RE.match(req.phone.strip()):
        raise HTTPException(status_code=400, detail="Неверный формат телефона")
    if req.method not in ("pickup", "delivery"):
        raise HTTPException(status_code=400, detail="method должен быть pickup/delivery")
    if req.method == "delivery" and len(req.address.strip()) < 5:
        raise HTTPException(status_code=400, detail="Укажите адрес подробнее")
    if not req.cart:
        raise HTTPException(status_code=400, detail="Корзина пуста")

    # validate initData
    tg_data = validate_init_data(req.initData)
    tg_user = tg_data.get("user", {})
    username = tg_user.get("username")
    user_id = tg_user.get("id")

    # build lines
    lines = []
    total = 0
    for c in req.cart:
        try:
            _, item = get_item(c.ci, c.ii)
        except (IndexError, KeyError):
            raise HTTPException(status_code=400, detail=f"Неверная позиция ci:{c.ci} ii:{c.ii}")
        if c.qty <= 0 or c.qty > 99:
            raise HTTPException(status_code=400, detail="qty должен быть 1..99")
        s = item["price"] * c.qty
        total += s
        lines.append({"ci": c.ci, "ii": c.ii, "name": item["name"], "price": item["price"], "qty": c.qty, "sum": s})

    order_id = next_order_id()
    data = {"name": name, "phone": req.phone.strip(), "method": req.method, "address": req.address.strip()}
    text = build_order_text(order_id, data, lines, total, username, user_id)

    # iiko
    iiko_note = ""
    if config.IIKO_API_LOGIN:
        try:
            payload = build_iiko_payload(order_id, data, lines)
            await iiko.create_delivery_order(payload)
            iiko_note = "\n🟢 Заказ передан в iiko"
            logger.info("Заказ №%s передан в iiko", order_id)
        except Exception as e:
            logger.exception("Ошибка iiko №%s", order_id)
            iiko_note = f"\n🔴 НЕ передан в iiko: {e}"
        text += iiko_note

    # send to admin via Bot API
    if not config.ADMIN_ID:
        logger.warning("ADMIN_ID не задан — заказ №%s не отправлен", order_id)
    else:
        from aiogram import Bot
        from aiogram.client.default import DefaultBotProperties
        from aiogram.enums import ParseMode
        from aiogram.client.session.aiohttp import AiohttpSession
        from aiogram.client.telegram import TelegramAPIServer

        session_kwargs = {}
        if config.PROXY_URL:
            session_kwargs["proxy"] = config.PROXY_URL
        session = AiohttpSession(**session_kwargs)
        if config.API_BASE_URL:
            session.api = TelegramAPIServer.from_base(config.API_BASE_URL.rstrip("/"))
        bot = Bot(token=config.BOT_TOKEN, session=session, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
        try:
            await bot.send_message(config.ADMIN_ID, text)
        except Exception:
            logger.exception("Не удалось отправить заказ админу")
            await bot.session.close()
            raise HTTPException(status_code=500, detail="Не удалось отправить заказ админу. Позвоните: +7 900 000-00-00")
        await bot.session.close()

    return {"ok": True, "order_id": order_id, "total": total, "iiko": bool(iiko_note and "🟢" in iiko_note)}

# --- Static frontend ---
WEBAPP_DIR = Path(__file__).parent / "webapp"
WEBAPP_DIR.mkdir(exist_ok=True)

# Mount static files if directory has files (after creation)
if WEBAPP_DIR.exists():
    # Serve assets under /assets etc via StaticFiles, but index.html via root
    try:
        app.mount("/static", StaticFiles(directory=WEBAPP_DIR), name="static")
    except Exception:
        pass

@app.get("/")
async def serve_index():
    index = WEBAPP_DIR / "index.html"
    if index.exists():
        return FileResponse(index)
    return {"message": "Mini App frontend не найден. Положи файлы в webapp/"}

@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    # For SPA routing, serve index.html for non-api paths
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404)
    file_path = WEBAPP_DIR / full_path
    if file_path.is_file():
        return FileResponse(file_path)
    index = WEBAPP_DIR / "index.html"
    if index.exists():
        return FileResponse(index)
    raise HTTPException(status_code=404)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=config.WEBAPP_HOST, port=config.WEBAPP_PORT)
