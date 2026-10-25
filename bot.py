import asyncio
from datetime import date, timedelta, datetime
from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
)
from aiogram.client.default import DefaultBotProperties

from config import BOT_TOKEN, ADMIN_IDS, DARKSTORE
import db

class Reg(StatesGroup):
    name = State()
    phone = State()

class CancelSlot(StatesGroup):
    choosing_slot = State()
    choosing_reason = State()
    detail = State()

class ReportTasks(StatesGroup):
    waiting_for_tasks = State()

class Broadcast(StatesGroup):
    waiting_for_text = State()

class MultiBook(StatesGroup):
    choosing_times = State()

CANCEL_REASONS = [
    ("sick", "🤒 Болезнь"),
    ("family", "👨‍👩‍👧 Семейные обстоятельства"),
    ("transport", "🚌 Проблемы с транспортом"),
    ("study", "🎓 Учёба"),
    ("other_job", "💼 Другая работа"),
    ("no_show", "❌ Не смогу выйти"),
    ("other", "✏️ Другая причина"),
]

def main_kb(is_admin=False):
    kb = [
        [KeyboardButton(text="📅 Свободные слоты")],
        [KeyboardButton(text="🗓 Мои смены"), KeyboardButton(text="❌ Отменить смену")],
        [KeyboardButton(text="✍️ Ввести задания"), KeyboardButton(text="ℹ️ Инфо")],
    ]
    if is_admin:
        kb.append([KeyboardButton(text="🛠 Админ-панель")])
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def admin_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📊 График на сегодня")],
            [KeyboardButton(text="📊 График на завтра")],
            [KeyboardButton(text="📅 График на неделю")],
            [KeyboardButton(text="🏆 Топ курьеров"), KeyboardButton(text="📈 Статистика")],
            [KeyboardButton(text="📢 Сделать рассылку")],
            [KeyboardButton(text="📋 Отчёты по отменам")],
            [KeyboardButton(text="🔙 Назад")],
        ],
        resize_keyboard=True
    )

def top_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🏆 Топ за сегодня"), KeyboardButton(text="🏆 Топ за неделю")],
            [KeyboardButton(text="🏆 Топ за месяц")],
            [KeyboardButton(text="🔙 Назад в админку")],
        ],
        resize_keyboard=True
    )

def phone_kb():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Отправить номер телефона", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )

# --- НОВЫЕ КНОПКИ ДЛЯ МУЛЬТИВЫБОРА ---

def multi_dates_kb(grouped, selected_dates):
    """Показывает даты с галочками для мультивыбора"""
    dates = sorted(grouped.keys())
    kb = []
    for d in dates:
        try:
            d_formatted = date.fromisoformat(d).strftime('%d.%m.%Y')
        except:
            d_formatted = d
        
        prefix = "✅ " if d in selected_dates else "🗓 "
        kb.append([InlineKeyboardButton(
            text=f"{prefix}{d_formatted}",
            callback_data=f"toggle_date:{d}"
        )])
    
    if selected_dates:
        kb.append([InlineKeyboardButton(
            text="💾 Записаться на выбранные дни",
            callback_data="start_multi_book"
        )])
    
    return InlineKeyboardMarkup(inline_keyboard=kb)

def slots_by_date_kb(slots):
    """Показывает кнопки времени для текущего дня"""
    kb = []
    for sid, ts, te in slots:
        kb.append([InlineKeyboardButton(
            text=f"⏰ {ts} – {te}",
            callback_data=f"multi_book:{sid}"
        )])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def my_slots_kb(slots):
    kb = [[InlineKeyboardButton(
        text=f"{d} {ts}-{te}",
        callback_data=f"pick_cancel:{sid}"
    )] for sid, d, ts, te in slots]
    return InlineKeyboardMarkup(inline_keyboard=kb) if kb else None

def reasons_kb():
    kb = [[InlineKeyboardButton(text=label, callback_data=f"reason:{code}")] for code, label in CANCEL_REASONS]
    return InlineKeyboardMarkup(inline_keyboard=kb)

router = Router()

