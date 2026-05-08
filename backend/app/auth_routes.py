"""Auth routes: POST /api/auth/login + GET /api/auth/me."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from . import auth, sistema_db
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

    empresas = sistema_db.fetch_user_empresas(str(u["id"]))
    super_admin = bool(u.get("super_admin"))
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


@router.get("/me")
def me(request: Request):
    user = auth.get_current_user(request)
    return user
