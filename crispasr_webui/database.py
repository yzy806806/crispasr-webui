#!/usr/bin/env python3
"""
CrispASR TTS Web UI v0.9 — Database
SQLite initialisation, migrations, connection helper.
Only imports from config.
"""

import sqlite3

from . import config


def init_db() -> None:
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    config.AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    config.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(config.DB_PATH))
    try:
        # M5: Enable WAL mode for better concurrent read/write performance
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS history (
                id TEXT PRIMARY KEY,
                text TEXT NOT NULL,
                voice TEXT NOT NULL,
                instruct TEXT DEFAULT '',
                speed REAL DEFAULT 1.0,
                fmt TEXT DEFAULT 'wav',
                audio_file TEXT,
                duration REAL DEFAULT 0,
                status TEXT DEFAULT 'pending',
                chunks_config TEXT DEFAULT '',
                created_at REAL NOT NULL,
                finished_at REAL
            );
            CREATE TABLE IF NOT EXISTS voices (
                name TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                created_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
        """)
        # Auto-migrate: add missing columns from older schema
        try:
            cols = [r[1] for r in conn.execute("PRAGMA table_info(history)").fetchall()]
            if "chunks_config" not in cols:
                conn.execute("ALTER TABLE history ADD COLUMN chunks_config TEXT DEFAULT ''")
            if "finished_at" not in cols:
                conn.execute("ALTER TABLE history ADD COLUMN finished_at REAL")
        except Exception:
            pass
        conn.commit()
    finally:
        conn.close()


def db_conn() -> sqlite3.Connection:
    """Get a database connection. Supports context manager for auto-close."""
    conn = sqlite3.connect(str(config.DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


class DBCtx:
    """Context manager wrapper for db_conn(). Usage: with DBCtx() as conn: ..."""
    def __enter__(self):
        self._conn = db_conn()
        return self._conn
    def __exit__(self, *exc):
        self._conn.close()
        return False
