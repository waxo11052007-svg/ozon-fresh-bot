import os

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]
DARKSTORE = os.getenv("DARKSTORE", "Ozon Fresh Даркстор Подольск Октябрьский")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN не задан")
