import os
import sqlite3
from datetime import datetime, date, timedelta

DB_PATH = os.getenv("DB_PATH", "schedule.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS couriers (
        user_id INTEGER PRIMARY KEY,
        full_name TEXT,
        phone TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS slots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        time_start TEXT NOT NULL,
        time_end TEXT NOT NULL,
        courier_id INTEGER,
        status TEXT DEFAULT 'free',
        created_at TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS cancellations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        slot_id INTEGER,
        courier_id INTEGER,
        reason TEXT,
        reason_detail TEXT,
        cancelled_at TEXT
    )""")
    conn.commit()
    conn.close()

def add_courier(user_id, full_name, phone):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT OR REPLACE INTO couriers(user_id, full_name, phone) VALUES (?,?,?)",
        (user_id, full_name, phone)
    )
    conn.commit(); conn.close()

def get_courier(user_id):
    conn = sqlite3.connect(DB_PATH)
    r = conn.execute("SELECT * FROM couriers WHERE user_id=?", (user_id,)).fetchone()
    conn.close()
    return r

def ensure_week_slots(days=14):
    conn = sqlite3.connect(DB_PATH)
    today = date.today()
    
    # ТВОИ НОВЫЕ СМЕНЫ
    times = [
        ("11:00", "00:00"), # 13 часов
        ("08:00", "20:00"), # 12 часов
        ("13:00", "01:00"), # 12 часов (вечерняя)
        ("17:00", "01:00"), # 8 часов
        ("17:00", "00:00"), # 7 часов
        ("18:00", "00:00")  # 6 часов
    ]
    
    for i in range(days):
        d = (today + timedelta(days=i)).isoformat()
        for ts, te in times:
            exists = conn.execute(
                "SELECT 1 FROM slots WHERE date=? AND time_start=? AND status!='cancelled'",
                (d, ts)
            ).fetchone()
            if not exists:
                conn.execute(
                    "INSERT INTO slots(date,time_start,time_end,status,created_at) VALUES (?,?,?, 'free', ?)",
                    (d, ts, te, datetime.now().isoformat())
                )
    conn.commit(); conn.close()

def get_free_slots_by_date():
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT id,date,time_start,time_end FROM slots WHERE status='free' ORDER BY date,time_start"
    ).fetchall()
    conn.close()
    grouped = {}
    for r in rows:
        grouped.setdefault(r[1], []).append(r)
    return grouped

def book_slot(slot_id, courier_id):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute(
        "UPDATE slots SET courier_id=?, status='booked' WHERE id=? AND status='free'",
        (courier_id, slot_id)
    )
    ok = cur.rowcount > 0
    conn.commit(); conn.close()
    return ok

def get_my_slots(courier_id):
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT id,date,time_start,time_end FROM slots WHERE courier_id=? AND status='booked' ORDER BY date,time_start",
        (courier_id,)
    ).fetchall()
    conn.close()
    return rows

def get_slot(slot_id):
    conn = sqlite3.connect(DB_PATH)
    r = conn.execute("SELECT * FROM slots WHERE id=?", (slot_id,)).fetchone()
    conn.close()
    return r

def cancel_slot(slot_id, courier_id, reason, detail):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "UPDATE slots SET status='cancelled', courier_id=NULL WHERE id=? AND courier_id=? AND status='booked'",
        (slot_id, courier_id)
    )
    conn.execute(
        "INSERT INTO cancellations(slot_id,courier_id,reason,reason_detail,cancelled_at) VALUES (?,?,?,?,?)",
        (slot_id, courier_id, reason, detail, datetime.now().isoformat())
    )
    conn.commit(); conn.close()

def schedule_for_date(d):
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("""
        SELECT s.id, s.time_start, s.time_end, s.status, c.full_name, c.phone
        FROM slots s LEFT JOIN couriers c ON s.courier_id = c.user_id
        WHERE s.date=? ORDER BY s.time_start
    """, (d,)).fetchall()
    conn.close()
    return rows

def cancellations_report(limit=50):
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("""
        SELECT s.date, s.time_start, s.time_end, c.full_name, x.reason, x.reason_detail, x.cancelled_at
        FROM cancellations x
        JOIN slots s ON s.id = x.slot_id
        LEFT JOIN couriers c ON c.user_id = x.courier_id
        ORDER BY x.cancelled_at DESC LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return rows
