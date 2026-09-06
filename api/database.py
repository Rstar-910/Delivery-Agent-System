"""
database.py — Shared SQLite access layer for the FastAPI server.

Connects to the same delivery_agent.db used by the C++ console application.
WAL (Write-Ahead Logging) journal mode is enabled on every connection so that
concurrent reads from both processes do not block each other, and concurrent
writes are serialised safely by SQLite's file-locking mechanism with a 10-second
timeout before raising OperationalError.

Two data-access implementations (this file and Source/common.cpp) intentionally
co-exist: the C++ app predates the API layer and was kept intact to preserve the
original project's story. The shared schema is the single source of truth — both
layers speak to the same tables. This is a deliberate engineering tradeoff for
scope reasons, not an oversight.
"""

import sqlite3
import pathlib
from contextlib import contextmanager

# Resolve DB path relative to this file so the server can be started from any cwd.
DB_PATH = pathlib.Path(__file__).parent.parent / "delivery_agent.db"

# ────────────────────────────────────────────────
# Schema — extends the C++ schema with users and sessions tables.
# The orders and courier_companies tables are kept identical to common.cpp.
# ────────────────────────────────────────────────
_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS orders (
    order_id       INTEGER PRIMARY KEY,
    customer_name  TEXT    NOT NULL,
    address        TEXT    NOT NULL,
    status         TEXT    NOT NULL,
    scheduled_date TEXT    NOT NULL,
    created_at     DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_orders_customer ON orders(customer_name);
CREATE INDEX IF NOT EXISTS idx_orders_status   ON orders(status);

CREATE TABLE IF NOT EXISTS courier_companies (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    company_name    TEXT    NOT NULL,
    contact_number  TEXT    NOT NULL,
    location        TEXT    NOT NULL,
    packaging_price REAL    NOT NULL,
    discount        REAL    NOT NULL,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT    NOT NULL UNIQUE,
    password_hash TEXT    NOT NULL,
    role          TEXT    NOT NULL CHECK(role IN ('customer', 'courier', 'admin')),
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sessions (
    token      TEXT     PRIMARY KEY,
    user_id    INTEGER  NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role       TEXT     NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    expires_at DATETIME NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
"""


@contextmanager
def get_db():
    """
    Context manager that opens a SQLite connection, enables WAL mode and
    foreign keys, yields the connection, then commits (or rolls back on error)
    and closes.

    WAL mode note: PRAGMA journal_mode=WAL is idempotent and safe to issue on
    every connection. It allows one writer and multiple concurrent readers,
    which is exactly the scenario when the C++ console app and the FastAPI
    server both access delivery_agent.db simultaneously.
    """
    conn = sqlite3.connect(str(DB_PATH), timeout=10, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """
    Create all tables if they do not already exist.
    Called once at FastAPI startup (see main.py lifespan handler).
    executescript() issues an implicit COMMIT before running, which is
    intentional — schema DDL should not be part of a user transaction.
    """
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.executescript(_SCHEMA_SQL)
    conn.close()
