"""GET /api/s1210-repo/anual/detalhe-cpf/{lote}/{per_apur}/{cpf}

Porta do endpoint V1 `python-scripts/esocial/s1210_repo_routes.py:detalhe_cpf`
para o V2 — mesma SHAPE de JSON do front, fontes adaptadas ao schema V2.

Schema V2 (real, produção SOLUCOES):
  * `s1210_cpf_scope`         — lista de CPFs por lote/per_apur
  * `s1210_cpf_envios`        — histórico de envios c/ `pagamentos` e
                                 `info_ir` JSONB já estruturados
  * `s1210_cpf_recibo`        — recibos (zip/usado/esocial) por CPF
  * `explorador_eventos`      — eventos S-1210/S-5002 com `dados_json` JSONB
                                 (já parseado pelo Explorador). Não há
                                 `xml_oid` nem `referenciado_recibo`.
"""
from __future__ import annotations

import logging
import re
import zipfile
from typing import Optional

import psycopg2
import psycopg2.extras
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from . import storage, tenant

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/s1210-repo", tags=["s1210-detalhe"])


# ─── Tabelas de labels (idênticas ao V1) ──────────────────────────────
_TP_PGTO_LABELS = {
    "1": "Pagamento de remuneração — folha mensal",
    "2": "Remuneração de período anterior",
    "3": "Pagamento de férias",
    "4": "Pagamento de 13º salário",
    "5": "Pagamento de benefício previdenciário",
    "6": "Pagamento de ajuste do 13º salário",
    "7": "Pagamento de rescisão",
    "8": "Pagamento de PLR",
    "9": "Pagamento de RRA",
}
_TP_CR_LABELS = {
    "0561": "IRRF — Trabalho assalariado",
    "0588": "IRRF — 13º salário",
    "3533": "IRRF — Rendimentos de aposentadoria e pensões",
    "5204": "IRRF — Rescisão de contrato de trabalho",
    "5936": "IRRF — Plano de previdência complementar",
}
_TP_INFO_IR_LABELS = {
    "11": "Rendimento tributável",
    "12": "Previdência oficial",
    "13": "Dependentes",
    "14": "Pensão alimentícia",
    "31": "IRRF retido",
    "43": "13º salário tributável",
    "7900": "Deduções (prev/dep/pensão)",
    "9901": "Outros rendimentos",
    "9903": "Ajuda de custo",
}


def _to_float(v) -> Optional[float]:
    if v is None:
        return None
    s = str(v).strip()
    if not s:
        return None
    try:
        return float(s.replace(",", "."))
    except (ValueError, TypeError):
        return None


def _tpcr_short(tp_cr: Optional[str]) -> str:
    """Reduz '056107' → '0561' para casar com _TP_CR_LABELS (V1)."""
    s = str(tp_cr or "").strip()
    return s[:4] if len(s) >= 4 else s


