"""GET /api/s1210-repo/anual/detalhe-cpf/{lote}/{per_apur}/{cpf}

Porta direta do endpoint V1 `python-scripts/esocial/s1210_repo_routes.py:detalhe_cpf`
para o V2. Mesma SHAPE de JSON (front pode ser reaproveitado 1:1).

Diferenças vs V1 (zero invenção, só substituição de fonte):
  * V1 lê o ZIP do eSocial em disco a cada chamada (descompacta inteiro).
    V2 lê de `explorador_eventos` (XML individual já isolado em LO),
    aproveitando a indexação feita pelo Explorador no upload do ZIP.
  * Chain walk: V1 varre vários ZIPs futuros. V2 faz UMA query SQL em
    `explorador_eventos.referenciado_recibo` (já populado pelo extrator).
  * Multi-tenant: usa `tenant.get_db_config_for_empresa(empresa_id)` —
    mesmo padrão do overview anual já existente.
"""
from __future__ import annotations

import logging
import re
from typing import Optional

import psycopg2
import psycopg2.extras
from fastapi import APIRouter, HTTPException, Query, Response

from . import tenant
from .storage import open_lo
from .xml_extractor import extrair_s1210

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


# ─── Parser S-5002 (copiado do V1 _parse_s5002_xml) ───────────────────
def _parse_s5002_bytes(raw_bytes: bytes) -> Optional[dict]:
    raw = raw_bytes.decode("utf-8", errors="replace")
    m_cpf = re.search(r"<cpfBenef>([^<]+)</cpfBenef>", raw)
    m_per = re.search(r"<perApur>([^<]+)</perApur>", raw)
    m_id = re.search(r'Id="([^"]+)"', raw)
    if not (m_cpf and m_per and m_id):
        return None
    rec = {
        "cpf": m_cpf.group(1),
        "per_apur": m_per.group(1),
        "id": m_id.group(1),
        "nr_recibo": "1.1." + m_id.group(1)[-19:],
        "CRMen": None,
        "vlrRendTrib": None,
        "vlrPrevOficial": None,
        "vlrCRMen": None,
        "infoIR": [],
        "vazio": False,
    }
    mc = re.search(
        r"<consolidApurMen>.*?<CRMen>([^<]+)</CRMen>"
        r".*?<vlrRendTrib>([^<]+)</vlrRendTrib>"
        r".*?<vlrPrevOficial>([^<]+)</vlrPrevOficial>"
        r".*?<vlrCRMen>([^<]+)</vlrCRMen>",
        raw,
        re.DOTALL,
    )
    if mc:
        rec["CRMen"] = mc.group(1)
        rec["vlrRendTrib"] = mc.group(2)
        rec["vlrPrevOficial"] = mc.group(3)
        rec["vlrCRMen"] = mc.group(4)
    else:
        rec["vazio"] = True
    for tp, v in re.findall(
        r"<infoIR><tpInfoIR>([^<]+)</tpInfoIR><valor>([^<]+)</valor></infoIR>",
        raw,
    ):
        rec["infoIR"].append({"tpInfoIR": tp, "valor": v})
    return rec


def _read_lo_bytes(conn, oid: int) -> bytes:
    """Lê o conteúdo inteiro de um Large Object como bytes."""
    lo = open_lo(conn, int(oid))
    try:
        return lo.read()
    finally:
        lo.close()


