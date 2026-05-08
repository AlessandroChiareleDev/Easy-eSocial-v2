"""Cert Routes — A1 (.pfx) — F4.B.

Endpoints (single-tenant via app.db; multi-tenant TODO via tenant.empresa_conn):
  POST   /api/certificados/upload
  GET    /api/certificados/ativo
  GET    /api/certificados/listar
  DELETE /api/certificados/{cert_id}
  POST   /api/certificados/senha/salvar
  GET    /api/certificados/senha/status
  DELETE /api/certificados/senha/remover

Tabelas: certificados_a1, senha_certificado_salva (criadas em empresa_v1.0.0.sql).
"""
from __future__ import annotations

import os

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from . import db
from .certificate_manager import CertificateManager

router = APIRouter(prefix="/api/certificados", tags=["certificados"])


# ---------------- helpers ----------------


def _get_saved_senha() -> str | None:
    with db.cursor() as cur:
        cur.execute(
            "SELECT senha_encrypted FROM senha_certificado_salva "
            "WHERE expires_at > NOW() ORDER BY id DESC LIMIT 1"
        )
        row = cur.fetchone()
    if not row:
        return None
    return CertificateManager.decrypt_password(row["senha_encrypted"])


# ---------------- certificados ----------------


@router.post("/upload")
async def upload_certificate(file: UploadFile = File(...), senha: str = Form(default="")):
    fname = (file.filename or "").lower()
    if not fname.endswith(".pfx") and not fname.endswith(".p12"):
        raise HTTPException(status_code=400, detail="Arquivo deve ser .pfx ou .p12")

    pfx_data = await file.read()
    if not pfx_data:
        raise HTTPException(status_code=400, detail="Arquivo vazio")

    if not senha:
        saved = _get_saved_senha()
        if not saved:
            raise HTTPException(
                status_code=400,
                detail="Senha nao informada e nenhuma senha salva encontrada",
            )
        senha = saved

    try:
        info = CertificateManager.validate_pfx(pfx_data, senha)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Certificado invalido: {e}")
    except Exception as e:  # noqa: BLE001
        raise HTTPException(
            status_code=400, detail=f"Erro ao ler certificado: {type(e).__name__}: {e}"
        )

    try:
        filepath = CertificateManager.save_certificate(
            pfx_data, info["cnpj"] or "unknown", info["numero_serie"]
        )
    except Exception as e:  # noqa: BLE001
        raise HTTPException(
            status_code=500, detail=f"Erro ao salvar arquivo: {type(e).__name__}: {e}"
        )

    senha_encrypted = CertificateManager.encrypt_password(senha)

    with db.cursor(commit=True) as cur:
        cur.execute("UPDATE certificados_a1 SET ativo = FALSE WHERE ativo = TRUE")
        cur.execute(
            """INSERT INTO certificados_a1
                 (cnpj, titular, emissor, numero_serie, validade_fim,
                  arquivo_path, senha_encrypted, ativo)
               VALUES (%s, %s, %s, %s, %s, %s, %s, TRUE)
               RETURNING id""",
            (
                info["cnpj"],
                info["nome_titular"],
                info["emissor"],
                info["numero_serie"],
                info["validade"],
                filepath,
                senha_encrypted,
            ),
        )
        cert_id = cur.fetchone()["id"]

    return {
        "id": cert_id,
        "cnpj": info["cnpj"],
        "titular": info["nome_titular"],
        "emissor": info["emissor"],
        "numero_serie": info["numero_serie"],
        "validade": info["validade"].isoformat(),
        "ativo": True,
    }


@router.get("/ativo")
async def get_active_certificate():
    with db.cursor() as cur:
        cur.execute(
            """SELECT id, cnpj, titular, emissor, numero_serie,
                      validade_fim, ativo, created_at
                 FROM certificados_a1
                WHERE ativo = TRUE
                LIMIT 1"""
        )
        row = cur.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Nenhum certificado ativo")

    return {
        "id": row["id"],
        "cnpj": row["cnpj"],
        "titular": row["titular"],
        "emissor": row["emissor"],
        "numero_serie": row["numero_serie"],
        "validade": row["validade_fim"].isoformat() if row["validade_fim"] else None,
        "ativo": row["ativo"],
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
    }


@router.get("/listar")
async def listar_certificados():
    with db.cursor() as cur:
        cur.execute(
            """SELECT id, cnpj, titular, emissor, numero_serie,
                      validade_fim, ativo, created_at
                 FROM certificados_a1
                ORDER BY ativo DESC, created_at DESC"""
        )
        rows = cur.fetchall()
    return [
        {
            "id": r["id"],
            "cnpj": r["cnpj"],
            "titular": r["titular"],
            "emissor": r["emissor"],
            "numero_serie": r["numero_serie"],
            "validade": r["validade_fim"].isoformat() if r["validade_fim"] else None,
            "ativo": r["ativo"],
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
        }
        for r in rows
    ]


@router.delete("/{cert_id}")
async def delete_certificate(cert_id: int):
    with db.cursor(commit=True) as cur:
        cur.execute("SELECT arquivo_path FROM certificados_a1 WHERE id = %s", (cert_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Certificado nao encontrado")
        filepath = row["arquivo_path"]
        if filepath and os.path.exists(filepath):
            try:
                os.remove(filepath)
            except OSError:
                pass
        cur.execute("DELETE FROM certificados_a1 WHERE id = %s", (cert_id,))
    return {"deleted": True, "id": cert_id}


# ---------------- senha salva ----------------


@router.post("/senha/salvar")
async def salvar_senha(senha: str = Form(...), duracao_horas: int = Form(default=24)):
    if duracao_horas < 1 or duracao_horas > 720:
        raise HTTPException(status_code=400, detail="Duracao deve ser entre 1 e 720 horas")
    senha_encrypted = CertificateManager.encrypt_password(senha)
    with db.cursor(commit=True) as cur:
        cur.execute("DELETE FROM senha_certificado_salva")
        cur.execute(
            "INSERT INTO senha_certificado_salva (senha_encrypted, expires_at) "
            "VALUES (%s, NOW() + make_interval(hours => %s)) "
            "RETURNING saved_at, expires_at",
            (senha_encrypted, duracao_horas),
        )
        row = cur.fetchone()
    return {
        "saved": True,
        "saved_at": row["saved_at"].isoformat(),
        "expires_at": row["expires_at"].isoformat(),
    }


@router.get("/senha/status")
async def status_senha():
    with db.cursor() as cur:
        cur.execute(
            "SELECT saved_at, expires_at FROM senha_certificado_salva "
            "WHERE expires_at > NOW() ORDER BY id DESC LIMIT 1"
        )
        row = cur.fetchone()
    if not row:
        return {"saved": False}
    return {
        "saved": True,
        "saved_at": row["saved_at"].isoformat(),
        "expires_at": row["expires_at"].isoformat(),
    }


@router.delete("/senha/remover")
async def remover_senha():
    with db.cursor(commit=True) as cur:
        cur.execute("DELETE FROM senha_certificado_salva")
    return {"removed": True}