@router.message(Command("start"))
async def start(msg: Message, state: FSMContext):
    if msg.chat.type in ['group', 'supergroup']:
        return
        
    await state.clear()
    if db.get_courier(msg.from_user.id):
        await msg.answer(
            f"👋 Снова здравствуй!\nДаркстор: <b>{DARKSTORE}</b>\nВыбери действие:",
            reply_markup=main_kb(msg.from_user.id in ADMIN_IDS)
        )
        return
    await msg.answer(
        f"👋 Добро пожаловать в бот графика курьеров\n"
        f"<b>{DARKSTORE}</b>\n\n"
        f"Давай зарегистрируемся.\nВведи своё <b>ФИО</b>:"
    )
    await state.set_state(Reg.name)

@router.message(Reg.name)
async def reg_name(msg: Message, state: FSMContext):
    await state.update_data(name=msg.text.strip())
    await msg.answer(
        "📱 Теперь отправь свой номер телефона, нажав на кнопку ниже.",
        reply_markup=phone_kb()
    )
    await state.set_state(Reg.phone)

@router.message(Reg.phone, F.contact)
async def reg_phone_contact(msg: Message, state: FSMContext):
    data = await state.get_data()
    if msg.contact.user_id != msg.from_user.id:
        await msg.answer("⚠️ Пожалуйста, отправь именно свой номер телефона.")
        return
        
    db.add_courier(msg.from_user.id, data["name"], msg.contact.phone_number)
    await state.clear()
    await msg.answer(
        "✅ Регистрация завершена!",
        reply_markup=main_kb(msg.from_user.id in ADMIN_IDS)
    )

@router.message(Reg.phone)
async def reg_phone_wrong(msg: Message):
    await msg.answer("⚠️ Нажми на кнопку «📱 Отправить номер телефона».", reply_markup=phone_kb())

@router.message(F.text == "ℹ️ Инфо")
async def info(msg: Message):
    await msg.answer(
        f"🏪 <b>{DARKSTORE}</b>\n\n"
        f"• Слоты на 14 дней вперёд\n"
        f"• Можно взять несколько смен на разные дни\n"
        f"• На одно время могут записаться несколько курьеров"
    )

# --- НОВАЯ ЛОГИКА ВЫБОРА СЛОТОВ ---

@router.message(F.text == "📅 Свободные слоты")
async def free_slots(msg: Message, state: FSMContext):
    await state.clear()
    db.ensure_week_slots()
    grouped = db.get_free_slots_by_date()
    
    if not grouped:
        await msg.answer("Свободных слотов пока нет 😕")
        return
        
    await state.update_data(selected_dates=[])
    await msg.answer(
        "Выбери дни, на которые хочешь записаться (можно несколько):", 
        reply_markup=multi_dates_kb(grouped, [])
    )
    await state.set_state(MultiBook.choosing_times)

@router.callback_query(MultiBook.choosing_times, F.data.startswith("toggle_date:"))
async def toggle_date(cb: CallbackQuery, state: FSMContext):
    selected_date = cb.data.split(":")[1]
    data = await state.get_data()
    selected_dates = data.get("selected_dates", [])
    
    if selected_date in selected_dates:
        selected_dates.remove(selected_date)
    else:
        selected_dates.append(selected_date)
        
    await state.update_data(selected_dates=selected_dates)
    
    grouped = db.get_free_slots_by_date()
    await cb.message.edit_reply_markup(
        reply_markup=multi_dates_kb(grouped, selected_dates)
    )

