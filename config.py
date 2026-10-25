import os

BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# Твой ID (главный админ)
admin_list = [1058638017]

# --- ВТОРОЙ АДМИН ---
# Впиши сюда ID второго админа (вместо 987654321)
# Если админов несколько, пиши через запятую: [1058638017, 111111111, 222222222]
admin_list.append(987654321) 

# Добавляем админов из переменных окружения BotHost (если они там заданы)
env_admins = os.getenv("ADMIN_IDS", "")
if env_admins:
    for x in env_admins.split(","):
        if x.strip().isdigit():
            admin_list.append(int(x.strip()))

# Убираем дубликаты ID, чтобы не было ошибок
ADMIN_IDS = list(set(admin_list))

# ID рабочего чата (замени на свой, если еще не сделал)
WORK_CHAT_ID = -1001234567890 

DARKSTORE = os.getenv("DARKSTORE", "Ozon Fresh Даркстор Подольск Октябрьский")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN не задан")
