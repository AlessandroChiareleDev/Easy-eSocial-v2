from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

os.environ.setdefault("PYTHONPATH", str(BACKEND))

from fastapi import HTTPException  # noqa: E402
from starlette.responses import Response, StreamingResponse  # noqa: E402

from app import db, explorador, sistema_db, tenant, timeline  # noqa: E402
from app.s1210_anual_detalhe import baixar_xml_cpf, detalhe_cpf  # noqa: E402

CNPJ = "10874523000110"
EMPRESA_ID = tenant.OBJETIVA_ID
ANO = 2025


def ok(name: str, **data: Any) -> None:
    bits = " ".join(f"{key}={value}" for key, value in data.items())
    print(f"PASS {name}" + (f" {bits}" if bits else ""))


def fail(name: str, exc: BaseException) -> None:
    if isinstance(exc, HTTPException):
        print(f"FAIL {name} HTTP {exc.status_code}: {exc.detail}")
    else:
        print(f"FAIL {name} {type(exc).__name__}: {exc}")
    raise SystemExit(1)


async def _collect_stream(resp: StreamingResponse) -> bytes:
    chunks: list[bytes] = []
    async for chunk in resp.body_iterator:
        if isinstance(chunk, str):
            chunk = chunk.encode("utf-8")
        chunks.append(chunk)
    return b"".join(chunks)


def response_bytes(resp: Response | StreamingResponse) -> bytes:
    if isinstance(resp, StreamingResponse):
        return asyncio.run(_collect_stream(resp))
    return bytes(resp.body or b"")


def validate_auth_link() -> None:
    with sistema_db.sistema_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT u.email, u.nome, u.super_admin, ue.papel, er.schema_name, er.ativo
              FROM user_empresas ue
              JOIN users u ON u.id = ue.user_id
              JOIN empresas_routing er ON er.cnpj = ue.cnpj
             WHERE ue.cnpj = %s
             ORDER BY lower(u.email)
            """,
            (CNPJ,),
        )
        rows = cur.fetchall()
    ana_rows = [r for r in rows if str(r[0]).lower() == "ana" or "ana" in str(r[1] or "").lower()]
    if not ana_rows:
        raise RuntimeError(f"Ana nao esta vinculada; vinculados={len(rows)}")
    row = ana_rows[0]
    ok("ana_link", email=row[0], papel=row[3], schema=row[4], ativo=row[5])


def validate_tenant() -> None:
    with db.cursor(empresa_id=EMPRESA_ID) as cur:
        cur.execute("SELECT current_schema() AS schema")
        schema = cur.fetchone()["schema"]
        cur.execute("SELECT COUNT(*) AS n FROM master_empresas WHERE cnpj=%s", (CNPJ,))
        empresa = int(cur.fetchone()["n"] or 0)
        cur.execute("SELECT COUNT(*) AS n FROM timeline_mes WHERE empresa_id=%s", (tenant.internal_empresa_id(EMPRESA_ID),))
        meses = int(cur.fetchone()["n"] or 0)
    if schema != "objetiva" or empresa != 1:
        raise RuntimeError(f"tenant invalido schema={schema} empresa={empresa}")
    ok("tenant_objetiva", schema=schema, timeline_mes=meses)


def validate_explorador() -> tuple[int, str, str]:
    zips = explorador.listar_zips(empresa_id=EMPRESA_ID)
    items = zips.get("items") or []
    if len(items) != 12:
        raise RuntimeError(f"zips={len(items)} esperado=12")
    zip_id = int(items[0]["id"])
    detalhe = explorador.detalhe_zip(zip_id, empresa_id=EMPRESA_ID)
    resumo = explorador.resumo_zip(zip_id, empresa_id=EMPRESA_ID)
    eventos = explorador.listar_eventos(
        empresa_id=EMPRESA_ID,
        tipo_evento="S-1210",
        zip_id=zip_id,
        limit=1,
        offset=0,
    )
    ev_items = eventos.get("items") or []
    if not ev_items:
        eventos = explorador.listar_eventos(
            empresa_id=EMPRESA_ID,
            tipo_evento="S-1210",
            limit=1,
            offset=0,
        )
        ev_items = eventos.get("items") or []
    if not ev_items:
        raise RuntimeError("nenhum S-1210 encontrado no Explorador")
    sample = ev_items[0]
    resp = explorador.baixar_xml(int(sample["id"]), empresa_id=EMPRESA_ID)
    data = response_bytes(resp)
    if len(data) < 50 or b"<" not in data[:50]:
        raise RuntimeError(f"XML invalido bytes={len(data)}")
    por_tipo = resumo.get("por_tipo") or []
    ok(
        "explorador",
        zips=len(items),
        zip_id=zip_id,
        eventos_indexados=detalhe["zip"].get("eventos_indexados"),
        tipos=len(por_tipo),
        xml_bytes=len(data),
    )
    return int(sample["id"]), str(sample["cpf"]), str(sample["per_apur"])


def validate_timeline_and_s1210(sample_cpf: str, sample_per: str) -> None:
    meses = timeline.listar_meses(empresa_id=EMPRESA_ID)
    if len(meses.get("items") or []) != 12:
        raise RuntimeError(f"timeline meses={len(meses.get('items') or [])}")
    overview = timeline.s1210_anual_overview(ano=ANO, empresa_id=EMPRESA_ID)
    overview_meses = overview.get("meses") or []
    meses_com_total = sum(
        1
        for mes in overview_meses
        if sum(int(lote.get("total") or 0) for lote in (mes.get("lotes") or [])) > 0
    )
    detalhe = detalhe_cpf(1, sample_per, sample_cpf, empresa_id=EMPRESA_ID)
    resp = baixar_xml_cpf(1, sample_per, sample_cpf, empresa_id=EMPRESA_ID, tipo="S-1210")
    data = response_bytes(resp)
    if len(data) < 50:
        raise RuntimeError(f"XML CPF invalido bytes={len(data)}")
    ok(
        "s1210_anual",
        timeline_meses=len(meses.get("items") or []),
        overview_meses=len(overview_meses),
        meses_com_total=meses_com_total,
        sample_per=sample_per,
        pagamentos=len(detalhe.get("pagamentos") or []),
        s5002=len(detalhe.get("s5002_list") or []),
        xml_bytes=len(data),
    )


def main() -> int:
    validate_auth_link()
    validate_tenant()
    _event_id, cpf, per_apur = validate_explorador()
    validate_timeline_and_s1210(cpf, per_apur)
    print("PASS overall Objetiva local validation complete")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        fail("overall", exc)