def _to_float(v) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(str(v).replace(",", "."))
    except (ValueError, TypeError):
        return None


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

    Mantém SHAPE de resposta idêntica ao V1.
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
                    WHERE empresa_id=%s AND per_apur=%s AND lote_num=%s AND cpf=%s""",
                (internal_id, per_apur, lote_num, cpf),
            )
            scope_row = cur.fetchone()
            if not scope_row:
                # Fallback: CPF fora do scope mas pode existir no Explorador
                # (ex.: rescisão, evento órfão, lote diferente). Retornamos
                # mesmo assim para permitir auditoria pelo modal.
                cur.execute(
                    """SELECT nome FROM s1210_cpf_scope
                        WHERE empresa_id=%s AND cpf=%s LIMIT 1""",
                    (internal_id, cpf),
                )
                fallback = cur.fetchone()
                scope_row = {
                    "cpf": cpf,
                    "nome": (fallback or {}).get("nome"),
                    "matricula": None,
                    "lote_num": lote_num,
                    "per_apur": per_apur,
                }

            # 2) Histórico de envios
            cur.execute(
                """SELECT status, codigo_resposta, descricao_resposta,
                          nr_recibo_usado, nr_recibo_novo, protocolo,
                          erro_descricao, enviado_em
                     FROM s1210_cpf_envios
                    WHERE empresa_id=%s AND per_apur=%s AND lote_num=%s AND cpf=%s
                    ORDER BY enviado_em DESC""",
                (internal_id, per_apur, lote_num, cpf),
            )
            envios = list(cur.fetchall() or [])

            # 3) S-1210 do Explorador — pega o mais recente (id DESC)
            cur.execute(
                """SELECT id, nr_recibo, referenciado_recibo, dt_processamento,
                          xml_oid
                     FROM explorador_eventos
                    WHERE tipo_evento='S-1210' AND cpf=%s AND per_apur=%s
                      AND xml_oid IS NOT NULL
                    ORDER BY id DESC
                    LIMIT 1""",
                (cpf, per_apur),
            )
            s1210_row = cur.fetchone()

            zip_data: Optional[dict] = None
            zip_erro: Optional[str] = None
            if s1210_row:
                try:
                    xml_bytes = _read_lo_bytes(conn, s1210_row["xml_oid"])
                    extr = extrair_s1210(xml_bytes)
                    # adapta nomes para shape V1
                    info_ir_cr: list[dict] = []
                    irc = extr.get("info_ir_complem") or {}
                    for x in (irc.get("infoIRCR") or []):
                        info_ir_cr.append(
                            {"tpCR": x.get("tpCR"), "vrCR": x.get("vrCR")}
                        )
                    zip_data = {
                        "info_pgtos": extr.get("info_pgtos") or [],
                        "info_ir_cr": info_ir_cr,
                        "nr_recibo": s1210_row.get("nr_recibo")
                        or extr.get("nr_recibo_atual"),
                        "ind_retif": extr.get("ind_retif_atual"),
                        "dh_proc": (
                            s1210_row["dt_processamento"].isoformat()
                            if s1210_row.get("dt_processamento")
                            else None
                        ),
                    }
                except Exception as e:
                    zip_erro = str(e)
                    log.warning(
                        "detalhe-cpf: falha ao parsear S-1210 para %s: %s", cpf, e
                    )

            # 4) Chain walk — recibo ativo = nr_recibo que NÃO é referenciado por nenhum outro
            recibo_ativo: Optional[str] = None
            recibo_fonte: Optional[str] = None
            cadeia_n = 0
            if zip_data and zip_data.get("nr_recibo"):
                try:
                    cur.execute(
                        """WITH evts AS (
                              SELECT id, nr_recibo, referenciado_recibo
                                FROM explorador_eventos
                               WHERE tipo_evento='S-1210' AND cpf=%s AND per_apur=%s
                                 AND nr_recibo IS NOT NULL
                           )
                           SELECT e.nr_recibo,
                                  (SELECT COUNT(*) FROM evts) AS total
                             FROM evts e
                            WHERE NOT EXISTS (
                                  SELECT 1 FROM evts e2
                                   WHERE e2.referenciado_recibo = e.nr_recibo
                            )
                            ORDER BY e.id DESC
                            LIMIT 1""",
                        (cpf, per_apur),
                    )
                    r = cur.fetchone()
                    if r:
                        recibo_ativo = r["nr_recibo"]
                        cadeia_n = max(int(r["total"]) - 1, 0)
                        recibo_fonte = (
                            "zip"
                            if recibo_ativo == zip_data["nr_recibo"]
                            else "cadeia"
                        )
                except Exception as e:
                    log.warning(
                        "detalhe-cpf: chain walk falhou para %s: %s", cpf, e
                    )

            # 5) Pagamentos com label
            pagamentos: list[dict] = []
            total_liquido = 0.0
            if zip_data and zip_data.get("info_pgtos"):
                for p in zip_data["info_pgtos"]:
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

            # 6) infoIRCR do S-1210
            ir_entries: list[dict] = []
            if zip_data and zip_data.get("info_ir_cr"):
                for ir in zip_data["info_ir_cr"]:
                    tp = str(ir.get("tpCR") or "")
                    vr = _to_float(ir.get("vrCR"))
                    ir_entries.append({
                        "tp_cr": tp,
                        "tp_cr_label": _TP_CR_LABELS.get(tp, f"Código {tp}"),
                        "vr_cr": vr,
                        "vr_cr_raw": ir.get("vrCR"),
                    })

            # 7) S-5002 do Explorador
            cur.execute(
                """SELECT id, nr_recibo, xml_oid
                     FROM explorador_eventos
                    WHERE tipo_evento='S-5002' AND cpf=%s AND per_apur=%s
                      AND xml_oid IS NOT NULL
                    ORDER BY nr_recibo DESC, id DESC""",
                (cpf, per_apur),
            )
            s5002_rows = list(cur.fetchall() or [])

            s5002_list: list[dict] = []
            for r in s5002_rows:
                try:
                    raw = _read_lo_bytes(conn, r["xml_oid"])
                    rec = _parse_s5002_bytes(raw)
                    if not rec:
                        continue
                    s5002_list.append({
                        "nr_recibo": r.get("nr_recibo") or rec.get("nr_recibo"),
                        "id": rec.get("id"),
                        "vazio": rec.get("vazio", False),
                        "cr_men": rec.get("CRMen"),
                        "vlr_rend_trib": _to_float(rec.get("vlrRendTrib")),
                        "vlr_prev_oficial": _to_float(rec.get("vlrPrevOficial")),
                        "vlr_ir_retido": _to_float(rec.get("vlrCRMen")),
                        "info_ir": [
                            {
                                "tp_info_ir": it.get("tpInfoIR"),
                                "tp_info_ir_label": _TP_INFO_IR_LABELS.get(
                                    str(it.get("tpInfoIR")),
                                    f"tpInfoIR {it.get('tpInfoIR')}",
                                ),
                                "valor": _to_float(it.get("valor")),
                            }
                            for it in (rec.get("infoIR") or [])
                        ],
                    })
                except Exception as e:
                    log.warning(
                        "detalhe-cpf: falha ao parsear S-5002 id=%s: %s", r["id"], e
                    )

            # 8) S-5002 ativo: preferencialmente o vinculado ao recibo ativo
            s5002_ativo: Optional[dict] = None
            ativo_nr = recibo_ativo or (zip_data.get("nr_recibo") if zip_data else None)
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
            ir_retido_s5002 = s5002_ativo.get("vlr_ir_retido") if s5002_ativo else None

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

            # CNPJ raiz do empregador (master_empresas) — mostra no cabeçalho
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
                "zip_erro": zip_erro,
                "ind_retif_original": zip_data.get("ind_retif") if zip_data else None,
                "dh_processamento": zip_data.get("dh_proc") if zip_data else None,
                "nr_recibo_zip": zip_data.get("nr_recibo") if zip_data else None,
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
# Baixa o XML cru direto do Large Object (sem reabrir ZIP).
# ═════════════════════════════════════════════════════════════════════
@router.get("/anual/xml-cpf/{lote_num}/{per_apur}/{cpf}")
def baixar_xml_cpf(
    lote_num: int,
    per_apur: str,
    cpf: str,
    empresa_id: int = Query(...),
    tipo: str = Query("S-1210", regex=r"^S-(1210|5002)$"),
):
    cpf = (cpf or "").strip().replace(".", "").replace("-", "")
    if len(cpf) != 11 or not cpf.isdigit():
        raise HTTPException(400, "CPF inválido")
    if not re.fullmatch(r"\d{4}-\d{2}", per_apur or ""):
        raise HTTPException(400, "per_apur inválido")

    cfg = tenant.get_db_config_for_empresa(empresa_id)
    conn = psycopg2.connect(**cfg)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """SELECT xml_oid FROM explorador_eventos
                    WHERE tipo_evento=%s AND cpf=%s AND per_apur=%s
                      AND xml_oid IS NOT NULL
                    ORDER BY id DESC LIMIT 1""",
                (tipo, cpf, per_apur),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(
                    404, f"Nenhum {tipo} indexado para CPF {cpf} em {per_apur}"
                )
            data = _read_lo_bytes(conn, row["xml_oid"])
    finally:
        conn.close()

    fname = f"{tipo}_{cpf}_{per_apur}.xml"
    return Response(
        content=data,
        media_type="application/xml",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )
