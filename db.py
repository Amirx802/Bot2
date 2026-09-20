import os
import sqlite3
import time
from contextlib import contextmanager

from .config import settings


@contextmanager
def _conn():
    os.makedirs(os.path.dirname(settings.db_path) or ".", exist_ok=True)
    con = sqlite3.connect(settings.db_path)
    try:
        yield con
        con.commit()
    finally:
        con.close()


def init_db() -> None:
    with _conn() as c:
        c.execute(
            """CREATE TABLE IF NOT EXISTS users (
                   id INTEGER PRIMARY KEY,
                   username TEXT,
                   first_name TEXT,
                   joined_at INTEGER,
                   banned INTEGER DEFAULT 0
               )"""
        )


def add_user(user_id: int, username: str | None, first_name: str | None) -> None:
    with _conn() as c:
        c.execute(
            "INSERT OR IGNORE INTO users (id, username, first_name, joined_at) VALUES (?,?,?,?)",
            (user_id, username, first_name, int(time.time())),
        )


def is_banned(user_id: int) -> bool:
    with _conn() as c:
        row = c.execute("SELECT banned FROM users WHERE id=?", (user_id,)).fetchone()
    return bool(row and row[0])


def count_users() -> int:
    with _conn() as c:
        return c.execute("SELECT COUNT(*) FROM users").fetchone()[0]


def all_user_ids() -> list[int]:
    with _conn() as c:
        return [r[0] for r in c.execute("SELECT id FROM users WHERE banned=0")]