# ═════════════════════════════════════════════════════════════════════
# GET /detalhe-cpf/{lote_num}/{per_apur}/{cpf}
# ═════════════════════════════════════════════════════════════════════
@router.get("/anual/detalhe-cpf/{lote_num}/{per_apur}/{cpf}")
def detalhe_cpf(
    lote_num: int,
    per_apur: str,
    cpf: str,
    empresa_id: int = Query(...),
):
    """Pacote completo de detalhes do CPF (pagamentos, IR, recibos, histórico).

    Mantém SHAPE de resposta idêntica ao V1. Fontes:
      * pagamentos / info_ir_cr → último envio OK (`s1210_cpf_envios`),
        fallback para `explorador_eventos` S-1210 (`dados_json`)
      * S-5002 → `explorador_eventos` (`dados_json` já parseado)
      * recibo ativo → `s1210_cpf_recibo` se houver; senão último S-1210
        no explorador; senão `nr_recibo_novo` do último envio OK
    """
    if lote_num < 1:
        raise HTTPException(400, "lote_num inválido")
    cpf = (cpf or "").strip().replace(".", "").replace("-", "")
    if len(cpf) != 11 or not cpf.isdigit():
        raise HTTPException(400, "CPF inválido")
    if not re.fullmatch(r"\d{4}-\d{2}", per_apur or ""):
        raise HTTPException(400, "per_apur deve estar no formato AAAA-MM")

    cfg = tenant.get_db_config_for_empresa(empresa_id)
    internal_id = tenant.internal_empresa_id(empresa_id)

    conn = psycopg2.connect(**cfg)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # 1) Scope
            cur.execute(
                """SELECT cpf, nome, matricula, lote_num, per_apur
                     FROM s1210_cpf_scope
                    WHERE empresa_id=%s AND per_apur=%s
                      AND lote_num=%s AND cpf=%s""",
                (internal_id, per_apur, lote_num, cpf),
            )
            scope_row = cur.fetchone()
            if not scope_row:
                # Fallback: CPF fora do scope do lote pedido, mas existe na empresa
                cur.execute(
                    """SELECT nome, matricula FROM s1210_cpf_scope
                        WHERE empresa_id=%s AND cpf=%s LIMIT 1""",
                    (internal_id, cpf),
                )
                fb = cur.fetchone()
                scope_row = {
                    "cpf": cpf,
                    "nome": (fb or {}).get("nome"),
                    "matricula": (fb or {}).get("matricula"),
                    "lote_num": lote_num,
                    "per_apur": per_apur,
                }

            # 2) Histórico de envios
            cur.execute(
                """SELECT status, codigo_resposta, descricao_resposta,
                          nr_recibo_usado, nr_recibo_novo, protocolo,
                          erro_descricao, pagamentos, info_ir, enviado_em,
                          duracao_ms
                     FROM s1210_cpf_envios
                    WHERE empresa_id=%s AND per_apur=%s
                      AND lote_num=%s AND cpf=%s
                    ORDER BY enviado_em DESC""",
                (internal_id, per_apur, lote_num, cpf),
            )
            envios = list(cur.fetchall() or [])

            ultimo_ok = next(
                (e for e in envios if (e.get("status") or "") == "ok"), None
            )

            # 3) S-1210 do Explorador — pega o mais recente (id DESC)
            cur.execute(
                """SELECT id, nr_recibo, id_evento, dt_processamento, dados_json
                     FROM explorador_eventos
                    WHERE tipo_evento='S-1210' AND cpf=%s AND per_apur=%s
                    ORDER BY id DESC
                    LIMIT 1""",
                (cpf, per_apur),
            )
            s1210_row = cur.fetchone()

            zip_data: Optional[dict] = None
            if s1210_row:
                dj = s1210_row.get("dados_json") or {}
                info_pgtos = dj.get("pagamentos") or []
                info_ir_cr = dj.get("infoIRCR") or []
                # alguns S-1210 trazem o pagamento principal direto (sem array)
                if not info_pgtos and dj.get("dtPgto"):
                    info_pgtos = [{
                        "vrLiq": dj.get("vrLiq"),
                        "dtPgto": dj.get("dtPgto"),
                        "perRef": dj.get("perRef") or per_apur,
                        "tpPgto": dj.get("tpPgto"),
                        "ideDmDev": dj.get("ideDmDev"),
                    }]
                if not info_ir_cr and dj.get("tpCR"):
                    info_ir_cr = [{"tpCR": dj.get("tpCR"), "vrCR": dj.get("vrCR")}]
                zip_data = {
                    "info_pgtos": info_pgtos,
                    "info_ir_cr": info_ir_cr,
                    "nr_recibo": s1210_row.get("nr_recibo"),
                    "ind_retif": dj.get("indRetif"),
                    "dh_proc": (
                        s1210_row["dt_processamento"].isoformat()
                        if s1210_row.get("dt_processamento")
                        else None
                    ),
                }

            # 4) Recibo ativo + cadeia
            #    Como o V2 não tem `referenciado_recibo`, o recibo ativo é
            #    o do registro mais recente (id DESC). Cadeia = qtd de
            #    versões anteriores.
            recibo_ativo: Optional[str] = None
            recibo_fonte: Optional[str] = None
            cadeia_n = 0

            cur.execute(
                """SELECT nr_recibo_esocial, nr_recibo_usado, nr_recibo_zip,
                          fonte, dh_processamento_zip
                     FROM s1210_cpf_recibo
                    WHERE empresa_id=%s AND per_apur=%s AND cpf=%s
                    LIMIT 1""",
                (internal_id, per_apur, cpf),
            )
            rec_row = cur.fetchone()
            if rec_row:
                recibo_ativo = (
                    rec_row.get("nr_recibo_esocial")
                    or rec_row.get("nr_recibo_usado")
                    or rec_row.get("nr_recibo_zip")
                )
                recibo_fonte = rec_row.get("fonte") or "s1210_cpf_recibo"

            if not recibo_ativo and zip_data and zip_data.get("nr_recibo"):
                recibo_ativo = zip_data["nr_recibo"]
                recibo_fonte = "explorador"

            if not recibo_ativo and ultimo_ok:
                recibo_ativo = (
                    ultimo_ok.get("nr_recibo_novo")
                    or ultimo_ok.get("nr_recibo_usado")
                )
                recibo_fonte = "envio"

            if s1210_row:
                cur.execute(
                    """SELECT COUNT(*) AS n
                         FROM explorador_eventos
                        WHERE tipo_evento='S-1210' AND cpf=%s AND per_apur=%s""",
                    (cpf, per_apur),
                )
                rr = cur.fetchone()
                cadeia_n = max(int((rr or {}).get("n") or 0) - 1, 0)

            # 5) Pagamentos: preferir envio OK (já estruturado) → fallback explorador
            pagamentos: list[dict] = []
            total_liquido = 0.0
            pgtos_src = None
            if ultimo_ok and ultimo_ok.get("pagamentos"):
                pgtos_src = ultimo_ok["pagamentos"]
            elif zip_data and zip_data.get("info_pgtos"):
                pgtos_src = zip_data["info_pgtos"]

            for p in (pgtos_src or []):
                tp = str(p.get("tpPgto") or "")
                vr = _to_float(p.get("vrLiq"))
                if vr is not None:
                    total_liquido += vr
                pagamentos.append({
                    "dt_pgto": p.get("dtPgto"),
                    "tp_pgto": tp,
                    "tp_pgto_label": _TP_PGTO_LABELS.get(tp, f"Tipo {tp}"),
                    "per_ref": p.get("perRef"),
                    "ide_dm_dev": p.get("ideDmDev"),
                    "vr_liq": vr,
                    "vr_liq_raw": p.get("vrLiq"),
                })

            # 6) infoIRCR — preferir envio OK; fallback explorador
            ir_entries: list[dict] = []
            ir_src = None
            if ultimo_ok and ultimo_ok.get("info_ir"):
                ir_src = ultimo_ok["info_ir"]
            elif zip_data and zip_data.get("info_ir_cr"):
                ir_src = zip_data["info_ir_cr"]

            for ir in (ir_src or []):
                tp_full = str(ir.get("tpCR") or "")
                tp = _tpcr_short(tp_full)
                vr = _to_float(ir.get("vrCR"))
                ir_entries.append({
                    "tp_cr": tp_full,
                    "tp_cr_label": _TP_CR_LABELS.get(tp, f"Código {tp_full}"),
                    "vr_cr": vr,
                    "vr_cr_raw": ir.get("vrCR"),
                })

            # 7) S-5002 do Explorador (dados_json já parseado)
            cur.execute(
                """SELECT id, nr_recibo, id_evento, dados_json
                     FROM explorador_eventos
                    WHERE tipo_evento='S-5002' AND cpf=%s AND per_apur=%s
                    ORDER BY nr_recibo DESC NULLS LAST, id DESC""",
                (cpf, per_apur),
            )
            s5002_rows = list(cur.fetchall() or [])

            s5002_list: list[dict] = []
            for r in s5002_rows:
                dj = r.get("dados_json") or {}
                cr_men = dj.get("totApurMen_CRMen")
                vlr_rt = _to_float(dj.get("totApurMen_vlrRendTrib"))
                vlr_po = _to_float(dj.get("totApurMen_vlrPrevOficial"))
                vlr_cr = _to_float(dj.get("totApurMen_vlrCRMen"))
                info_ir_list = dj.get("infoIR") or []
                vazio = not (
                    cr_men or vlr_rt or vlr_po or vlr_cr or info_ir_list
                )
                s5002_list.append({
                    "nr_recibo": r.get("nr_recibo"),
                    "id": r.get("id_evento"),
                    "vazio": vazio,
                    "cr_men": cr_men,
                    "vlr_rend_trib": vlr_rt,
                    "vlr_prev_oficial": vlr_po,
                    "vlr_ir_retido": vlr_cr,
                    "info_ir": [
                        {
                            "tp_info_ir": it.get("tpInfoIR"),
                            "tp_info_ir_label": _TP_INFO_IR_LABELS.get(
                                str(it.get("tpInfoIR")),
                                f"tpInfoIR {it.get('tpInfoIR')}",
                            ),
                            "valor": _to_float(it.get("valor")),
                        }
                        for it in info_ir_list
                    ],
                })

            # 8) S-5002 ativo
            s5002_ativo: Optional[dict] = None
            ativo_nr = recibo_ativo or (
                zip_data.get("nr_recibo") if zip_data else None
            )
            if ativo_nr:
                for s in s5002_list:
                    if s["nr_recibo"] == ativo_nr:
                        s5002_ativo = s
                        break
            if not s5002_ativo:
                for s in s5002_list:
                    if not s["vazio"]:
                        s5002_ativo = s
                        break
            ir_retido_s5002 = (
                s5002_ativo.get("vlr_ir_retido") if s5002_ativo else None
            )

            # 9) IR efetivo (prioriza vrCR S-1210 quando > 0, senão S-5002)
            ir_efetivo_valor: Optional[float] = None
            ir_efetivo_fonte: Optional[str] = None
            for e in ir_entries:
                if e.get("vr_cr") is not None and e["vr_cr"] > 0:
                    ir_efetivo_valor = e["vr_cr"]
                    ir_efetivo_fonte = "S-1210"
                    break
            if ir_efetivo_valor is None and ir_retido_s5002 is not None:
                ir_efetivo_valor = ir_retido_s5002
                ir_efetivo_fonte = "S-5002"
            if ir_efetivo_valor is None and ir_entries:
                ir_efetivo_valor = ir_entries[0].get("vr_cr")
                ir_efetivo_fonte = "S-1210"

            ultimo = envios[0] if envios else None

            # CNPJ raiz do empregador
            cur.execute(
                "SELECT cnpj FROM master_empresas WHERE id=%s",
                (internal_id,),
            )
            mrow = cur.fetchone()
            cnpj_raiz = (mrow["cnpj"][:8] if mrow and mrow.get("cnpj") else "")

            return {
                "cpf": cpf,
                "nome": scope_row["nome"],
                "matricula": scope_row["matricula"],
                "lote_num": lote_num,
                "per_apur": per_apur,
                "zip_encontrado": bool(zip_data),
                "zip_erro": None,
                "ind_retif_original": (
                    zip_data.get("ind_retif") if zip_data else None
                ),
                "dh_processamento": (
                    zip_data.get("dh_proc") if zip_data else None
                ),
                "nr_recibo_zip": (
                    zip_data.get("nr_recibo") if zip_data else None
                ),
                "nr_recibo_ativo": recibo_ativo,
                "recibo_fonte": recibo_fonte,
                "cadeia_candidatos": cadeia_n,
                "pagamentos": pagamentos,
                "total_vr_liq": round(total_liquido, 2) if pagamentos else None,
                "info_ir": ir_entries,
                "s5002_list": s5002_list,
                "s5002_ativo": s5002_ativo,
                "ir_efetivo_valor": ir_efetivo_valor,
                "ir_efetivo_fonte": ir_efetivo_fonte,
                "status_atual": (ultimo["status"] if ultimo else "pendente"),
                "ultimo_envio": ultimo,
                "historico_envios": envios,
                "qtd_envios": len(envios),
                "empregador_cnpj_raiz": cnpj_raiz,
                "tp_amb": "1",
                "proc_emi": "1",
                "ver_proc": "EasySocial_V2",
            }
    finally:
        conn.close()


