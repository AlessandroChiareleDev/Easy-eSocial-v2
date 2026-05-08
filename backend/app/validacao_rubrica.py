"""F8.2 — Validacao de rubricas (porte de V1 rubrica-validation-service.ts).

Compara col_d/e/f (codigos cadastrados) vs codigos extraidos de col_h/i/j da tabela_eb,
populando rubrica_corrections com status='pendente' para divergencias novas.
"""
from __future__ import annotations

import re
from typing import Any

from fastapi import APIRouter, Body, HTTPException, Path, Query, Request

from . import tenant


router = APIRouter(prefix="/api/rubrica", tags=["rubrica"])

ALLOWED_STATUS = ("pendente", "corrigido", "verificado", "realizada")

# Match " - " ou " -<NBSP>" (V1 regex literal)
_CODE_RE = re.compile(r"^(.+?)\s-[\s\u00A0]")


def _extract_code(full_text: Any) -> str:
    if not full_text:
        return ""
    s = str(full_text).strip()
    m = _CODE_RE.match(s)
    if m:
        return m.group(1).strip()
    return s


def _cnpj_ativo(request: Request) -> str:
    cnpj = getattr(request.state, "cnpj_ativo", None)
    if not cnpj:
        cnpj = request.headers.get("X-Empresa-CNPJ", "").strip() or None
    if not cnpj:
        raise HTTPException(400, "header X-Empresa-CNPJ ausente")
    return cnpj


@router.post("/detectar")
def detectar_divergencias(request: Request):
    cnpj = _cnpj_ativo(request)
    with tenant.empresa_conn(cnpj) as conn:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, col_a, col_b, col_d, col_e, col_f, col_h, col_i, col_j "
                    "FROM tabela_eb ORDER BY id"
                )
                rows = cur.fetchall()

                cur.execute(
                    "DELETE FROM rubrica_corrections WHERE status = 'pendente'"
                )

                divergentes = 0
                inseridas = 0
                for r in rows:
                    (eb_id, col_a, col_b, col_d, col_e, col_f,
                     col_h, col_i, col_j) = r
                    cod_d = (col_d or "").strip()
                    cod_e = (col_e or "").strip()
                    cod_f = (col_f or "").strip()
                    cod_h = _extract_code(col_h)
                    cod_i = _extract_code(col_i)
                    cod_j = _extract_code(col_j)
                    if cod_d == cod_h and cod_e == cod_i and cod_f == cod_j:
                        continue
                    divergentes += 1
                    cur.execute(
                        "SELECT 1 FROM rubrica_corrections "
                        "WHERE tabela_eb_id = %s AND status IN ('corrigido','verificado')",
                        (eb_id,),
                    )
                    if cur.fetchone():
                        continue
                    cur.execute(
                        """
                        INSERT INTO rubrica_corrections
                          (tabela_eb_id, cod_rubrica, descricao,
                           inss_antes, irrf_antes, fgts_antes,
                           inss_correto, irrf_correto, fgts_correto, status)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'pendente')
                        """,
                        (
                            eb_id, col_a or "", col_b or "",
                            cod_d, cod_e, cod_f,
                            cod_h, cod_i, cod_j,
                        ),
                    )
                    inseridas += 1
            conn.commit()
        except HTTPException:
            conn.rollback()
            raise
        except Exception as e:  # noqa: BLE001
            conn.rollback()
            raise HTTPException(500, f"falha: {e}")

    return {
        "ok": True,
        "total": len(rows),
        "divergentes": divergentes,
        "inseridas": inseridas,
    }


@router.get("/resumo")
def resumo(request: Request):
    cnpj = _cnpj_ativo(request)
    with tenant.empresa_conn(cnpj) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM tabela_eb")
            total_rubricas = cur.fetchone()[0]
            cur.execute(
                """
                SELECT
                    COUNT(*),
                    COUNT(*) FILTER (WHERE status='pendente'),
                    COUNT(*) FILTER (WHERE status='corrigido'),
                    COUNT(*) FILTER (WHERE status='verificado'),
                    COUNT(*) FILTER (WHERE status='realizada')
                  FROM rubrica_corrections
                """
            )
            total, pend, corr, ver, real = cur.fetchone()
    return {
        "total_rubricas": total_rubricas,
        "total_divergentes": total,
        "total_pendentes": pend,
        "total_corrigidas": corr,
        "total_verificadas": ver,
        "total_realizadas": real,
    }


@router.get("/divergencias")
def listar_divergencias(
    request: Request,
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    cnpj = _cnpj_ativo(request)
    where = ""
    params: list[Any] = []
    if status:
        if status not in ALLOWED_STATUS:
            raise HTTPException(400, f"status invalido. use {ALLOWED_STATUS}")
        where = "WHERE rc.status = %s"
        params.append(status)
    with tenant.empresa_conn(cnpj) as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT COUNT(*) FROM rubrica_corrections rc {where}", params
            )
            total = cur.fetchone()[0]
            cur.execute(
                f"""
                SELECT rc.id, rc.tabela_eb_id, rc.cod_rubrica, rc.descricao,
                       rc.inss_antes, rc.irrf_antes, rc.fgts_antes,
                       rc.inss_correto, rc.irrf_correto, rc.fgts_correto,
                       rc.status, rc.corrigido_em, rc.observacao,
                       eb.col_h, eb.col_i, eb.col_j
                  FROM rubrica_corrections rc
                  JOIN tabela_eb eb ON eb.id = rc.tabela_eb_id
                  {where}
                 ORDER BY
                    CASE WHEN rc.cod_rubrica ~ '^[0-9]+$'
                         THEN CAST(rc.cod_rubrica AS INTEGER)
                         ELSE NULL END NULLS LAST,
                    rc.id
                 LIMIT %s OFFSET %s
                """,
                params + [limit, offset],
            )
            cols = [d.name for d in cur.description]
            data = [dict(zip(cols, r)) for r in cur.fetchall()]
    return {"total": total, "limit": limit, "offset": offset, "data": data}


@router.get("/proxima-pendente")
def proxima_pendente(request: Request):
    cnpj = _cnpj_ativo(request)
    with tenant.empresa_conn(cnpj) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT rc.id, rc.tabela_eb_id, rc.cod_rubrica, rc.descricao,
                       rc.inss_antes, rc.irrf_antes, rc.fgts_antes,
                       rc.inss_correto, rc.irrf_correto, rc.fgts_correto,
                       rc.status, eb.col_h, eb.col_i, eb.col_j
                  FROM rubrica_corrections rc
                  JOIN tabela_eb eb ON eb.id = rc.tabela_eb_id
                 WHERE rc.status = 'pendente'
                 ORDER BY
                    CASE WHEN rc.cod_rubrica ~ '^[0-9]+$'
                         THEN CAST(rc.cod_rubrica AS INTEGER)
                         ELSE NULL END NULLS LAST,
                    rc.id
                 LIMIT 1
                """
            )
            row = cur.fetchone()
            if not row:
                return {"data": None}
            cols = [d.name for d in cur.description]
            return {"data": dict(zip(cols, row))}


def _update_status(cnpj: str, rc_id: int, new_status: str, **extra: Any) -> dict[str, Any] | None:
    sets = ["status = %s"]
    params: list[Any] = [new_status]
    if "observacao" in extra:
        sets.append("observacao = %s")
        params.append(extra["observacao"])
    if extra.get("set_corrigido_em") is True:
        sets.append("corrigido_em = NOW()")
    elif extra.get("set_corrigido_em") is False:
        sets.append("corrigido_em = NULL, observacao = NULL")
    params.append(rc_id)
    with tenant.empresa_conn(cnpj) as conn:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"UPDATE rubrica_corrections SET {', '.join(sets)} WHERE id = %s RETURNING *",
                    params,
                )
                row = cur.fetchone()
                if not row:
                    return None
                cols = [d.name for d in cur.description]
                result = dict(zip(cols, row))
            conn.commit()
        except Exception as e:  # noqa: BLE001
            conn.rollback()
            raise HTTPException(500, f"falha: {e}")
    return result


@router.post("/{rc_id}/corrigir")
def marcar_corrigido(
    request: Request,
    rc_id: int = Path(..., ge=1),
    payload: dict[str, Any] = Body(default={}),
):
    cnpj = _cnpj_ativo(request)
    obs = payload.get("observacao") if isinstance(payload, dict) else None
    row = _update_status(cnpj, rc_id, "corrigido", observacao=obs, set_corrigido_em=True)
    if not row:
        raise HTTPException(404, f"rubrica_corrections id={rc_id} nao encontrado")
    return {"ok": True, "data": row}


@router.post("/{rc_id}/verificar")
def marcar_verificado(request: Request, rc_id: int = Path(..., ge=1)):
    cnpj = _cnpj_ativo(request)
    row = _update_status(cnpj, rc_id, "verificado")
    if not row:
        raise HTTPException(404, f"rubrica_corrections id={rc_id} nao encontrado")
    return {"ok": True, "data": row}


@router.post("/{rc_id}/realizada")
def marcar_realizada(request: Request, rc_id: int = Path(..., ge=1)):
    cnpj = _cnpj_ativo(request)
    row = _update_status(cnpj, rc_id, "realizada", set_corrigido_em=True)
    if not row:
        raise HTTPException(404, f"rubrica_corrections id={rc_id} nao encontrado")
    return {"ok": True, "data": row}


@router.post("/{rc_id}/resetar")
def resetar(request: Request, rc_id: int = Path(..., ge=1)):
    cnpj = _cnpj_ativo(request)
    row = _update_status(cnpj, rc_id, "pendente", set_corrigido_em=False)
    if not row:
        raise HTTPException(404, f"rubrica_corrections id={rc_id} nao encontrado")
    return {"ok": True, "data": row}
