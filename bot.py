import asyncio
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

import config
from handlers.user import router


async def main():
    log_file = Path(__file__).parent / "bot.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            RotatingFileHandler(log_file, maxBytes=1_000_000, backupCount=3, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )
    if not config.BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN не задан. Заполните файл .env")
    if not config.ADMIN_ID:
        logging.warning("ADMIN_ID не задан — предзаказы не будут отправляться")
    if config.WEBAPP_URL:
        logging.info("Mini App URL: %s", config.WEBAPP_URL)
    else:
        logging.warning("WEBAPP_URL не задан — кнопка Mini App не появится. Задайте URL после деплоя webapp")

    session_kwargs = {}
    if config.PROXY_URL:
        session_kwargs["proxy"] = config.PROXY_URL
    session = AiohttpSession(**session_kwargs)
    if config.API_BASE_URL:
        session.api = TelegramAPIServer.from_base(config.API_BASE_URL.rstrip("/"))
    bot = Bot(
        token=config.BOT_TOKEN,
        session=session,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
