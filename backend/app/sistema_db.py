"""Sistema DB — DB unico de auth + routing multi-tenant.

Tabelas usadas (ver sistema_v1.0.0.sql):
- users, empresas_routing, user_empresas, audit_log, schema_meta

Connection pool: ThreadedConnectionPool (1..5).
Se SISTEMA_DB_URL vazio, todas as funcoes levantam RuntimeError.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator, Optional

import psycopg2
import psycopg2.extras
from psycopg2.pool import ThreadedConnectionPool

from . import config


_pool: Optional[ThreadedConnectionPool] = None


def _ensure_pool() -> ThreadedConnectionPool:
    global _pool
    if _pool is not None:
        return _pool
    if not config.SISTEMA_DB_URL:
        raise RuntimeError(
            "SISTEMA_DB_URL nao configurado no .env (rota de auth/routing indisponivel)"
        )
    # client_encoding=UTF8 + lc_messages=C evita UnicodeDecodeError em servers WIN-1252.
    _pool = ThreadedConnectionPool(
        1,
        5,
        dsn=config.SISTEMA_DB_URL,
        client_encoding="UTF8",
        options="-c lc_messages=C",
    )
    return _pool


def is_available() -> bool:
    return bool(config.SISTEMA_DB_URL)


@contextmanager
def sistema_conn() -> Iterator[psycopg2.extensions.connection]:
    pool = _ensure_pool()
    conn = pool.getconn()
    try:
        yield conn
    finally:
        pool.putconn(conn)


def ping() -> dict[str, Any]:
    if not is_available():
        return {"ok": False, "error": "SISTEMA_DB_URL nao configurado"}
    try:
        with sistema_conn() as c, c.cursor() as cur:
            cur.execute("SELECT current_database(), version()")
            row = cur.fetchone()
            return {"ok": True, "db": row[0], "version": str(row[1]).split(",")[0]}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)}


# ---------- Routing ----------

_ROUTING_COLS = ("cnpj", "razao_social", "db_url", "schema_version", "flags", "ativo")


def fetch_routing(cnpj: str) -> Optional[dict[str, Any]]:
    """Retorna a rota da empresa (ou None se nao existir)."""
    with sistema_conn() as c, c.cursor() as cur:
        cur.execute(
            "SELECT cnpj, razao_social, db_url, schema_version, flags, ativo "
            "FROM empresas_routing WHERE cnpj = %s",
            (cnpj,),
        )
        row = cur.fetchone()
        if not row:
            return None
        return dict(zip(_ROUTING_COLS, row))


def list_empresas_ativas() -> list[dict[str, Any]]:
    with sistema_conn() as c, c.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            "SELECT cnpj, razao_social, schema_version, flags "
            "FROM empresas_routing WHERE ativo = TRUE ORDER BY razao_social"
        )
        return [dict(r) for r in cur.fetchall()]


# ---------- Users ----------


def fetch_user_by_email(email: str) -> Optional[dict[str, Any]]:
    with sistema_conn() as c, c.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            "SELECT id, email, password_hash, nome, ativo, super_admin "
            "FROM users WHERE lower(email) = lower(%s)",
            (email,),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def fetch_user_empresas(user_id: str) -> list[dict[str, Any]]:
    """Retorna lista de empresas que o user tem acesso."""
    with sistema_conn() as c, c.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            SELECT ue.cnpj, er.razao_social, ue.papel
              FROM user_empresas ue
              JOIN empresas_routing er ON er.cnpj = ue.cnpj
             WHERE ue.user_id = %s AND er.ativo = TRUE
             ORDER BY er.razao_social
            """,
            (user_id,),
        )
        return [dict(r) for r in cur.fetchall()]


def update_last_login(user_id: str) -> None:
    with sistema_conn() as c:
        with c.cursor() as cur:
            cur.execute("UPDATE users SET ultimo_login = now() WHERE id = %s", (user_id,))
        c.commit()


def write_audit(
    user_id: Optional[str],
    cnpj: Optional[str],
    acao: str,
    ip: Optional[str] = None,
    detalhes: Optional[dict] = None,
) -> None:
    """Insere uma linha em audit_log (best-effort, nao levanta)."""
    try:
        with sistema_conn() as c:
            with c.cursor() as cur:
                cur.execute(
                    "INSERT INTO audit_log (user_id, cnpj, acao, ip, detalhes) "
                    "VALUES (%s, %s, %s, %s, %s::jsonb)",
                    (user_id, cnpj, acao, ip, psycopg2.extras.Json(detalhes or {})),
                )
            c.commit()
    except Exception as e:  # noqa: BLE001
        print(f"[audit] falhou: {e}")
