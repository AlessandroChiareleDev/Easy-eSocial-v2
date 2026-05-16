"""Auth routes: POST /api/auth/login + GET /api/auth/me."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from . import auth, config, sistema_db
from .rate_limit import login_rate_limit


router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginPayload(BaseModel):
    # Aceita email OU username (ex: "Ana", "xandeadmin"). A validacao de
    # existencia/credenciais e feita pelo lookup em sistema.users abaixo.
    email: str
    password: str


class LoginResponse(BaseModel):
    token: str
    user: dict[str, Any]
    empresas: list[dict[str, Any]]


@router.post("/login", response_model=LoginResponse, dependencies=[Depends(login_rate_limit)])
def login(payload: LoginPayload, request: Request):
    if not sistema_db.is_available():
        raise HTTPException(status_code=503, detail="sistema_db nao configurado (.env)")

    u = sistema_db.fetch_user_by_email(payload.email)
    if not u or not u.get("ativo"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="credenciais invalidas")
    if not auth.verify_password(payload.password, u["password_hash"]):
        sistema_db.write_audit(
            user_id=str(u["id"]),
            cnpj=None,
            acao="login_fail",
            ip=request.client.host if request.client else None,
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="credenciais invalidas")

    super_admin = bool(u.get("super_admin"))
    empresas = sistema_db.fetch_user_empresas(str(u["id"]))
    if super_admin and not empresas:
        empresas = [
            {
                "cnpj": e["cnpj"],
                "razao_social": e.get("razao_social"),
                "schema_name": e.get("schema_name"),
                "ativo": True,
                "papel": "admin",
            }
            for e in sistema_db.list_empresas_ativas()
        ]
    if super_admin and not empresas:
        empresas = [
            {
                "cnpj": "05969071000110",
                "razao_social": "APPA",
                "schema_name": "appa",
                "ativo": True,
                "papel": "admin",
            },
            {
                "cnpj": "09445502000109",
                "razao_social": "SOLUCOES",
                "schema_name": "solucoes",
                "ativo": True,
                "papel": "admin",
            },
        ]
    token = auth.encode_jwt(
        {
            "sub": str(u["id"]),
            "email": u["email"],
            "nome": u.get("nome"),
            "super_admin": super_admin,
            "empresas": [e["cnpj"] for e in empresas],
        }
    )
    sistema_db.update_last_login(str(u["id"]))
    sistema_db.write_audit(
        user_id=str(u["id"]),
        cnpj=None,
        acao="login_ok",
        ip=request.client.host if request.client else None,
    )
    return {
        "token": token,
        "user": {
            "id": str(u["id"]),
            "email": u["email"],
            "nome": u.get("nome"),
            "super_admin": super_admin,
        },
        "empresas": empresas,
    }


@router.post("/dev-login", response_model=LoginResponse)
def dev_login(request: Request):
    if not config.LOCAL_DEV_LOGIN:
        raise HTTPException(status_code=404, detail="dev login desabilitado")
    client_host = request.client.host if request.client else ""
    if client_host not in {"127.0.0.1", "localhost", "::1"}:
        raise HTTPException(status_code=403, detail="dev login apenas local")
    if not sistema_db.is_available():
        raise HTTPException(status_code=503, detail="sistema_db nao configurado (.env)")

    u = sistema_db.fetch_user_by_email("xandeadmin") or sistema_db.fetch_user_by_email("Ana")
    if not u or not u.get("ativo"):
        raise HTTPException(status_code=503, detail="usuario dev indisponivel")

    empresas = sistema_db.fetch_user_empresas(str(u["id"]))
    super_admin = bool(u.get("super_admin"))
    if super_admin and not empresas:
        empresas = [
            {
                "cnpj": e["cnpj"],
                "razao_social": e.get("razao_social"),
                "schema_name": e.get("schema_name"),
                "ativo": True,
                "papel": "admin",
            }
            for e in sistema_db.list_empresas_ativas()
        ]
    if super_admin and not empresas:
        empresas = [
            {
                "cnpj": "05969071000110",
                "razao_social": "APPA",
                "schema_name": "appa",
                "ativo": True,
                "papel": "admin",
            },
            {
                "cnpj": "09445502000109",
                "razao_social": "SOLUCOES",
                "schema_name": "solucoes",
                "ativo": True,
                "papel": "admin",
            },
        ]
    token = auth.encode_jwt(
        {
            "sub": str(u["id"]),
            "email": u["email"],
            "nome": u.get("nome"),
            "super_admin": super_admin,
            "empresas": [e["cnpj"] for e in empresas],
            "dev_login": True,
        }
    )
    return {
        "token": token,
        "user": {
            "id": str(u["id"]),
            "email": u["email"],
            "nome": u.get("nome"),
            "super_admin": super_admin,
        },
        "empresas": empresas,
    }


@router.get("/me")
def me(request: Request):
    user = auth.get_current_user(request)
    return user
