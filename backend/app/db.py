"""Conexão Postgres simples — psycopg2."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

import psycopg2
import psycopg2.extras

from . import config


def connect():
    """Abre uma nova conexão. Caller é responsável por fechar."""
    return psycopg2.connect(**config.DB_CONFIG)


@contextmanager
def cursor(commit: bool = False) -> Iterator[psycopg2.extensions.cursor]:
    """Context manager: yield cursor, fecha conexão no fim.

    Use commit=True para escritas.
    """
    conn = connect()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            yield cur
            if commit:
                conn.commit()
        finally:
            cur.close()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def ping() -> dict:
    """Testa conexão. Retorna {ok: bool, db: str, version: str}."""
    try:
        with cursor() as cur:
            cur.execute("SELECT current_database() AS db, version() AS v")
            row = cur.fetchone()
            return {"ok": True, "db": row["db"], "version": row["v"].split(",")[0]}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)}
