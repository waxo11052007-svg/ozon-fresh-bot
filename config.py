import os

BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# Твой ID вписан прямо здесь, а если в BotHost заданы другие, они добавятся к твоему
env_admins = os.getenv("ADMIN_IDS", "")
admin_list = [1058638017]  # Твой ID
if env_admins:
    for x in env_admins.split(","):
        if x.strip().isdigit():
            admin_list.append(int(x.strip()))

ADMIN_IDS = list(set(admin_list))
DARKSTORE = os.getenv("DARKSTORE", "Ozon Fresh Даркстор Подольск Октябрьский")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN не задан")
