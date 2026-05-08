"""Migration runner V2 — schema unico (sistema + empresa).

Estrutura:
  backend/migrations/
    sistema/sistema_v<X.Y.Z>.sql     -> aplicado no DB de sistema (auth + routing)
    empresa/empresa_v<X.Y.Z>.sql     -> aplicado em cada DB de empresa (1 por CNPJ)
    _legacy/*.sql                    -> migrations antigas pre-consolidacao (nao roda)

Idempotencia: o runner consulta public.schema_meta(target, version) ANTES de aplicar.
Se ja existe, pula. SQL nao precisa ser idempotente em ALTER TABLE ADD CONSTRAINT.

Uso:
    python -m app.migrate apply --target sistema --version 1.0.0
    python -m app.migrate apply --target empresa --version 1.0.0 --db <db_name>
    python -m app.migrate apply --target empresa --version 1.0.0 --dsn <conn_string>
    python -m app.migrate status [--target sistema|empresa] [--db <db_name>]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import psycopg2

from . import config

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"


def _build_conn_kwargs(db_override: str | None, dsn: str | None) -> dict[str, Any] | str:
    if dsn:
        return dsn
    cfg = dict(config.DB_CONFIG)
    if db_override:
        cfg["database"] = db_override
    return cfg


def _connect(conn_kwargs: dict[str, Any] | str):
    if isinstance(conn_kwargs, str):
        return psycopg2.connect(conn_kwargs)
    return psycopg2.connect(**conn_kwargs)


def _resolve_sql(target: str, version: str) -> Path:
    if target not in ("sistema", "empresa"):
        raise ValueError(f"target invalido: {target}")
    f = MIGRATIONS_DIR / target / f"{target}_v{version}.sql"
    if not f.exists():
        raise FileNotFoundError(f"migration nao encontrada: {f}")
    return f


def _has_schema_meta(cur) -> bool:
    cur.execute(
        "SELECT 1 FROM information_schema.tables "
        "WHERE table_schema='public' AND table_name='schema_meta'"
    )
    return cur.fetchone() is not None


def _already_applied(cur, target: str, version: str) -> bool:
    if not _has_schema_meta(cur):
        return False
    cur.execute(
        "SELECT 1 FROM public.schema_meta WHERE target=%s AND version=%s",
        (target, version),
    )
    return cur.fetchone() is not None


def cmd_apply(args: argparse.Namespace) -> int:
    sql_file = _resolve_sql(args.target, args.version)
    conn_kwargs = _build_conn_kwargs(args.db, args.dsn)

    print(f"[INFO] aplicando {sql_file.name}")
    print(f"[INFO] target={args.target} version={args.version}")

    conn = _connect(conn_kwargs)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT current_database()")
            row = cur.fetchone()
            print(f"[INFO] conectado em DB={row[0] if row else '?'}")

            if _already_applied(cur, args.target, args.version):
                print(f"[SKIP] {args.target} v{args.version} ja aplicado.")
                return 0

        sql_text = sql_file.read_text(encoding="utf-8")
        with conn.cursor() as cur:
            cur.execute(sql_text)
        conn.commit()
        print(f"[OK] {args.target} v{args.version} aplicado.")
        return 0
    except Exception as e:  # noqa: BLE001
        conn.rollback()
        print(f"[ERRO] falha: {e}")
        return 1
    finally:
        conn.close()


def cmd_status(args: argparse.Namespace) -> int:
    conn_kwargs = _build_conn_kwargs(args.db, args.dsn)
    conn = _connect(conn_kwargs)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT current_database()")
            row = cur.fetchone()
            print(f"DB: {row[0] if row else '?'}")

            if not _has_schema_meta(cur):
                print("schema_meta: AUSENTE (nenhuma migration aplicada)")
                return 0

            if args.target:
                cur.execute(
                    "SELECT target, version, aplicado_em FROM public.schema_meta "
                    "WHERE target=%s ORDER BY aplicado_em",
                    (args.target,),
                )
            else:
                cur.execute(
                    "SELECT target, version, aplicado_em FROM public.schema_meta "
                    "ORDER BY target, aplicado_em"
                )
            rows = cur.fetchall()
            if not rows:
                print("(nenhuma versao registrada)")
                return 0
            print(f"{'target':<10} {'version':<10} aplicado_em")
            for t, v, ts in rows:
                print(f"{t:<10} {v:<10} {ts}")
        return 0
    finally:
        conn.close()


def main() -> int:
    p = argparse.ArgumentParser(prog="migrate")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_apply = sub.add_parser("apply", help="aplica uma migration")
    p_apply.add_argument("--target", required=True, choices=["sistema", "empresa"])
    p_apply.add_argument("--version", required=True, help="ex: 1.0.0")
    p_apply.add_argument("--db", default=None, help="override do nome do DB (usa LOCAL_DB_* do .env)")
    p_apply.add_argument("--dsn", default=None, help="DSN completo (override total)")

    p_status = sub.add_parser("status", help="lista versoes aplicadas")
    p_status.add_argument("--target", default=None, choices=["sistema", "empresa"])
    p_status.add_argument("--db", default=None)
    p_status.add_argument("--dsn", default=None)

    args = p.parse_args()
    if args.cmd == "apply":
        return cmd_apply(args)
    if args.cmd == "status":
        return cmd_status(args)
    p.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
