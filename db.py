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
        created_at TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS bookings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        slot_id INTEGER,
        courier_id INTEGER,
        status TEXT DEFAULT 'booked',
        UNIQUE(slot_id, courier_id)
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        courier_id INTEGER,
        date TEXT,
        tasks INTEGER
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

def get_all_couriers():
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("SELECT user_id FROM couriers").fetchall()
    conn.close()
    return [r[0] for r in rows]

def ensure_week_slots(days=14):
    conn = sqlite3.connect(DB_PATH)
    today = date.today()
    times = [
        ("11:00", "00:00"), ("08:00", "20:00"), ("13:00", "01:00"),
        ("17:00", "01:00"), ("17:00", "00:00"), ("18:00", "00:00")
    ]
    for i in range(days):
        d = (today + timedelta(days=i)).isoformat()
        for ts, te in times:
            exists = conn.execute(
                "SELECT 1 FROM slots WHERE date=? AND time_start=?", (d, ts)
            ).fetchone()
            if not exists:
                conn.execute(
                    "INSERT INTO slots(date,time_start,time_end,created_at) VALUES (?,?,?,?)",
                    (d, ts, te, datetime.now().isoformat())
                )
    conn.commit(); conn.close()

def get_courier_shifts_by_date(courier_id, target_date):
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("""
        SELECT b.id FROM bookings b
        JOIN slots s ON b.slot_id = s.id
        WHERE b.courier_id=? AND s.date=? AND b.status='booked'
    """, (courier_id, target_date)).fetchall()
    conn.close()
    return len(rows)

def get_free_slots_by_date():
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT id,date,time_start,time_end FROM slots WHERE date >= date('now') ORDER BY date,time_start"
    ).fetchall()
    conn.close()
    grouped = {}
    for r in rows:
        grouped.setdefault(r[1], []).append(r)
    return grouped

def book_slot(slot_id, courier_id):
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("INSERT INTO bookings(slot_id, courier_id) VALUES (?,?)", (slot_id, courier_id))
        ok = True
    except sqlite3.IntegrityError:
        ok = False
    conn.commit(); conn.close()
    return ok

def get_my_slots(courier_id):
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("""
        SELECT s.id, s.date, s.time_start, s.time_end 
        FROM bookings b JOIN slots s ON b.slot_id = s.id 
        WHERE b.courier_id=? AND b.status='booked' 
        ORDER BY s.date, s.time_start
    """, (courier_id,)).fetchall()
    conn.close()
    return rows

def get_slot(slot_id):
    conn = sqlite3.connect(DB_PATH)
    r = conn.execute("SELECT * FROM slots WHERE id=?", (slot_id,)).fetchone()
    conn.close()
    return r

def cancel_slot(slot_id, courier_id, reason, detail):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("UPDATE bookings SET status='cancelled' WHERE slot_id=? AND courier_id=?", (slot_id, courier_id))
    conn.execute(
        "INSERT INTO cancellations(slot_id,courier_id,reason,reason_detail,cancelled_at) VALUES (?,?,?,?,?)",
        (slot_id, courier_id, reason, detail, datetime.now().isoformat())
    )
    conn.commit(); conn.close()

def schedule_for_date(d):
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("""
        SELECT s.time_start, s.time_end, c.full_name, c.phone
        FROM slots s 
        LEFT JOIN bookings b ON s.id = b.slot_id AND b.status='booked'
        LEFT JOIN couriers c ON b.courier_id = c.user_id
        WHERE s.date=? ORDER BY s.time_start
    """, (d,)).fetchall()
    conn.close()
    return rows

def weekly_stats(start_date, end_date):
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("""
        SELECT c.full_name, s.time_start, s.time_end
        FROM bookings b
        JOIN slots s ON b.slot_id = s.id
        JOIN couriers c ON b.courier_id = c.user_id
        WHERE s.date >= ? AND s.date <= ? AND b.status='booked'
    """, (start_date, end_date)).fetchall()
    conn.close()
    
    stats = {}
    for name, ts, te in rows:
        t1 = datetime.strptime(ts, "%H:%M")
        t2 = datetime.strptime(te, "%H:%M")
        if t2 < t1:
            t2 += timedelta(days=1)
        hours = (t2 - t1).total_seconds() / 3600
        stats[name] = stats.get(name, 0) + hours
    return stats

def save_report(courier_id, report_date, tasks):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO reports (courier_id, date, tasks) VALUES (?, ?, ?)",
        (courier_id, report_date, tasks)
    )
    conn.commit(); conn.close()

def get_top(start_date, end_date, limit=3):
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("""
        SELECT c.full_name, SUM(r.tasks) as total_tasks
        FROM reports r
        JOIN couriers c ON r.courier_id = c.user_id
        WHERE r.date >= ? AND r.date <= ?
        GROUP BY r.courier_id
        ORDER BY total_tasks DESC
        LIMIT ?
    """, (start_date, end_date, limit)).fetchall()
    conn.close()
    return rows

def get_all_tasks_period(start_date, end_date):
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("""
        SELECT c.full_name, SUM(r.tasks)
        FROM reports r JOIN couriers c ON r.courier_id = c.user_id
        WHERE r.date >= ? AND r.date <= ?
        GROUP BY r.courier_id ORDER BY SUM(r.tasks) DESC
    """, (start_date, end_date)).fetchall()
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
