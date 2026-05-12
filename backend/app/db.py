"""Conexao Postgres simples - psycopg2.

Roteamento multi-tenant: aceita `empresa_id` (default = APPA=1) e usa
tenant.get_db_config_for_empresa para apontar pro Supabase com search_path
correto. Sem `empresa_id` = APPA (mantem compat com chamadas legadas).
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator, Optional

import psycopg2
import psycopg2.extras


def _resolve_cfg(empresa_id):
    # Import local pra evitar ciclo
    from . import tenant
    eid = empresa_id if empresa_id is not None else tenant.APPA_ID
    return tenant.get_db_config_for_empresa(eid)


def connect(empresa_id: Optional[int] = None):
    """Abre uma nova conexao. Caller eh responsavel por fechar.

    IMPORTANTE: o pooler do Supabase (pgbouncer transaction mode) NAO
    propaga o `options=-csearch_path=...` corretamente entre conexoes.
    Por isso, alem do startup option, executamos SET search_path
    explicitamente apos conectar pra garantir o tenant certo.
    """
    from . import tenant as _tenant
    cfg = _resolve_cfg(empresa_id)
    conn = psycopg2.connect(**cfg)
    eid = empresa_id if empresa_id is not None else _tenant.APPA_ID
    schema = _tenant._EMPRESA_SCHEMA.get(int(eid), "public")
    try:
        with conn.cursor() as _c:
            _c.execute(f'SET search_path TO "{schema}", public')
        conn.commit()
    except Exception:
        conn.close()
        raise
    return conn


@contextmanager
def cursor(commit: bool = False, empresa_id: Optional[int] = None) -> Iterator[psycopg2.extensions.cursor]:
    """Context manager: yield cursor, fecha conexao no fim.

    `empresa_id` roteia o tenant (default APPA). `commit=True` para escritas.
    """
    conn = connect(empresa_id)
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
    """Testa conexao. Retorna {ok: bool, db: str, version: str}."""
    try:
        with cursor() as cur:
            cur.execute("SELECT current_database() AS db, version() AS v")
            row = cur.fetchone()
            return {"ok": True, "db": row["db"], "version": row["v"].split(",")[0]}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)}
