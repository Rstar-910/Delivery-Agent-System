"""
auth.py — Authentication endpoints and role-based access control (RBAC).

Session design
--------------
Tokens are cryptographically random 32-byte URL-safe strings (secrets.token_urlsafe).
They are stored in the `sessions` SQLite table with an expiry timestamp (24 h TTL).
This means sessions survive API server restarts — a live-demo-safe property that an
in-memory store would not provide.

Passwords are hashed using the `bcrypt` package directly (not via passlib) because
passlib 1.7.4 is incompatible with bcrypt 4+ (missing __about__ attribute). Using
bcrypt directly is the recommended fallback and is simpler.

Role guards (require_customer, require_courier, require_admin) are FastAPI Depends()
callables that wrap _get_current_user; routers import only the guard they need, which
keeps the coupling minimal.
"""

from __future__ import annotations

import datetime
import secrets

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .database import get_db
from .models import LoginRequest, TokenResponse

# ── Constants ────────────────────────────────────────────────────────────────

TOKEN_TTL_HOURS = 24

# ── Password hashing (bcrypt directly — avoids passlib/bcrypt version issues) ─

def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


# ── Router ───────────────────────────────────────────────────────────────────

router = APIRouter(prefix="/auth", tags=["Auth"])
_bearer = HTTPBearer()


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate and receive a Bearer token",
)
def login(req: LoginRequest):
    """
    Validates credentials against the `users` table and issues a session token
    stored in the `sessions` table (SQLite-backed, 24 h TTL).
    """
    with get_db() as conn:
        row = conn.execute(
            "SELECT id, username, password_hash, role FROM users WHERE username = ?",
            (req.username,),
        ).fetchone()

        if not row or not verify_password(req.password, row["password_hash"]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password",
            )

        token = secrets.token_urlsafe(32)
        expires_at = datetime.datetime.utcnow() + datetime.timedelta(hours=TOKEN_TTL_HOURS)

        conn.execute(
            "INSERT INTO sessions(token, user_id, role, expires_at) VALUES(?, ?, ?, ?)",
            (token, row["id"], row["role"], expires_at.isoformat()),
        )

        return TokenResponse(token=token, role=row["role"], username=row["username"])


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke the current Bearer token",
)
def logout(credentials: HTTPAuthorizationCredentials = Depends(_bearer)):
    """Deletes the session row, immediately invalidating the token."""
    with get_db() as conn:
        conn.execute("DELETE FROM sessions WHERE token = ?", (credentials.credentials,))


# ── Internal session resolver ─────────────────────────────────────────────────

def _get_current_user(credentials: HTTPAuthorizationCredentials = Depends(_bearer)) -> dict:
    """
    Resolves a Bearer token to a user session dict {user_id, role}.
    Deletes expired tokens on the fly so they don't accumulate.
    """
    token = credentials.credentials
    with get_db() as conn:
        row = conn.execute(
            "SELECT user_id, role, expires_at FROM sessions WHERE token = ?",
            (token,),
        ).fetchone()

        if not row:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token — please log in again",
            )

        if datetime.datetime.fromisoformat(row["expires_at"]) < datetime.datetime.utcnow():
            conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired — please log in again",
            )

        return {"user_id": row["user_id"], "role": row["role"]}


# ── Role guards (import these in routers) ────────────────────────────────────

def require_customer(session: dict = Depends(_get_current_user)) -> dict:
    if session["role"] != "customer":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Customer role required",
        )
    return session


def require_courier(session: dict = Depends(_get_current_user)) -> dict:
    if session["role"] != "courier":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Courier role required",
        )
    return session


def require_admin(session: dict = Depends(_get_current_user)) -> dict:
    if session["role"] != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )
    return session
