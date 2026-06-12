import sqlite3
import time
import hashlib
import secrets
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
        conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            created_at INTEGER NOT NULL
        )
        """)
        conn.commit()

def hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    if salt is None:
        salt = secrets.token_hex(16)
    pwd_bytes = password.encode('utf-8')
    salt_bytes = salt.encode('utf-8')
    h_bytes = hashlib.pbkdf2_hmac('sha256', pwd_bytes, salt_bytes, 100000)
    return h_bytes.hex(), salt

def create_admin(username: str, password: str) -> bool:
    h_pass, salt = hash_password(password)
    try:
        with get_conn() as conn:
            conn.execute(
                "INSERT INTO users (username, password_hash, salt, created_at) VALUES (?, ?, ?, ?)",
                (username, h_pass, salt, int(time.time()))
            )
            conn.commit()
            return True
    except sqlite3.IntegrityError:
        return False

def verify_admin(username: str, password: str) -> bool:
    with get_conn() as conn:
        row = conn.execute("SELECT password_hash, salt FROM users WHERE username=?", (username,)).fetchone()
        if not row:
            return False
        stored_hash = row["password_hash"]
        salt = row["salt"]
        h_pass, _ = hash_password(password, salt)
        return secrets.compare_digest(stored_hash, h_pass)

def has_admin() -> bool:
    with get_conn() as conn:
        row = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()
        return int(row["c"]) > 0

def update_admin_password(username: str, old_password: str, new_password: str) -> bool:
    if not verify_admin(username, old_password):
        return False
    h_pass, salt = hash_password(new_password)
    with get_conn() as conn:
        conn.execute(
            "UPDATE users SET password_hash=?, salt=? WHERE username=?",
            (h_pass, salt, username)
        )
        conn.commit()
    return True

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
