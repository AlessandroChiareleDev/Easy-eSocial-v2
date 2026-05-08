"""Roteamento multi-tenant para o V2.

Mapeamento (compativel com V1):
  empresa_id=1  -> APPA      -> Supabase  (SUPABASE_DB_CONFIG)
  empresa_id=2  -> SOLUCOES  -> Local easy_social_solucoes (DB_CONFIG)

Convencao IMPORTANTE: dentro do banco LOCAL `easy_social_solucoes`, a
coluna `empresa_id` foi cadastrada com valor 1 (id interno do banco).
Por isso, ao receber empresa_id=2 (SOLUCOES) na API, traduzimos para
internal_empresa_id=1 ao executar queries no banco local.

==========================================================================
F3 — Multi-tenant runtime por CNPJ:
  empresa_conn(cnpj) usa empresas_routing.db_url via sistema_db.fetch_routing.
  Cada CNPJ tem seu proprio pool. APIs novas devem migrar pra essa interface.
==========================================================================
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator, Optional

import psycopg2
from psycopg2.pool import ThreadedConnectionPool

from . import config


APPA_ID = 1
SOLUCOES_ID = 2


# ============================================================
# API LEGADA (por empresa_id) — mantida pra compat com V1
# ============================================================


def get_db_config_for_empresa(empresa_id: Optional[int]) -> dict:
    eid = int(empresa_id) if empresa_id is not None else SOLUCOES_ID
    if eid == APPA_ID:
        if config.SUPABASE_DB_CONFIG is None:
            raise RuntimeError(
                "SUPABASE_DB_CONFIG nao configurado (.env). Empresa 1 (APPA) precisa do Supabase."
            )
        return config.SUPABASE_DB_CONFIG  # type: ignore[return-value]
    # SOLUCOES e demais futuras -> local
    return config.DB_CONFIG  # type: ignore[return-value]


def connect_for_empresa(empresa_id: Optional[int]):
    cfg = get_db_config_for_empresa(empresa_id)
    return psycopg2.connect(**cfg)


def db_kind_for_empresa(empresa_id: Optional[int]) -> str:
    cfg = get_db_config_for_empresa(empresa_id)
    host = str(cfg.get("host") or "").lower()
    return "supabase" if "supabase" in host else "local"


def internal_empresa_id(empresa_id: Optional[int]) -> int:
    """Traduz empresa_id externo para o id interno usado nas tabelas do banco.

    No banco local SOLUCOES, a row em master_empresas/empresa_zips_brutos
    foi cadastrada com id=1, mas o V1/front usa empresa_id=2 para
    referir-se a SOLUCOES. APPA (Supabase) usa id=1 internamente tambem.
    """
    eid = int(empresa_id) if empresa_id is not None else SOLUCOES_ID
    if eid == SOLUCOES_ID:
        return 1
    return eid


# ============================================================
# API NOVA (por CNPJ) — F3 multi-tenant runtime
# ============================================================

_pools_by_cnpj: dict[str, ThreadedConnectionPool] = {}


def get_pool(cnpj: str) -> ThreadedConnectionPool:
    """Retorna (ou cria) um pool por CNPJ usando empresas_routing.db_url."""
    if cnpj in _pools_by_cnpj:
        return _pools_by_cnpj[cnpj]
    # Lazy import pra nao quebrar quando SISTEMA_DB_URL nao esta setado
    from . import sistema_db

    rota = sistema_db.fetch_routing(cnpj)
    if not rota:
        raise PermissionError(f"empresa CNPJ={cnpj} nao cadastrada em empresas_routing")
    if not rota.get("ativo"):
        raise PermissionError(f"empresa CNPJ={cnpj} esta desativada")
    db_url = rota.get("db_url")
    if not db_url:
        raise RuntimeError(f"empresas_routing.db_url vazio para CNPJ={cnpj}")
    pool = ThreadedConnectionPool(1, 10, dsn=db_url)
    _pools_by_cnpj[cnpj] = pool
    return pool


@contextmanager
def empresa_conn(cnpj: str) -> Iterator[psycopg2.extensions.connection]:
    """Context manager: abre conexao no DB da empresa (CNPJ)."""
    pool = get_pool(cnpj)
    conn = pool.getconn()
    try:
        yield conn
    finally:
        pool.putconn(conn)


def close_all_pools() -> None:
    """Fecha todos os pools (uso em shutdown)."""
    for cnpj, pool in list(_pools_by_cnpj.items()):
        try:
            pool.closeall()
        except Exception:  # noqa: BLE001
            pass
        _pools_by_cnpj.pop(cnpj, None)

