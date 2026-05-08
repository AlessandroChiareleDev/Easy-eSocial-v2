"""FastAPI app — Explorador de Arquivos."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
import psycopg2
import psycopg2.extras

from . import config, db, sistema_db
from .auth_routes import router as auth_router
from .explorador import router as explorador_router
from .middlewares import auth_middleware, tenant_middleware
from .timeline import router as timeline_router
from .timeline import download_router as timeline_download_router
from .timeline import s1210_repo_router

app = FastAPI(
    title="Easy-eSocial-v2 — Explorador",
    description="Backend do Explorador de Arquivos (multi-tenant V2).",
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Auth + tenant middleware (opt-in: so habilita se JWT_SECRET estiver no .env).
# Ordem: tenant depois de auth (auth roda primeiro pq foi adicionado depois).
if config.JWT_SECRET:
    app.add_middleware(BaseHTTPMiddleware, dispatch=tenant_middleware)
    app.add_middleware(BaseHTTPMiddleware, dispatch=auth_middleware)

app.include_router(auth_router)
app.include_router(explorador_router)
app.include_router(timeline_router)
app.include_router(timeline_download_router)
app.include_router(s1210_repo_router)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "easy-esocial-v2-explorador",
        "version": app.version,
    }


@app.get("/api/empresas")
def listar_empresas():
    """Lista as empresas do master_empresas no Supabase (V1).

    APPA (id=1)     -> Supabase
    SOLUCOES (id=2) -> Local
    """
    from . import tenant

    empresas: list[dict] = []
    # 1) tenta listar do Supabase (master)
    if config.SUPABASE_DB_CONFIG is not None:
        try:
            with psycopg2.connect(**config.SUPABASE_DB_CONFIG) as conn:  # type: ignore[arg-type]
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as c:
                    c.execute(
                        """
                        SELECT id, nome, cnpj, ativo
                          FROM master_empresas
                         WHERE ativo IS TRUE
                         ORDER BY id
                        """
                    )
                    rows = c.fetchall()
            for r in rows:
                eid = int(r["id"])
                empresas.append({
                    "id": eid,
                    "nome": r["nome"],
                    "cnpj": r["cnpj"],
                    "ativo": True,
                    "tem_dados": True,
                    "envios_count": 0,
                    "db_kind": tenant.db_kind_for_empresa(eid),
                })
        except Exception as e:  # noqa: BLE001
            print(f"[empresas] Supabase indisponivel: {e}")

    # 2) garante que SOLUCOES (id=2) sempre apareca, mesmo offline do supabase
    if not any(e["id"] == 2 for e in empresas):
        try:
            with db.cursor() as c:
                c.execute("SELECT nome, cnpj FROM master_empresas WHERE id=1")
                row = c.fetchone()
            if row:
                empresas.append({
                    "id": 2,
                    "nome": row["nome"],
                    "cnpj": row["cnpj"],
                    "ativo": True,
                    "tem_dados": True,
                    "envios_count": 0,
                    "db_kind": "local",
                })
        except Exception as e:  # noqa: BLE001
            print(f"[empresas] fallback local falhou: {e}")
    empresas.sort(key=lambda x: x["id"])
    return {"empresas": empresas}


@app.get("/health/db")
def health_db():
    return db.ping()


@app.get("/health/sistema")
def health_sistema():
    return sistema_db.ping()
