"""
Mock database layer.

In production this is where you'd call INTERPOL I-24/7 SLTD (restricted
to law enforcement) or a national passport-issuing-authority API instead
of a local SQLite table.
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "screening.db"


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS blacklist (
            passport_number TEXT PRIMARY KEY,
            reason TEXT,
            added_on TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS scan_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            passport_number TEXT,
            risk_score INTEGER,
            verdict TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.executemany(
        "INSERT OR IGNORE INTO blacklist (passport_number, reason) VALUES (?, ?)",
        [
            ("X9988771", "reported stolen"),
            ("Y5566123", "revoked - fraud investigation"),
        ],
    )
    conn.commit()
    conn.close()


def get_blacklist() -> set:
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("SELECT passport_number FROM blacklist").fetchall()
    conn.close()
    return {r[0] for r in rows}


def log_scan(passport_number, risk_score, verdict):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO scan_log (passport_number, risk_score, verdict) VALUES (?, ?, ?)",
        (passport_number, risk_score, verdict),
    )
    conn.commit()
    conn.close()