@router.callback_query(F.data == "start_multi_book")
async def start_multi_book(cb: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    selected_dates = sorted(data.get("selected_dates", []))
    
    if not selected_dates:
        await cb.answer("Ты не выбрал ни одного дня!", show_alert=True)
        return
        
    # Берем первый день из списка
    first_date = selected_dates[0]
    remaining_dates = selected_dates[1:]
    
    await state.update_data(
        current_date=first_date, 
        remaining_dates=remaining_dates
    )
    
    grouped = db.get_free_slots_by_date()
    date_slots = [(item[0], item[2], item[3]) for item in grouped.get(first_date, [])]
    
    try:
        d_formatted = date.fromisoformat(first_date).strftime('%d.%m.%Y')
    except:
        d_formatted = first_date

    await cb.message.edit_text(
        f"🗓 <b>Дата: {d_formatted}</b>\nВыбери удобное время:",
        reply_markup=slots_by_date_kb(date_slots)
    )

@router.callback_query(F.data.startswith("multi_book:"))
async def multi_book_time(cb: CallbackQuery, state: FSMContext):
    slot_id = int(cb.data.split(":")[1])
    data = await state.get_data()
    
    current_date = data.get("current_date")
    remaining_dates = data.get("remaining_dates", [])
    
    # Записываем на выбранное время
    db.book_slot(slot_id, cb.from_user.id)
    
    if remaining_dates:
        # Если есть еще дни, переходим к следующему
        next_date = remaining_dates[0]
        new_remaining = remaining_dates[1:]
        
        await state.update_data(
            current_date=next_date, 
            remaining_dates=new_remaining
        )
        
        grouped = db.get_free_slots_by_date()
        date_slots = [(item[0], item[2], item[3]) for item in grouped.get(next_date, [])]
        
        try:
            d_formatted = date.fromisoformat(next_date).strftime('%d.%m.%Y')
        except:
            d_formatted = next_date
            
        await cb.message.edit_text(
            f"🗓 <b>Дата: {d_formatted}</b>\nВыбери удобное время:",
            reply_markup=slots_by_date_kb(date_slots)
        )
    else:
        # Если дни закончились
        await state.clear()
        await cb.message.edit_text(f"✅ Успешно! Ты записан на выбранные дни.")
        await cb.message.answer("Главное меню:", reply_markup=main_kb(cb.from_user.id in ADMIN_IDS))

# --- МОИ СМЕНЫ И ОТМЕНА ---

@router.message(F.text == "🗓 Мои смены")
async def my_shifts(msg: Message):
    slots = db.get_my_slots(msg.from_user.id)
    if not slots:
        await msg.answer("У тебя нет записей на смены.")
        return
    text = "🗓 <b>Твои смены:</b>\n" + "\n".join(f"• {d} {ts}-{te}" for _, d, ts, te in slots)
    await msg.answer(text)

@router.message(F.text == "❌ Отменить смену")
async def cancel_start(msg: Message, state: FSMContext):
    slots = db.get_my_slots(msg.from_user.id)
    if not slots:
        await msg.answer("Нечего отменять — у тебя нет активных смен.")
        return
    await msg.answer("Выбери смену для отмены:", reply_markup=my_slots_kb(slots))
    await state.set_state(CancelSlot.choosing_slot)

@router.callback_query(F.data.startswith("pick_cancel:"))
async def cancel_pick(cb: CallbackQuery, state: FSMContext):
    slot_id = int(cb.data.split(":")[1])
    await state.update_data(slot_id=slot_id)
    await cb.message.edit_text("Укажи причину отмены:", reply_markup=reasons_kb())
    await state.set_state(CancelSlot.choosing_reason)

@router.callback_query(F.data.startswith("reason:"))
async def cancel_reason(cb: CallbackQuery, state: FSMContext):
    code = cb.data.split(":")[1]
    label = dict(CANCEL_REASONS)[code]
    await state.update_data(reason_code=code, reason_label=label)
    if code == "other":
        await cb.message.edit_text("Опиши причину текстом:")
        await state.set_state(CancelSlot.detail)
        return
    data = await state.get_data()
    db.cancel_slot(data["slot_id"], cb.from_user.id, label, "")
    await state.clear()
    await cb.message.edit_text(f"❌ Смена отменена.\nПричина: {label}")
    for aid in ADMIN_IDS:
        try:
            await cb.bot.send_message(aid, f"❌ <b>Отмена смены</b>\nКурьер: {db.get_courier(cb.from_user.id)[1]}\nПричина: {label}")
        except:
            pass

@router.message(CancelSlot.detail)
async def cancel_detail(msg: Message, state: FSMContext):
    data = await state.get_data()
    db.cancel_slot(data["slot_id"], msg.from_user.id, data["reason_label"], msg.text)
    await state.clear()
    await msg.answer(f"❌ Смена отменена.\nПричина: {data['reason_label']} — {msg.text}")
    for aid in ADMIN_IDS:
        try:
            await msg.bot.send_message(aid, f"❌ <b>Отмена смены</b>\nКурьер: {db.get_courier(msg.from_user.id)[1]}\nПричина: {data['reason_label']}")
        except:
            pass

# --- ВВОД ЗАДАНИЙ ---

@router.message(F.text == "✍️ Ввести задания")
async def start_report(msg: Message, state: FSMContext):
    today = date.today().isoformat()
    if db.has_report_today(msg.from_user.id, today):
        await msg.answer("⚠️ Ты уже сдал отчет за сегодня! Завтра сможешь сдать новый.")
        return
    await msg.answer("Введи количество выполненных заданий (число от 1 до 150):")
    await state.set_state(ReportTasks.waiting_for_tasks)

@router.message(ReportTasks.waiting_for_tasks)
async def process_report(msg: Message, state: FSMContext):
    if not msg.text.isdigit():
        await msg.answer("⚠️ Введи только число (например: 25).")
        return
    tasks = int(msg.text)
    if tasks < 1:
        await msg.answer("⚠️ Количество заданий должно быть больше нуля.")
        return
    if tasks > 150:
        await msg.answer("⚠️ Максимум 150 заданий за смену.")
        return
    today = date.today().isoformat()
    db.save_report(msg.from_user.id, today, tasks)
    await state.clear()
    await msg.answer(f"✅ Отчёт сохранен: <b>{tasks}</b> заданий.", reply_markup=main_kb(msg.from_user.id in ADMIN_IDS))
    
    courier = db.get_courier(msg.from_user.id)
    report_text = f"📝 <b>Новый отчёт о заданиях</b>\n\n👤 Курьер: <b>{courier[1]}</b>\n📞 Тел: {courier[2]}\n📦 Выполнено: <b>{tasks}</b> шт."
    
    from config import WORK_CHAT_ID
    for aid in ADMIN_IDS:
        try:
            await msg.bot.send_message(aid, report_text)
        except:
            pass
    if WORK_CHAT_ID != 0:
        try:
            await msg.bot.send_message(WORK_CHAT_ID, report_text)
        except:
            pass

# --- КОМАНДЫ ДЛЯ ЧАТА ---

@router.message(Command("top"))
async def chat_top(msg: Message):
    today = date.today()
    start = (today - timedelta(days=today.weekday())).isoformat()
    end = (today + timedelta(days=6)).isoformat()
    await send_top_to_chat(msg, start, end, "Неделя")

@router.message(Command("stats"))
async def chat_stats(msg: Message):
    today = date.today()
    start = (today - timedelta(days=today.weekday())).isoformat()
    end = (today + timedelta(days=6)).isoformat()
    stats = db.weekly_stats(start, end)
    tasks = db.get_all_tasks_period(start, end)
    if not stats and not tasks:
        await msg.answer("За эту неделю пока нет данных.")
        return
    lines = [f"📈 <b>Статистика за неделю</b>\n({start} - {end}):\n"]
    for name, hours in sorted(stats.items(), key=lambda x: x[1], reverse=True):
        lines.append(f"👤 {name}: {hours:.1f} ч.")
    lines.append("\n<b>Задания:</b>")
    for name, count in tasks:
        lines.append(f"👤 {name}: {count} шт.")
    await msg.answer("\n".join(lines))

# --- АДМИН ПАНЕЛЬ ---

@router.message(F.text == "🛠 Админ-панель")
async def admin_panel(msg: Message):
    if msg.from_user.id not in ADMIN_IDS: return
    await msg.answer("Админ-панель:", reply_markup=admin_kb())

@router.message(F.text == "🔙 Назад")
async def back(msg: Message):
    await msg.answer("Главное меню", reply_markup=main_kb(msg.from_user.id in ADMIN_IDS))

@router.message(F.text == "🔙 Назад в админку")
async def back_admin(msg: Message):
    await msg.answer("Админ-панель:", reply_markup=admin_kb())

@router.message(F.text == "📢 Сделать рассылку")
async def broadcast_start(msg: Message, state: FSMContext):
    if msg.from_user.id not in ADMIN_IDS: return
    await msg.answer("Напиши текст для рассылки:", reply_markup=ReplyKeyboardRemove())
    await state.set_state(Broadcast.waiting_for_text)

@router.message(Broadcast.waiting_for_text)
async def broadcast_send(msg: Message, state: FSMContext):
    if msg.from_user.id not in ADMIN_IDS: return
    text = msg.text
    couriers = db.get_all_couriers()
    success = 0
    for cid in couriers:
        try:
            await msg.bot.send_message(cid, text)
            success += 1
            await asyncio.sleep(0.05)
        except Exception:
            pass
    await state.clear()
    await msg.answer(f"✅ Рассылка завершена.\nДоставлено: {success} из {len(couriers)}", reply_markup=admin_kb())

@router.message(F.text == "📊 График на сегодня")
async def sched_today(msg: Message):
    if msg.from_user.id not in ADMIN_IDS: return
    await send_schedule(msg, date.today())

@router.message(F.text == "📊 График на завтра")
async def sched_tomorrow(msg: Message):
    if msg.from_user.id not in ADMIN_IDS: return
    await send_schedule(msg, date.today() + timedelta(days=1))

@router.message(F.text == "📅 График на неделю")
async def sched_week(msg: Message):
    if msg.from_user.id not in ADMIN_IDS: return
    today = date.today()
    lines = ["📅 <b>График на неделю:</b>\n"]
    for i in range(7):
        d = today + timedelta(days=i)
        rows = db.schedule_for_date(d.isoformat())
        if not rows: continue
        lines.append(f"<b>{d.strftime('%d.%m (%a)')}</b>")
        for ts, te, name, phone in rows:
            lines.append(f"  • {ts}-{te} — {name if name else 'пусто'}")
        lines.append("")
    text = "\n".join(lines)
    for i in range(0, len(text), 4000):
        await msg.answer(text[i:i+4000])

@router.message(F.text == "📈 Статистика")
async def stats_menu(msg: Message):
    if msg.from_user.id not in ADMIN_IDS: return
    await chat_stats(msg)

@router.message(F.text == "🏆 Топ курьеров")
async def top_menu(msg: Message):
    if msg.from_user.id not in ADMIN_IDS: return
    await msg.answer("Выбери период:", reply_markup=top_kb())

@router.message(F.text == "🏆 Топ за сегодня")
async def top_day(msg: Message):
    if msg.from_user.id not in ADMIN_IDS: return
    today = date.today().isoformat()
    await send_top_to_chat(msg, today, today, "Сегодня")

@router.message(F.text == "🏆 Топ за неделю")
async def top_week(msg: Message):
    if msg.from_user.id not in ADMIN_IDS: return
    today = date.today()
    start = (today - timedelta(days=today.weekday())).isoformat()
    end = (today + timedelta(days=6)).isoformat()
    await send_top_to_chat(msg, start, end, "Неделя")

@router.message(F.text == "🏆 Топ за месяц")
async def top_month(msg: Message):
    if msg.from_user.id not in ADMIN_IDS: return
    today = date.today()
    start = today.replace(day=1).isoformat()
    next_month = today.replace(day=28) + timedelta(days=4)
    end = (next_month - timedelta(days=next_month.day)).isoformat()
    await send_top_to_chat(msg, start, end, "Месяц")

async def send_top_to_chat(msg: Message, start, end, period_name):
    rows = db.get_top(start, end, limit=3)
    if not rows:
        await msg.answer(f"За период «{period_name}» пока нет заданий.")
        return
    lines = [f"🏆 <b>Топ-3 курьера ({period_name}):</b>\n"]
    medals = ["🥇", "🥈", "🥉"]
    for i, (name, tasks) in enumerate(rows):
        lines.append(f"{medals[i]} <b>{name}</b> — {tasks} заданий")
    await msg.answer("\n".join(lines))

@router.message(F.text == "📋 Отчёты по отменам")
async def cancels(msg: Message):
    if msg.from_user.id not in ADMIN_IDS: return
    rows = db.cancellations_report()
    if not rows:
        await msg.answer("Отмен пока нет.")
        return
    lines = ["📋 <b>Последние отмены:</b>"]
    for d, ts, te, name, reason, detail, at in rows:
        extra = f" — {detail}" if detail else ""
        lines.append(f"• {d} {ts}-{te} | {name or '?'} | {reason}{extra}")
    await msg.answer("\n".join(lines))

async def send_schedule(msg: Message, d: date):
    db.ensure_week_slots()
    rows = db.schedule_for_date(d.isoformat())
    if not rows:
        await msg.answer("Нет данных.")
        return
    lines = [f"📊 <b>График на {d.strftime('%d.%m.%Y')}</b>"]
    for ts, te, name, phone in rows:
        if name:
            lines.append(f"✅ {ts}-{te} — {name} ({phone})")
        else:
            lines.append(f"🟢 {ts}-{te} — свободен")
    await msg.answer("\n".join(lines))

async def main():
    db.init_db()
    db.ensure_week_slots(days=14)
    
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
    dp = Dispatcher()
    dp.include_router(router)
    
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
