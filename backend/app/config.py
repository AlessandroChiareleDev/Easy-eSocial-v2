"""Configuração centralizada — lê .env."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# .env fica em backend/.env
_BACKEND_DIR = Path(__file__).resolve().parent.parent
load_dotenv(_BACKEND_DIR / ".env")


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


# --- Postgres LOCAL (SOLUCOES) ---
DB_HOST = _env("LOCAL_DB_HOST", "localhost")
DB_PORT = int(_env("LOCAL_DB_PORT", "5432"))
DB_NAME = _env("LOCAL_DB_NAME", "easy_social_solucoes")
DB_USER = _env("LOCAL_DB_USER", "easy_social_user")
DB_PASSWORD = _env("LOCAL_DB_PASSWORD", "")
DB_SSL = _env("LOCAL_DB_SSL", "false").lower() == "true"

DB_CONFIG: dict[str, object] = {
    "host": DB_HOST,
    "port": DB_PORT,
    "database": DB_NAME,
    "user": DB_USER,
    "password": DB_PASSWORD,
}
if DB_SSL:
    DB_CONFIG["sslmode"] = "require"


# --- Supabase (APPA / master multi-tenant) ---
SUPABASE_DB_HOST = _env("SUPABASE_DB_HOST", "")
SUPABASE_DB_PORT = int(_env("SUPABASE_DB_PORT", "5432") or "5432")
SUPABASE_DB_NAME = _env("SUPABASE_DB_NAME", "postgres")
SUPABASE_DB_USER = _env("SUPABASE_DB_USER", "")
SUPABASE_DB_PASSWORD = _env("SUPABASE_DB_PASSWORD", "")
SUPABASE_DB_SSL = _env("SUPABASE_DB_SSL", "true").lower() == "true"

SUPABASE_DB_CONFIG: dict[str, object] | None = None
if SUPABASE_DB_HOST and SUPABASE_DB_USER:
    SUPABASE_DB_CONFIG = {
        "host": SUPABASE_DB_HOST,
        "port": SUPABASE_DB_PORT,
        "database": SUPABASE_DB_NAME,
        "user": SUPABASE_DB_USER,
        "password": SUPABASE_DB_PASSWORD,
    }
    if SUPABASE_DB_SSL:
        SUPABASE_DB_CONFIG["sslmode"] = "require"


# --- API ---
API_HOST = _env("API_HOST", "127.0.0.1")
API_PORT = int(_env("API_PORT", "8001"))
CORS_ORIGINS = [o.strip() for o in _env("CORS_ORIGINS", "http://localhost:5173").split(",") if o.strip()]


# --- Upload ---
MAX_UPLOAD_BYTES = int(_env("MAX_UPLOAD_BYTES", str(3 * 1024 * 1024 * 1024)))  # 3 GB
