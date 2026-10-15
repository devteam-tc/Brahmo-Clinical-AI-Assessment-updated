"""Database connection manager for SQLite.
Configures WAL mode, busy timeout, and foreign keys.
"""
import sqlite3
from typing import Generator
from contextlib import contextmanager
from config.settings import settings

def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(
        settings.db.db_path,
        timeout=settings.db.busy_timeout_ms / 1000.0
    )
    conn.row_factory = sqlite3.Row
    if settings.db.wal_mode:
        conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn

@contextmanager
def get_db() -> Generator[sqlite3.Connection, None, None]:
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
