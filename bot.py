import asyncio
from datetime import date, timedelta
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton
)

from config import BOT_TOKEN, ADMIN_IDS, DARKSTORE
import db

class Reg(StatesGroup):
    name = State()
    phone = State()

class CancelSlot(StatesGroup):
    choosing_slot = State()
    choosing_reason = State()
    detail = State()

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
        [KeyboardButton(text="ℹ️ Инфо")],
    ]
    if is_admin:
        kb.append([KeyboardButton(text="🛠 Админ-панель")])
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def admin_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📊 График на сегодня")],
            [KeyboardButton(text="📊 График на завтра")],
            [KeyboardButton(text="📋 Отчёты по отменам")],
            [KeyboardButton(text="🔙 Назад")],
        ],
        resize_keyboard=True
    )

def slots_kb(grouped):
    kb = []
    for d, items in grouped.items():
        for sid, dd, ts, te in items:
            kb.append([InlineKeyboardButton(
                text=f"{dd} {ts}-{te}",
                callback_data=f"book:{sid}"
            )])
    return InlineKeyboardMarkup(inline_keyboard=kb) if kb else None

def my_slots_kb(slots):
    kb = [[InlineKeyboardButton(
        text=f"{d} {ts}-{te}",
        callback_data=f"pick_cancel:{sid}"
    )] for sid, d, ts, te in slots]
    return InlineKeyboardMarkup(inline_keyboard=kb) if kb else None

def reasons_kb():
    kb = [[InlineKeyboardButton(text=label, callback_data=f"reason:{code}")] for code, label in CANCEL_REASONS]
    return InlineKeyboardMarkup(inline_keyboard=kb)

from aiogram import Router
router = Router()

@router.message(Command("start"))
async def start(msg: Message, state: FSMContext):
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
    await msg.answer("📱 Введи номер телефона (например +79991234567):")
    await state.set_state(Reg.phone)

@router.message(Reg.phone)
async def reg_phone(msg: Message, state: FSMContext):
    data = await state.get_data()
    db.add_courier(msg.from_user.id, data["name"], msg.text.strip())
    await state.clear()
    await msg.answer(
        "✅ Регистрация завершена!",
        reply_markup=main_kb(msg.from_user.id in ADMIN_IDS)
    )

@router.message(F.text == "ℹ️ Инфо")
async def info(msg: Message):
    await msg.answer(
        f"🏪 <b>{DARKSTORE}</b>\n\n"
        f"• Слоты на 7 дней вперёд\n"
        f"• 3 смены в день: 08:00-14:00, 14:00-20:00, 20:00-23:00\n"
        f"• Отмена смены — только с указанием причины"
    )

@router.message(F.text == "📅 Свободные слоты")
async def free_slots(msg: Message):
    db.ensure_week_slots()
    grouped = db.get_free_slots_by_date()
    kb = slots_kb(grouped)
    if not kb:
        await msg.answer("Свободных слотов пока нет 😕")
        return
    await msg.answer("Выбери слот для записи:", reply_markup=kb)

@router.callback_query(F.data.startswith("book:"))
async def do_book(cb: CallbackQuery):
    slot_id = int(cb.data.split(":")[1])
    ok = db.book_slot(slot_id, cb.from_user.id)
    if ok:
        s = db.get_slot(slot_id)
        await cb.message.edit_text(
            f"✅ Ты записан: <b>{s[1]} {s[2]}-{s[3]}</b>"
        )
    else:
        await cb.answer("Слот уже занят 😕", show_alert=True)

@router.message(F.text == "🗓 Мои смены")
async def my_shifts(msg: Message):
    slots = db.get_my_slots(msg.from_user.id)
    if not slots:
        await msg.answer("У тебя нет записей на смены.")
        return
    text = "🗓 <b>Твои смены:</b>\n" + "\n".join(
        f"• {d} {ts}-{te}" for _, d, ts, te in slots
    )
    await msg.answer(text)

@router.message(F.text == "❌ Отменить смену")
async def cancel_start(msg: Message, state: FSMContext):
    slots = db.get_my_slots(msg.from_user.id)
    if not slots:
        await msg.answer("Нечего отменять — у тебя нет активных смен.")
        return
    await msg.answer(
        "Выбери смену для отмены:",
        reply_markup=my_slots_kb(slots)
    )
    await state.set_state(CancelSlot.choosing_slot)

@router.callback_query(F.data.startswith("pick_cancel:"))
async def cancel_pick(cb: CallbackQuery, state: FSMContext):
    slot_id = int(cb.data.split(":")[1])
    await state.update_data(slot_id=slot_id)
    await cb.message.edit_text(
        "Укажи причину отмены:",
        reply_markup=reasons_kb()
    )
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
            await msg.bot.send_message(aid, f"❌ <b>Отмена смены</b>\nКурьер: {db.get_courier(msg.from_user.id)[1]}\nПричина: {data['reason_label']}\nДетали: {msg.text}")
        except:
            pass

@router.message(F.text == "🛠 Админ-панель")
async def admin_panel(msg: Message):
    if msg.from_user.id not in ADMIN_IDS:
        return
    await msg.answer("Админ-панель:", reply_markup=admin_kb())

@router.message(F.text == "🔙 Назад")
async def back(msg: Message):
    await msg.answer("Главное меню", reply_markup=main_kb(msg.from_user.id in ADMIN_IDS))

@router.message(F.text == "📊 График на сегодня")
async def sched_today(msg: Message):
    if msg.from_user.id not in ADMIN_IDS: return
    await send_schedule(msg, date.today())

@router.message(F.text == "📊 График на завтра")
async def sched_tomorrow(msg: Message):
    if msg.from_user.id not in ADMIN_IDS: return
    await send_schedule(msg, date.today() + timedelta(days=1))

async def send_schedule(msg: Message, d: date):
    db.ensure_week_slots()
    rows = db.schedule_for_date(d.isoformat())
    if not rows:
        await msg.answer("Нет данных.")
        return
    lines = [f"📊 <b>График на {d.strftime('%d.%m.%Y')}</b>"]
    for sid, ts, te, status, name, phone in rows:
        if status == "booked":
            lines.append(f"✅ {ts}-{te} — {name} ({phone})")
        elif status == "free":
            lines.append(f"🟢 {ts}-{te} — свободен")
        else:
            lines.append(f"🔴 {ts}-{te} — отменён")
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

async def main():
    db.init_db()
    db.ensure_week_slots(days=14)
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    dp.include_router(router)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
    proxy_url = "socks5://modeler_ERgRnW:00qoCuIlWfMN@139.144.99.147:23411"
