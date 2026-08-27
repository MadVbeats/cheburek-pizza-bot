import os

from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
PROXY_URL = os.getenv("PROXY_URL", "")
API_BASE_URL = os.getenv("API_BASE_URL", "")

IIKO_API_URL = os.getenv("IIKO_API_URL", "https://api-ru.iiko.services")
IIKO_API_LOGIN = os.getenv("IIKO_API_LOGIN", "")
IIKO_ORGANIZATION_ID = os.getenv("IIKO_ORGANIZATION_ID", "")
IIKO_TERMINAL_GROUP_ID = os.getenv("IIKO_TERMINAL_GROUP_ID", "")

# Mini App
WEBAPP_URL = os.getenv("WEBAPP_URL", "")  # https://your-domain.com
WEBAPP_HOST = os.getenv("WEBAPP_HOST", "0.0.0.0")
WEBAPP_PORT = int(os.getenv("WEBAPP_PORT", "8000"))