# ═════════════════════════════════════════════════════════════════════
# GET /anual/xml-cpf/{lote_num}/{per_apur}/{cpf}?tipo=S-1210|S-5002
# ═════════════════════════════════════════════════════════════════════
@router.get("/anual/xml-cpf/{lote_num}/{per_apur}/{cpf}")
def baixar_xml_cpf(
    lote_num: int,
    per_apur: str,
    cpf: str,
    empresa_id: int = Query(...),
    tipo: str = Query("S-1210", pattern=r"^S-(1210|5002)$"),
):
    cpf = (cpf or "").strip().replace(".", "").replace("-", "")
    if len(cpf) != 11 or not cpf.isdigit():
        raise HTTPException(400, "CPF inválido")
    if not re.fullmatch(r"\d{4}-\d{2}", per_apur or ""):
        raise HTTPException(400, "per_apur deve estar no formato AAAA-MM")

    cfg = tenant.get_db_config_for_empresa(empresa_id)
    internal_id = tenant.internal_empresa_id(empresa_id)

    conn = psycopg2.connect(**cfg)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT e.id, e.xml_entry_name, e.xml_oid, e.xml_bytes,
                       z.conteudo_oid, z.tamanho_bytes, z.nome_arquivo_original
                  FROM explorador_eventos e
                  JOIN empresa_zips_brutos z ON z.id=e.zip_id
                 WHERE z.empresa_id=%s
                   AND e.tipo_evento=%s
                   AND e.cpf=%s
                   AND e.per_apur=%s
                 ORDER BY (e.retificado_por_id IS NULL) DESC,
                          e.dt_processamento DESC NULLS LAST,
                          e.id DESC
                 LIMIT 20
                """,
                (internal_id, tipo, cpf, per_apur),
            )
            rows = list(cur.fetchall() or [])
        if not rows:
            raise HTTPException(404, f"XML {tipo} não encontrado para este CPF/período")

        last_error = ""
        for row in rows:
            data: bytes | None = None
            if row.get("xml_bytes") is not None:
                data = bytes(row["xml_bytes"])

            if data is None and row.get("xml_oid") is not None:
                try:
                    lo = conn.lobject(int(row["xml_oid"]), mode="rb")
                    try:
                        data = lo.read()
                    finally:
                        lo.close()
                except Exception as exc:
                    conn.rollback()
                    last_error = str(exc).strip()
                    data = None

            if data is None and row.get("xml_entry_name"):
                try:
                    reader = storage.LargeObjectReader(
                        conn,
                        int(row["conteudo_oid"]),
                        int(row["tamanho_bytes"]),
                    )
                    try:
                        with zipfile.ZipFile(reader, mode="r") as zf:
                            with zf.open(row["xml_entry_name"]) as fh:
                                data = fh.read()
                    finally:
                        reader.close()
                except Exception as exc:
                    conn.rollback()
                    last_error = str(exc).strip()
                    data = None

            if data is not None:
                filename = (row.get("xml_entry_name") or f"{tipo}_{cpf}_{per_apur}.xml").split("/")[-1]
                headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
                return Response(content=data, media_type="application/xml", headers=headers)
    finally:
        conn.close()

    detail = "XML bruto existe no índice, mas o arquivo/large object não está mais recuperável"
    if last_error:
        detail = f"{detail}: {last_error}"
    raise HTTPException(404, detail)
