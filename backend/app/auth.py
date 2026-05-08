"""Auth: JWT + bcrypt + FastAPI Depends.

Uso:
    from .auth import get_current_user, encode_jwt, hash_password, verify_password
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request, status

from . import config


# ---------- Password ----------
# bcrypt aceita no maximo 72 bytes — truncamos a senha antes (padrao seguro).


def _truncate(plain: str) -> bytes:
    return plain.encode("utf-8")[:72]


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(_truncate(plain), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(_truncate(plain), hashed.encode("utf-8"))
    except Exception:  # noqa: BLE001
        return False


# ---------- JWT ----------


def _ensure_secret() -> str:
    if not config.JWT_SECRET or len(config.JWT_SECRET) < 32:
        raise RuntimeError(
            "JWT_SECRET ausente ou < 32 chars no .env (defina um valor aleatorio robusto)"
        )
    return config.JWT_SECRET


def encode_jwt(payload: dict[str, Any], expires_minutes: Optional[int] = None) -> str:
    secret = _ensure_secret()
    exp_min = expires_minutes if expires_minutes is not None else config.JWT_EXPIRES_MINUTES
    now = datetime.now(timezone.utc)
    body = dict(payload)
    body["iat"] = int(now.timestamp())
    body["exp"] = int((now + timedelta(minutes=exp_min)).timestamp())
    return jwt.encode(body, secret, algorithm=config.JWT_ALGORITHM)


def decode_jwt(token: str) -> dict[str, Any]:
    secret = _ensure_secret()
    return jwt.decode(token, secret, algorithms=[config.JWT_ALGORITHM])


# ---------- FastAPI Depends ----------


def get_current_user(request: Request) -> dict[str, Any]:
    """Depends que retorna o user do JWT.

    Espera que tenant_middleware ou auth_middleware ja tenha colocado em
    request.state.user. Senao, valida o header aqui.
    """
    user = getattr(request.state, "user", None)
    if user:
        return user

    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing token")
    try:
        payload = decode_jwt(auth.removeprefix("Bearer ").strip())
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="token expirado")
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="token invalido")
    request.state.user = payload
    return payload


def require_super_admin(user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    if not user.get("super_admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="super_admin requerido")
    return user


def require_cnpj(request: Request, user: dict[str, Any] = Depends(get_current_user)) -> str:
    """Garante que ha CNPJ no header X-Empresa-CNPJ e que o user tem acesso."""
    cnpj = request.headers.get("X-Empresa-CNPJ", "").strip()
    if not cnpj:
        raise HTTPException(status_code=400, detail="header X-Empresa-CNPJ ausente")
    if not user.get("super_admin"):
        empresas = user.get("empresas") or []
        # empresas pode ser list[str] ou list[{cnpj,...}]
        cnpjs = [e if isinstance(e, str) else e.get("cnpj") for e in empresas]
        if cnpj not in cnpjs:
            raise HTTPException(status_code=403, detail="sem permissao nesta empresa")
    request.state.cnpj_ativo = cnpj
    return cnpj
