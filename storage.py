import sqlite3
import time
from pathlib import Path
from config import settings

DB_PATH = settings.data_dir / "watchdog.db"

def get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_conn() as conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("""
        CREATE TABLE IF NOT EXISTS metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts INTEGER NOT NULL,
            iface TEXT,
            tx_bytes INTEGER,
            rx_bytes INTEGER,
            tx_used_mb REAL,
            rx_used_mb REAL,
            tx_speed_kbps REAL,
            rx_speed_kbps REAL,
            cpu_percent REAL,
            mem_percent REAL,
            disk_percent REAL,
            load1 REAL,
            uptime_seconds INTEGER
        )
        """)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts INTEGER NOT NULL,
            level TEXT NOT NULL,
            type TEXT NOT NULL,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            sent INTEGER NOT NULL DEFAULT 0
        )
        """)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS state (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """)
        conn.commit()

def get_state(key: str, default: str | None = None) -> str | None:
    with get_conn() as conn:
        row = conn.execute("SELECT value FROM state WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default

def set_state(key: str, value: str) -> None:
    with get_conn() as conn:
        conn.execute("INSERT OR REPLACE INTO state(key,value) VALUES(?,?)", (key, value))
        conn.commit()

def insert_metric(data: dict):
    fields = [
        "ts", "iface", "tx_bytes", "rx_bytes", "tx_used_mb", "rx_used_mb",
        "tx_speed_kbps", "rx_speed_kbps", "cpu_percent", "mem_percent",
        "disk_percent", "load1", "uptime_seconds"
    ]
    values = [data.get(f) for f in fields]
    with get_conn() as conn:
        conn.execute(
            f"INSERT INTO metrics ({','.join(fields)}) VALUES ({','.join(['?']*len(fields))})",
            values
        )
        conn.commit()

def insert_alert(level: str, typ: str, title: str, message: str, sent: bool = False):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO alerts(ts,level,type,title,message,sent) VALUES(?,?,?,?,?,?)",
            (int(time.time()), level, typ, title, message, 1 if sent else 0)
        )
        conn.commit()

def recent_metrics(limit: int = 288) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM metrics ORDER BY id DESC LIMIT ?",
            (limit,)
        ).fetchall()
        return [dict(r) for r in reversed(rows)]

def recent_alerts(limit: int = 50) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM alerts ORDER BY id DESC LIMIT ?",
            (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

def count_mails_today() -> int:
    now = int(time.time())
    start = now - (now % 86400)
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM alerts WHERE sent=1 AND ts>=?",
            (start,)
        ).fetchone()
        return int(row["c"])

def cleanup_old(days: int = 30):
    cutoff = int(time.time()) - days * 86400
    with get_conn() as conn:
        conn.execute("DELETE FROM metrics WHERE ts < ?", (cutoff,))
        conn.execute("DELETE FROM alerts WHERE ts < ?", (cutoff,))
        conn.commit()

# Automatically initialize database when module is imported
init_db()
