"""Middlewares: auth + tenant.

auth_middleware:
  - Pula rotas publicas: /api/auth/login, /health*, /docs, /openapi.json
  - Exige `Authorization: Bearer <jwt>`. Coloca payload em request.state.user.

tenant_middleware:
  - Le `X-Empresa-CNPJ` (opcional). Se presente e usuario nao for super_admin,
    valida que CNPJ esta na lista de empresas do JWT. Coloca em request.state.cnpj_ativo.

NOTA: Em F3 mantemos os middlewares OPT-IN: a app chama add_middleware so se
JWT_SECRET estiver setado. Isso nao quebra o ambiente atual onde rotas legadas
ainda nao usam auth.
"""
from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse
import jwt

from . import auth, config


_PUBLIC_PREFIXES = (
    "/api/auth/login",
    "/health",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/favicon.ico",
)


def _is_public(path: str) -> bool:
    return any(path == p or path.startswith(p + "/") or path == p for p in _PUBLIC_PREFIXES)


async def auth_middleware(request: Request, call_next):
    if _is_public(request.url.path) or request.method == "OPTIONS":
        return await call_next(request)
    if not config.JWT_SECRET:
        # Sem JWT_SECRET, nao da pra validar nada. Deixa passar (modo legado).
        return await call_next(request)

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return JSONResponse({"detail": "missing token"}, status_code=401)
    try:
        payload = auth.decode_jwt(auth_header.removeprefix("Bearer ").strip())
    except jwt.ExpiredSignatureError:
        return JSONResponse({"detail": "token expirado"}, status_code=401)
    except Exception:
        return JSONResponse({"detail": "token invalido"}, status_code=401)
    request.state.user = payload
    return await call_next(request)


async def tenant_middleware(request: Request, call_next):
    cnpj = request.headers.get("X-Empresa-CNPJ", "").strip() or None
    user = getattr(request.state, "user", None)
    if cnpj and user and not user.get("super_admin"):
        empresas = user.get("empresas") or []
        cnpjs = [e if isinstance(e, str) else e.get("cnpj") for e in empresas]
        if cnpj not in cnpjs:
            return JSONResponse({"detail": "sem permissao nesta empresa"}, status_code=403)
    request.state.cnpj_ativo = cnpj
    return await call_next(request)
