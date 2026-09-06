"""
main.py — FastAPI application entry point for the Delivery Agent System API.

Start the server from the repository root:
    uvicorn api.main:app --reload --port 8000

Interactive API docs (Swagger UI):
    http://localhost:8000/docs

CORS policy: all origins are permitted. This is a deliberate demo-scope decision.
In a production deployment, replace allow_origins=["*"] with the specific frontend
origin (e.g., ["https://yourapp.com"]) to prevent cross-origin token theft.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .auth import router as auth_router
from .database import init_db
from .routers.admin import router as admin_router
from .routers.courier import router as courier_router
from .routers.customer import router as customer_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialise DB schema (idempotent) before the server starts accepting requests."""
    init_db()
    yield


app = FastAPI(
    title="Delivery Agent System API",
    description=(
        "REST API layer over the Delivery Agent System's SQLite persistence layer. "
        "Shares the same `delivery_agent.db` file as the C++ console application — "
        "a multi-language system with a common persistence layer.\n\n"
        "**Authentication**: POST `/auth/login` → receive Bearer token → include as "
        "`Authorization: Bearer <token>` on subsequent requests.\n\n"
        "**Default credentials**: customer1 / courier1 / admin1 — all with password `pass123`. "
        "Run `python3 -m api.seed_users` once to create them."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS ─────────────────────────────────────────────────────────────────────
# allow_origins=["*"] is appropriate for this demo project.
# Restrict to specific origins in a production deployment.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(auth_router)
app.include_router(customer_router)
app.include_router(courier_router)
app.include_router(admin_router)


@app.get("/", tags=["Health"], summary="Health check")
def health():
    """Returns a simple liveness response."""
    return {"status": "ok", "service": "Delivery Agent System API", "version": "1.0.0"}
