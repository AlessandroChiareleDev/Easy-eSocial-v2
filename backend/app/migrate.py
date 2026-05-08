"""Aplica todas as SQLs em backend/migrations/ na ordem alfabética.

Idempotente: cada SQL usa IF NOT EXISTS / DO $$ guards.

Uso:
    python -m app.migrate
"""
from __future__ import annotations

import sys
from pathlib import Path

from . import db

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"


def main() -> int:
    if not MIGRATIONS_DIR.exists():
        print(f"[ERRO] pasta de migrations não existe: {MIGRATIONS_DIR}")
        return 2

    files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    if not files:
        print("[INFO] nenhuma migration .sql encontrada.")
        return 0

    ping = db.ping()
    if not ping.get("ok"):
        print(f"[ERRO] não conectou no Postgres: {ping.get('error')}")
        return 1
    print(f"[OK] conectado em {ping['db']} ({ping['version']})")

    conn = db.connect()
    try:
        for sql_file in files:
            print(f"-> aplicando {sql_file.name} ...")
            sql = sql_file.read_text(encoding="utf-8")
            with conn.cursor() as cur:
                cur.execute(sql)
            conn.commit()
            print(f"   OK")
    except Exception as e:  # noqa: BLE001
        conn.rollback()
        print(f"[ERRO] falha aplicando migrations: {e}")
        return 1
    finally:
        conn.close()

    print("[OK] todas as migrations aplicadas.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
