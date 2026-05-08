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


_EMPRESA_SCHEMA = {
    APPA_ID: "appa",
    SOLUCOES_ID: "solucoes",
}


def get_db_config_for_empresa(empresa_id: Optional[int]) -> dict:
    """Retorna a config psycopg2 com search_path setado pelo schema da empresa.

    APPA e SOLUCOES vivem ambas no mesmo Supabase (schemas separados).
    Injetamos `options=-csearch_path=<schema>,public` para que queries
    sem schema explicito caiam no tenant correto.
    """
    eid = int(empresa_id) if empresa_id is not None else SOLUCOES_ID
    if config.SUPABASE_DB_CONFIG is None:
        raise RuntimeError(
            "SUPABASE_DB_CONFIG nao configurado (.env). APPA/SOLUCOES vivem no Supabase."
        )
    schema = _EMPRESA_SCHEMA.get(eid, "public")
    cfg = dict(config.SUPABASE_DB_CONFIG)  # copia rasa pra nao mutar global
    cfg["options"] = f"-csearch_path={schema},public"
    return cfg


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
# API NOVA (por CNPJ) — F5 schema-based multi-tenant
# Pool unico no DB sistema; cada empresa = schema diferente.
# Switching feito via SET search_path em cada conexao adquirida.
# ============================================================

import re

_VALID_SCHEMA_RE = re.compile(r"^[a-z][a-z0-9_]{0,62}$")


def _validate_schema(name: str) -> str:
    if not _VALID_SCHEMA_RE.fullmatch(name):
        raise ValueError(f"schema_name invalido: {name!r}")
    return name


def get_schema_for_cnpj(cnpj: str) -> str:
    """Resolve o schema da empresa via empresas_routing."""
    from . import sistema_db

    rota = sistema_db.fetch_routing(cnpj)
    if not rota:
        raise PermissionError(f"empresa CNPJ={cnpj} nao cadastrada em empresas_routing")
    if not rota.get("ativo"):
        raise PermissionError(f"empresa CNPJ={cnpj} esta desativada")
    schema = rota.get("schema_name")
    if not schema:
        raise RuntimeError(f"empresas_routing.schema_name vazio para CNPJ={cnpj}")
    return _validate_schema(schema)


@contextmanager
def empresa_conn(cnpj: str) -> Iterator[psycopg2.extensions.connection]:
    """Context manager: conexao do pool sistema com search_path da empresa.

    Ao final, faz RESET search_path antes de devolver ao pool.
    """
    from . import sistema_db

    schema = get_schema_for_cnpj(cnpj)
    pool = sistema_db._ensure_pool()  # noqa: SLF001 — reuso intencional
    conn = pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(f'SET search_path TO "{schema}", public')
        yield conn
    finally:
        try:
            with conn.cursor() as cur:
                cur.execute("RESET search_path")
            if not conn.autocommit:
                conn.rollback()  # garante estado limpo
        except Exception:  # noqa: BLE001
            pass
        pool.putconn(conn)


def close_all_pools() -> None:
    """Mantido pra compat. Pool e gerenciado por sistema_db agora."""
    return None

