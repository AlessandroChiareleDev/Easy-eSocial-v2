"""Migration runner V2 — schema-based (1 DB com schemas por empresa).

Estrutura:
  backend/migrations/
    sistema/sistema_v<X.Y.Z>.sql     -> aplicado em schema 'public' do DB sistema
    empresa/empresa_v<X.Y.Z>.sql     -> aplicado em schema <NOME> dentro do mesmo DB
    _legacy/*.sql                    -> migrations antigas pre-consolidacao (nao roda)

F5 (schema-based): com --schema NOME, faz string replace 'public.' -> '<NOME>.'
no SQL antes de executar, garantindo isolamento logico entre empresas.

Idempotencia: consulta {schema}.schema_meta(target, version) ANTES de aplicar.

Uso:
    python -m app.migrate apply --target sistema --version 1.0.0 --dsn <DSN>
    python -m app.migrate apply --target empresa --version 1.0.0 --schema appa --dsn <DSN>
    python -m app.migrate status --schema appa --dsn <DSN>
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


def _has_schema_meta(cur, schema: str = "public") -> bool:
    cur.execute(
        "SELECT 1 FROM information_schema.tables "
        "WHERE table_schema=%s AND table_name='schema_meta'",
        (schema,),
    )
    return cur.fetchone() is not None


def _already_applied(cur, target: str, version: str, schema: str = "public") -> bool:
    if not _has_schema_meta(cur, schema):
        return False
    cur.execute(
        f"SELECT 1 FROM {schema}.schema_meta WHERE target=%s AND version=%s",
        (target, version),
    )
    return cur.fetchone() is not None


def _validate_schema_name(name: str) -> None:
    """Garante que o schema name e seguro pra interpolacao (so [a-z0-9_])."""
    import re

    if not re.fullmatch(r"[a-z][a-z0-9_]{0,62}", name):
        raise ValueError(
            f"schema name invalido: {name!r}. Deve ser [a-z][a-z0-9_]* (max 63 chars)"
        )


def _rewrite_sql_for_schema(sql_text: str, schema: str) -> str:
    """Substitui 'public.' por '<schema>.' no SQL e remove SET search_path=''."""
    _validate_schema_name(schema)
    rewritten = sql_text.replace("public.", f"{schema}.")
    # O dump tem essa linha que forca search_path vazio. Mantemos por seguranca.
    return rewritten


def cmd_apply(args: argparse.Namespace) -> int:
    sql_file = _resolve_sql(args.target, args.version)
    conn_kwargs = _build_conn_kwargs(args.db, args.dsn)
    schema = args.schema or "public"
    _validate_schema_name(schema)

    print(f"[INFO] aplicando {sql_file.name}")
    print(f"[INFO] target={args.target} version={args.version} schema={schema}")

    conn = _connect(conn_kwargs)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT current_database()")
            row = cur.fetchone()
            print(f"[INFO] conectado em DB={row[0] if row else '?'}")

            # Cria schema se nao for public
            if schema != "public":
                cur.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema}"')
                conn.commit()

            if _already_applied(cur, args.target, args.version, schema):
                print(f"[SKIP] {args.target} v{args.version} ja aplicado em schema={schema}.")
                return 0

        sql_text = sql_file.read_text(encoding="utf-8")
        if schema != "public":
            sql_text = _rewrite_sql_for_schema(sql_text, schema)

        with conn.cursor() as cur:
            cur.execute(sql_text)
        conn.commit()
        print(f"[OK] {args.target} v{args.version} aplicado em schema={schema}.")
        return 0
    except Exception as e:  # noqa: BLE001
        conn.rollback()
        print(f"[ERRO] falha: {e}")
        return 1
    finally:
        conn.close()


def cmd_status(args: argparse.Namespace) -> int:
    conn_kwargs = _build_conn_kwargs(args.db, args.dsn)
    schema = args.schema or "public"
    _validate_schema_name(schema)
    conn = _connect(conn_kwargs)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT current_database()")
            row = cur.fetchone()
            print(f"DB: {row[0] if row else '?'}  schema: {schema}")

            if not _has_schema_meta(cur, schema):
                print(f"schema_meta: AUSENTE em {schema} (nenhuma migration aplicada)")
                return 0

            if args.target:
                cur.execute(
                    f"SELECT target, version, aplicado_em FROM {schema}.schema_meta "
                    "WHERE target=%s ORDER BY aplicado_em",
                    (args.target,),
                )
            else:
                cur.execute(
                    f"SELECT target, version, aplicado_em FROM {schema}.schema_meta "
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
    p_apply.add_argument(
        "--schema",
        default=None,
        help="schema target (sed 'public.' -> '<schema>.'). Default: public",
    )

    p_status = sub.add_parser("status", help="lista versoes aplicadas")
    p_status.add_argument("--target", default=None, choices=["sistema", "empresa"])
    p_status.add_argument("--db", default=None)
    p_status.add_argument("--dsn", default=None)
    p_status.add_argument("--schema", default=None)

    args = p.parse_args()
    if args.cmd == "apply":
        return cmd_apply(args)
    if args.cmd == "status":
        return cmd_status(args)
    p.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
