"""Roteamento multi-tenant para o V2.

Mapeamento (compativel com V1):
  empresa_id=1  -> APPA      -> Supabase  (SUPABASE_DB_CONFIG)
  empresa_id=2  -> SOLUCOES  -> Local easy_social_solucoes (DB_CONFIG)

Convencao IMPORTANTE: dentro do banco LOCAL `easy_social_solucoes`, a
coluna `empresa_id` foi cadastrada com valor 1 (id interno do banco).
Por isso, ao receber empresa_id=2 (SOLUCOES) na API, traduzimos para
internal_empresa_id=1 ao executar queries no banco local.
"""
from __future__ import annotations

from typing import Optional

import psycopg2

from . import config


APPA_ID = 1
SOLUCOES_ID = 2


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
