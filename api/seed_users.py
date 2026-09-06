"""
seed_users.py — Populates default users in delivery_agent.db.

Run once from the repository root:
    python3 -m api.seed_users

Idempotent: skips users that already exist, so it is safe to re-run.

Default credentials:
    customer1 / pass123  (role: customer)
    courier1  / pass123  (role: courier)
    admin1    / pass123  (role: admin)
"""

from __future__ import annotations

from .auth import hash_password
from .database import get_db, init_db

_DEFAULT_USERS: list[tuple[str, str, str]] = [
    ("customer1", "pass123", "customer"),
    ("courier1",  "pass123", "courier"),
    ("admin1",    "pass123", "admin"),
]


def seed() -> None:
    print("Initialising database schema...")
    init_db()

    print("Seeding default users...")
    with get_db() as conn:
        for username, password, role in _DEFAULT_USERS:
            existing = conn.execute(
                "SELECT id FROM users WHERE username = ?", (username,)
            ).fetchone()

            if existing:
                print(f"  [skip] '{username}' already exists")
                continue

            conn.execute(
                "INSERT INTO users(username, password_hash, role) VALUES(?, ?, ?)",
                (username, hash_password(password), role),
            )
            print(f"  [ok]   '{username}' ({role}) created")

    print("\nDone. Default credentials: password is 'pass123' for all accounts.")
    print("  Customer : customer1")
    print("  Courier  : courier1")
    print("  Admin    : admin1")


if __name__ == "__main__":
    seed()
