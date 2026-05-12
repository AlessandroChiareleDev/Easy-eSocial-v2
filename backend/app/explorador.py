"""Router do Explorador — upload, extração, listagem."""
from __future__ import annotations

import json
import re
import zipfile
from datetime import date, datetime
from typing import Any, Optional

import psycopg2
import psycopg2.extras
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from . import config, db, storage, tenant
from .esocial_parser import parse_xml_bytes

router = APIRouter(prefix="/api/explorador", tags=["explorador"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SEQ_RE = re.compile(r"(\d{6,})")  # captura sequencial numérico do nome


def _extrair_sequencial(filename: str) -> str | None:
    """Tenta extrair sequencial numérico do nome do arquivo zip."""
    m = _SEQ_RE.search(filename)
    return m.group(1) if m else None


def _ensure_empresa(empresa_id: int) -> dict:
    from . import tenant
    internal_id = tenant.internal_empresa_id(empresa_id)
    with db.cursor(empresa_id=empresa_id) as c:
        c.execute("SELECT id, nome, tipo_estado FROM master_empresas WHERE id=%s", (internal_id,))
        row = c.fetchone()
    if not row:
        raise HTTPException(404, f"empresa_id={empresa_id} não existe em master_empresas")
    return dict(row)


def _log_atividade(
    empresa_id: int,
    acao: str,
    *,
    zip_id: int | None = None,
    nome_arquivo: str | None = None,
    sha256: str | None = None,
    tamanho_bytes: int | None = None,
    total_xmls: int | None = None,
    detalhe: dict | None = None,
) -> None:
    """Grava linha em explorador_atividade. Não levanta erro se falhar."""
    try:
        internal_id = tenant.internal_empresa_id(empresa_id)
        with db.cursor(commit=True, empresa_id=empresa_id) as c:
            c.execute(
                """
                INSERT INTO explorador_atividade
                  (empresa_id, acao, zip_id, nome_arquivo, sha256,
                   tamanho_bytes, total_xmls, detalhe)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    internal_id, acao, zip_id, nome_arquivo, sha256,
                    tamanho_bytes, total_xmls,
                    json.dumps(detalhe) if detalhe is not None else None,
                ),
            )
    except Exception as e:  # noqa: BLE001
        print(f"[WARN] _log_atividade falhou: {e}")


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------

@router.post("/zips/upload")
def upload_zip(
    arquivo: UploadFile = File(...),
    empresa_id: int = Form(...),
    dt_ini: str = Form(..., description="YYYY-MM-DD"),
    dt_fim: str = Form(..., description="YYYY-MM-DD"),
):
    """Recebe 1 zip, salva como Large Object no banco e registra metadados.

    Streaming: chunks de 4 MB direto pro pg_largeobject. SHA-256 calculado
    em paralelo. Dedup por (empresa_id, sha256).
    """
    _ensure_empresa(empresa_id)
    # IMPORTANTE: empresa_id da request é o externo (APPA=1, SOLUCOES=2).
    # No DB, rows da SOLUCOES guardam empresa_id=1 (convenção interna).
    internal_id = tenant.internal_empresa_id(empresa_id)

    try:
        d_ini = date.fromisoformat(dt_ini)
        d_fim = date.fromisoformat(dt_fim)
    except ValueError as e:
        raise HTTPException(400, f"data inválida: {e}")

    nome_original = arquivo.filename or "upload.zip"
    seq = _extrair_sequencial(nome_original)

    conn = db.connect(empresa_id)
    oid = None
    try:
        # 1) Stream → Large Object
        oid, total_bytes, sha256_hex = storage.write_lo_streaming(conn, arquivo.file)

        if total_bytes == 0:
            storage.unlink_lo(conn, oid)
            conn.commit()
            raise HTTPException(400, "arquivo vazio")
        if total_bytes > config.MAX_UPLOAD_BYTES:
            storage.unlink_lo(conn, oid)
            conn.commit()
            raise HTTPException(413, f"arquivo > {config.MAX_UPLOAD_BYTES} bytes")

        # 2) Dedup por (empresa_id, sha256) — usa internal_id
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT id FROM empresa_zips_brutos WHERE empresa_id=%s AND sha256=%s",
                (internal_id, sha256_hex),
            )
            existing = cur.fetchone()

        if existing:
            storage.unlink_lo(conn, oid)
            conn.commit()
            _log_atividade(
                empresa_id, "duplicado",
                zip_id=existing["id"],
                nome_arquivo=nome_original,
                sha256=sha256_hex,
                tamanho_bytes=total_bytes,
            )
            return {
                "ok": True,
                "duplicado": True,
                "zip_id": existing["id"],
                "sha256": sha256_hex,
                "tamanho_bytes": total_bytes,
                "mensagem": "zip já existia (sha256 igual). Nada gravado.",
            }

        # 3) Insere registro
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO empresa_zips_brutos
                  (empresa_id, dt_ini, dt_fim, sequencial_esocial,
                   nome_arquivo_original, sha256, tamanho_bytes, conteudo_oid,
                   extracao_status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'pendente')
                RETURNING id, enviado_em
                """,
                (internal_id, d_ini, d_fim, seq, nome_original, sha256_hex, total_bytes, oid),
            )
            ins = cur.fetchone()

        conn.commit()
        _log_atividade(
            empresa_id, "upload",
            zip_id=ins["id"],
            nome_arquivo=nome_original,
            sha256=sha256_hex,
            tamanho_bytes=total_bytes,
            detalhe={"dt_ini": dt_ini, "dt_fim": dt_fim, "sequencial": seq},
        )
        return {
            "ok": True,
            "duplicado": False,
            "zip_id": ins["id"],
            "sha256": sha256_hex,
            "tamanho_bytes": total_bytes,
            "sequencial_esocial": seq,
            "enviado_em": ins["enviado_em"].isoformat(),
        }
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        if oid:
            try:
                storage.unlink_lo(conn, oid)
                conn.commit()
            except Exception:  # noqa: BLE001
                pass
        raise HTTPException(500, f"falha no upload: {e}")
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Listagem
# ---------------------------------------------------------------------------

@router.get("/zips")
def listar_zips(empresa_id: int, limit: int = 100, offset: int = 0):
    from . import tenant
    internal_id = tenant.internal_empresa_id(empresa_id)
    with db.cursor(empresa_id=empresa_id) as c:
        c.execute(
            """
            SELECT id, empresa_id, dt_ini, dt_fim, sequencial_esocial,
                   nome_arquivo_original, sha256, tamanho_bytes,
                   total_xmls, perapur_dominante,
                   enviado_em, extraido_em, extracao_status, extracao_erro
            FROM empresa_zips_brutos
            WHERE empresa_id=%s
            ORDER BY enviado_em DESC
            LIMIT %s OFFSET %s
            """,
            (internal_id, limit, offset),
        )
        rows = [dict(r) for r in c.fetchall()]
    # serialize datas
    for r in rows:
        for k in ("dt_ini", "dt_fim", "enviado_em", "extraido_em"):
            if r.get(k) is not None:
                r[k] = r[k].isoformat()
    return {"ok": True, "total": len(rows), "items": rows}


@router.get("/zips/{zip_id}")
def detalhe_zip(zip_id: int):
    with db.cursor() as c:
        c.execute(
            "SELECT * FROM empresa_zips_brutos WHERE id=%s",
            (zip_id,),
        )
        row = c.fetchone()
        if not row:
            raise HTTPException(404, "zip não encontrado")
        c.execute(
            "SELECT COUNT(*) AS n FROM explorador_eventos WHERE zip_id=%s",
            (zip_id,),
        )
        n_evts = c.fetchone()["n"]
    out = dict(row)
    out["conteudo_oid"] = int(out["conteudo_oid"])
    for k in ("dt_ini", "dt_fim", "enviado_em", "extraido_em"):
        if out.get(k) is not None:
            out[k] = out[k].isoformat()
    out["eventos_indexados"] = n_evts
    return {"ok": True, "zip": out}


@router.post("/zips/{zip_id}/reupload")
def reupload_zip(
    zip_id: int,
    arquivo: UploadFile = File(...),
    forcar: bool = Form(False, description="Se True, aceita SHA-256 diferente"),
    empresa_id: Optional[int] = Form(None, description="Tenant alvo (default: tenta todos)"),
):
    """Substitui o Large Object do ZIP existente (recupera card com LO perdido).

    Útil quando `extracao_status='erro'` com mensagem "large object N does not exist".
    Por padrão exige SHA-256 idêntico ao registrado. Use `forcar=True` para aceitar
    qualquer arquivo (cuidado: vai sobrescrever metadados de tamanho/sha).
    """
    nome_original = arquivo.filename or "reupload.zip"

    # 1) lê o card existente. Se empresa_id não foi passado, varre tenants conhecidos
    #    (multi-tenant: cada empresa tem seu próprio DB, então db.cursor() default = APPA).
    tenants_a_tentar = [empresa_id] if empresa_id is not None else [tenant.APPA_ID, tenant.SOLUCOES_ID]
    row = None
    tenant_id_achado: Optional[int] = None
    for eid in tenants_a_tentar:
        with db.cursor(empresa_id=eid) as c:
            c.execute(
                """SELECT id, empresa_id, conteudo_oid, sha256, tamanho_bytes,
                          nome_arquivo_original, extracao_status
                   FROM empresa_zips_brutos WHERE id=%s""",
                (zip_id,),
            )
            row = c.fetchone()
            if row:
                tenant_id_achado = eid
                break
    if not row or tenant_id_achado is None:
        raise HTTPException(404, "zip não encontrado")

    # IMPORTANTE: usar tenant_id_achado pra conectar, NÃO row["empresa_id"]
    # (no BD SOLUCOES, rows guardam empresa_id=1 internamente — convenção do tenant.py)
    empresa_id = tenant_id_achado
    old_oid = int(row["conteudo_oid"]) if row["conteudo_oid"] is not None else None
    sha_esperado = row["sha256"]
    tam_esperado = row["tamanho_bytes"]

    conn = db.connect(empresa_id)
    new_oid = None
    try:
        # 2) stream do novo arquivo → novo LO
        new_oid, total_bytes, sha256_hex = storage.write_lo_streaming(conn, arquivo.file)

        if total_bytes == 0:
            storage.unlink_lo(conn, new_oid)
            conn.commit()
            raise HTTPException(400, "arquivo vazio")
        if total_bytes > config.MAX_UPLOAD_BYTES:
            storage.unlink_lo(conn, new_oid)
            conn.commit()
            raise HTTPException(413, f"arquivo > {config.MAX_UPLOAD_BYTES} bytes")

        # 3) validação de identidade (a menos que forcar=True)
        if not forcar:
            if sha_esperado and sha256_hex != sha_esperado:
                storage.unlink_lo(conn, new_oid)
                conn.commit()
                raise HTTPException(
                    400,
                    f"SHA-256 não bate (esperado={sha_esperado[:16]}…, recebido={sha256_hex[:16]}…). "
                    "Use forcar=true para sobrescrever mesmo assim.",
                )
            if tam_esperado and total_bytes != tam_esperado:
                storage.unlink_lo(conn, new_oid)
                conn.commit()
                raise HTTPException(
                    400,
                    f"tamanho não bate (esperado={tam_esperado}, recebido={total_bytes}). "
                    "Use forcar=true para sobrescrever.",
                )

        # 4) atualiza card: aponta para o novo LO, reseta status, atualiza meta
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE empresa_zips_brutos
                      SET conteudo_oid = %s,
                          sha256 = %s,
                          tamanho_bytes = %s,
                          extracao_status = 'pendente',
                          extracao_erro = NULL,
                          extraido_em = NULL
                    WHERE id = %s""",
                (new_oid, sha256_hex, total_bytes, zip_id),
            )

        # 5) tenta apagar o LO antigo (pode já não existir — ignora erro)
        if old_oid and old_oid != new_oid:
            try:
                storage.unlink_lo(conn, old_oid)
            except Exception:  # noqa: BLE001
                pass

        conn.commit()
        _log_atividade(
            empresa_id, "reupload",
            zip_id=zip_id,
            nome_arquivo=nome_original,
            sha256=sha256_hex,
            tamanho_bytes=total_bytes,
            detalhe={
                "oid_antigo": old_oid,
                "oid_novo": new_oid,
                "sha_bate": sha_esperado == sha256_hex,
                "forcado": forcar,
            },
        )
        return {
            "ok": True,
            "zip_id": zip_id,
            "sha256": sha256_hex,
            "tamanho_bytes": total_bytes,
            "oid_antigo": old_oid,
            "oid_novo": new_oid,
            "sha_bate": sha_esperado == sha256_hex,
        }
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        print(f"[REUPLOAD ERROR zip_id={zip_id} tenant={empresa_id}]\n{tb}", flush=True)
        conn.rollback()
        if new_oid:
            try:
                storage.unlink_lo(conn, new_oid)
                conn.commit()
            except Exception:  # noqa: BLE001
                pass
        raise HTTPException(500, f"falha no reupload: {type(e).__name__}: {e} | TB(last): {tb.strip().splitlines()[-3:]}")
    finally:
        conn.close()


@router.delete("/zips/{zip_id}")
def deletar_zip(zip_id: int, empresa_id: Optional[int] = None):
    """Apaga zip + eventos indexados + Large Object do conteúdo.

    Multi-tenant: se `empresa_id` não vier, varre APPA e SOLUCOES até achar.
    """
    # 1) descobre em qual tenant o zip mora
    tenants_a_tentar = [empresa_id] if empresa_id is not None else [tenant.APPA_ID, tenant.SOLUCOES_ID]
    tenant_id_achado: Optional[int] = None
    row = None
    for eid in tenants_a_tentar:
        with db.cursor(empresa_id=eid) as c:
            c.execute(
                """SELECT empresa_id, conteudo_oid, nome_arquivo_original,
                          sha256, tamanho_bytes, total_xmls
                   FROM empresa_zips_brutos WHERE id=%s""",
                (zip_id,),
            )
            row = c.fetchone()
            if row:
                tenant_id_achado = eid
                break
    if not row or tenant_id_achado is None:
        raise HTTPException(404, "zip não encontrado")

    conn = db.connect(tenant_id_achado)
    info: dict = {}
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        info = dict(row)
        oid = int(row["conteudo_oid"]) if row["conteudo_oid"] is not None else None
        # coleta xml_oid de cada evento para apagar os LOs depois
        cur.execute(
            "SELECT xml_oid FROM explorador_eventos "
            "WHERE zip_id=%s AND xml_oid IS NOT NULL",
            (zip_id,),
        )
        xml_oids = [int(r["xml_oid"]) for r in cur.fetchall()]
        cur.execute("DELETE FROM explorador_eventos WHERE zip_id=%s", (zip_id,))
        n_evts = cur.rowcount
        cur.execute("DELETE FROM empresa_zips_brutos WHERE id=%s", (zip_id,))
        # apaga LO do zip (pode ja nao existir — tolera)
        if oid is not None:
            try:
                storage.unlink_lo(conn, oid)
            except Exception:  # noqa: BLE001
                pass
        # apaga LOs por evento
        for x_oid in xml_oids:
            try:
                storage.unlink_lo(conn, x_oid)
            except Exception:  # noqa: BLE001
                pass
        conn.commit()
        cur.close()
    except HTTPException:
        conn.rollback()
        raise
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    _log_atividade(
        tenant_id_achado, "exclusao",
        zip_id=zip_id,
        nome_arquivo=info.get("nome_arquivo_original"),
        sha256=info.get("sha256"),
        tamanho_bytes=info.get("tamanho_bytes"),
        total_xmls=info.get("total_xmls"),
        detalhe={"eventos_apagados": n_evts},
    )
    return {"ok": True, "zip_id": zip_id, "eventos_apagados": n_evts}


@router.get("/atividade")
def listar_atividade(empresa_id: int, limit: int = 200):
    """Histórico de upload/exclusão/extração/duplicado."""
    from . import tenant
    internal_id = tenant.internal_empresa_id(empresa_id)
    with db.cursor(empresa_id=empresa_id) as c:
        c.execute(
            """
            SELECT id, empresa_id, acao, zip_id, nome_arquivo, sha256,
                   tamanho_bytes, total_xmls, detalhe, criado_em
            FROM explorador_atividade
            WHERE empresa_id=%s
            ORDER BY criado_em DESC
            LIMIT %s
            """,
            (internal_id, limit),
        )
        rows = [dict(r) for r in c.fetchall()]
    for r in rows:
        if r.get("criado_em") is not None:
            r["criado_em"] = r["criado_em"].isoformat()
    return {"ok": True, "total": len(rows), "items": rows}


@router.get("/zips/{zip_id}/download")
def download_zip(zip_id: int):
    """Devolve o zip original (auditoria). Streaming direto do Large Object."""
    with db.cursor() as c:
        c.execute(
            "SELECT conteudo_oid, tamanho_bytes, nome_arquivo_original "
            "FROM empresa_zips_brutos WHERE id=%s",
            (zip_id,),
        )
        row = c.fetchone()
    if not row:
        raise HTTPException(404, "zip não encontrado")

    conn = db.connect()

    def gen():
        try:
            for chunk in storage.iter_lo_bytes(conn, int(row["conteudo_oid"])):
                yield chunk
        finally:
            conn.close()

    headers = {
        "Content-Disposition": f'attachment; filename="{row["nome_arquivo_original"]}"',
        "Content-Length": str(row["tamanho_bytes"]),
    }
    return StreamingResponse(gen(), media_type="application/zip", headers=headers)


# ---------------------------------------------------------------------------
# Extração
# ---------------------------------------------------------------------------

def _extrair_zip_sync(zip_id: int, somente_s5002: bool = False, empresa_id: int | None = None) -> dict:
    """Lê o zip do Large Object e popula explorador_eventos.

    Usa DUAS conexões:
      - conn_lo: mantida em transação aberta para o Large Object permanecer válido.
      - conn_db: para INSERTs/UPDATEs com commits/rollbacks livres.

    Parametros:
      somente_s5002: se True, IGNORA totalmente eventos S-1210 (nem insere
        nem atualiza). Útil para re-extrair um ZIP de mês já enviado e
        enriquecer só o S-5002, sem risco de tocar nos S-1210.
      empresa_id: roteia para o tenant correto (default APPA=1). ZIPs da
        SOLUCOES (empresa_id=2) estão em outro banco.
    """
    conn_db = db.connect(empresa_id=empresa_id)
    conn_lo = db.connect(empresa_id=empresa_id)
    conn_w = db.connect(empresa_id=empresa_id)  # escreve LOs por evento (sem invalidar reader)
    try:
        # marca como extraindo
        with conn_db.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT id, empresa_id, conteudo_oid, tamanho_bytes, nome_arquivo_original, dt_ini, dt_fim "
                "FROM empresa_zips_brutos WHERE id=%s FOR UPDATE",
                (zip_id,),
            )
            zrow = cur.fetchone()
            if not zrow:
                raise HTTPException(404, "zip não encontrado")
            cur.execute(
                "UPDATE empresa_zips_brutos SET extracao_status='extraindo', extracao_erro=NULL WHERE id=%s",
                (zip_id,),
            )
        conn_db.commit()

        oid = int(zrow["conteudo_oid"])
        size = int(zrow["tamanho_bytes"])

        # cria importacao
        periodo = zrow["dt_ini"].strftime("%Y-%m")
        with conn_db.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "INSERT INTO explorador_importacoes (pasta, periodo, total_arquivos) "
                "VALUES (%s, %s, 0) RETURNING id",
                (zrow["nome_arquivo_original"], periodo),
            )
            importacao_id = cur.fetchone()["id"]
        conn_db.commit()

        total = 0
        ok = 0
        falhas = 0
        duplicados = 0
        per_counter: dict[str, int] = {}

        # abre LO na conn_lo (transação fica aberta enquanto lê)
        reader = storage.LargeObjectReader(conn_lo, oid, size)
        try:
            with zipfile.ZipFile(reader, mode="r") as zf:
                names = [n for n in zf.namelist() if n.lower().endswith(".xml")]
                for name in names:
                    total += 1
                    try:
                        with zf.open(name) as fh:
                            data = fh.read()
                        evt = parse_xml_bytes(data)
                        if evt is None:
                            falhas += 1
                            continue
                        # Modo "somente S-5002": pula totalmente qualquer
                        # evento que não seja S-5002 (S-1210 e demais).
                        if somente_s5002 and evt.tipo_evento != "S-5002":
                            continue
                        if evt.per_apur:
                            per_counter[evt.per_apur] = per_counter.get(evt.per_apur, 0) + 1
                        # cria 1 Large Object por evento (xml_oid).
                        # Usa conn_w (terceira conexao) para que commits
                        # incrementais nao invalidem o LO descriptor que
                        # mantem o ZipFile aberto em conn_lo.
                        import hashlib as _hl
                        x_lo = conn_w.lobject(0, mode="wb")
                        x_oid = x_lo.oid
                        try:
                            x_lo.write(data)
                        finally:
                            x_lo.close()
                        x_size = len(data)
                        x_sha = _hl.sha256(data).hexdigest()
                        # Enriquece dados_json para S-1210 e S-5002 com os
                        # campos lidos do XML (pagamentos, infoIRCR, etc.) —
                        # demais eventos seguem com {nome_tecnico} apenas.
                        dados_json_payload: dict = {"nome_tecnico": evt.nome_tecnico}
                        try:
                            if evt.tipo_evento == "S-1210":
                                from .xml_extractor import extrair_s1210 as _ex_s1210
                                d = _ex_s1210(data) or {}
                                dados_json_payload.update({
                                    "pagamentos": d.get("info_pgtos") or [],
                                    "infoIRCR": (d.get("info_ir_complem") or {}).get("infoIRCR") or [],
                                    "planSaude": d.get("plan_saude"),
                                    "indRetif": d.get("ind_retif_atual"),
                                    "nrReciboAtual": d.get("nr_recibo_atual"),
                                })
                            elif evt.tipo_evento == "S-5002":
                                from .xml_extractor import extrair_s5002 as _ex_s5002
                                d = _ex_s5002(data) or {}
                                dados_json_payload.update({
                                    "infoIR": d.get("infoIR") or [],
                                    "totApurMen_CRMen": d.get("totApurMen_CRMen"),
                                    "totApurMen_vlrRendTrib": d.get("totApurMen_vlrRendTrib"),
                                    "totApurMen_vlrPrevOficial": d.get("totApurMen_vlrPrevOficial"),
                                    "totApurMen_vlrCRMen": d.get("totApurMen_vlrCRMen"),
                                })
                        except Exception as _ex_enrich:  # noqa: BLE001
                            # Falha de enriquecimento não derruba indexação;
                            # mantemos pelo menos {nome_tecnico} pra não
                            # quebrar inserts existentes.
                            print(f"[WARN] enrich dados_json ({evt.tipo_evento}): {_ex_enrich}")

                        with conn_db.cursor() as cur2:
                            cur2.execute(
                                """
                                INSERT INTO explorador_eventos
                                  (importacao_id, tipo_evento, cpf, per_apur,
                                   nr_recibo, id_evento, dt_processamento,
                                   cd_resposta, arquivo_origem, dados_json,
                                   zip_id, xml_entry_name, referenciado_recibo,
                                   xml_oid, xml_size_bytes, xml_sha256)
                                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                                ON CONFLICT (id_evento) WHERE id_evento IS NOT NULL DO UPDATE
                                  SET dados_json = EXCLUDED.dados_json
                                  WHERE explorador_eventos.tipo_evento IN ('S-1210','S-5002')
                                    AND (
                                      explorador_eventos.dados_json IS NULL
                                      OR NOT (
                                        explorador_eventos.dados_json ? 'pagamentos'
                                        OR explorador_eventos.dados_json ? 'infoIRCR'
                                        OR explorador_eventos.dados_json ? 'infoIR'
                                        OR explorador_eventos.dados_json ? 'totApurMen_CRMen'
                                      )
                                    )
                                RETURNING id, (xmax = 0) AS inserted_new
                                """,
                                (
                                    importacao_id,
                                    evt.tipo_evento,
                                    evt.cpf,
                                    evt.per_apur,
                                    evt.nr_recibo,
                                    evt.id_evento,
                                    evt.dt_processamento,
                                    evt.cd_resposta,
                                    name,
                                    json.dumps(dados_json_payload),
                                    zip_id,
                                    name,
                                    evt.referenciado_recibo,
                                    x_oid,
                                    x_size,
                                    x_sha,
                                ),
                            )
                            row_ret = cur2.fetchone()
                        # RETURNING devolve linha em INSERT e em UPDATE; só
                        # devolve None se o ON CONFLICT bater no WHERE e
                        # filtrar (linha já tinha dados_json rico).
                        # row_ret é tupla: (id, inserted_new_bool)
                        inserted = bool(row_ret and row_ret[1])
                        if row_ret is None:
                            # já existia e dados_json já era rico → duplicado puro
                            duplicados += 1
                            try:
                                storage.unlink_lo(conn_w, x_oid)
                            except Exception:  # noqa: BLE001
                                pass
                        elif not inserted:
                            # UPDATE (enriqueceu dados_json de linha antiga)
                            duplicados += 1
                            # LO criado virou órfão (linha antiga já tem xml_oid)
                            try:
                                storage.unlink_lo(conn_w, x_oid)
                            except Exception:  # noqa: BLE001
                                pass
                        else:
                            ok += 1
                        # commit em lotes
                        if (ok + duplicados) % 500 == 0:
                            conn_db.commit()
                            conn_w.commit()
                    except Exception as ex_inner:  # noqa: BLE001
                        falhas += 1
                        conn_db.rollback()
                        try:
                            conn_w.rollback()
                        except Exception:  # noqa: BLE001
                            pass
                conn_db.commit()
                conn_w.commit()
        finally:
            reader.close()
            try:
                conn_lo.rollback()  # libera transacao do LO do zip
            except Exception:  # noqa: BLE001
                pass

        # perApur dominante
        per_dom = max(per_counter.items(), key=lambda kv: kv[1])[0] if per_counter else None

        with conn_db.cursor() as cur:
            cur.execute(
                """
                UPDATE empresa_zips_brutos
                SET extracao_status='ok',
                    extraido_em=now(),
                    total_xmls=%s,
                    perapur_dominante=%s
                WHERE id=%s
                """,
                (total, per_dom, zip_id),
            )
            cur.execute(
                "UPDATE explorador_importacoes SET total_arquivos=%s, importado_em=now() WHERE id=%s",
                (total, importacao_id),
            )
        conn_db.commit()
        # backfill chain walk para o(s) per_apur que apareceram neste zip
        try:
            from . import backfill_chain
            with db.cursor() as _c:
                _c.execute(
                    "SELECT empresa_id FROM empresa_zips_brutos WHERE id=%s",
                    (zip_id,),
                )
                _r = _c.fetchone()
            if _r:
                _conn = db.connect()
                try:
                    backfill_chain.backfill_empresa(_conn, _r["empresa_id"])
                finally:
                    _conn.close()
        except Exception as e:  # noqa: BLE001
            print(f"[WARN] backfill_chain pós-extração falhou: {e}")
        return {
            "ok": True,
            "zip_id": zip_id,
            "total_xmls": total,
            "indexados": ok,
            "duplicados_id_evento": duplicados,
            "falhas": falhas,
            "perapur_dominante": per_dom,
        }
    except Exception as e:
        try:
            conn_db.rollback()
        except Exception:  # noqa: BLE001
            pass
        try:
            with conn_db.cursor() as cur:
                cur.execute(
                    "UPDATE empresa_zips_brutos SET extracao_status='erro', extracao_erro=%s WHERE id=%s",
                    (str(e)[:1000], zip_id),
                )
            conn_db.commit()
        except Exception:  # noqa: BLE001
            pass
        raise
    finally:
        try:
            conn_w.close()
        except Exception:  # noqa: BLE001
            pass
        try:
            conn_lo.close()
        except Exception:  # noqa: BLE001
            pass
        try:
            conn_db.close()
        except Exception:  # noqa: BLE001
            pass


@router.post("/zips/{zip_id}/extrair")
def extrair_zip(zip_id: int, somente_s5002: bool = False, empresa_id: int | None = None):
    """Extração SÍNCRONA (MVP). Pode demorar para zips grandes.

    Query param `somente_s5002=true`: ignora completamente eventos S-1210
    (não insere nem atualiza). Útil para re-extrair um ZIP de mês já
    enviado e enriquecer apenas o S-5002 sem risco de tocar nos S-1210.

    Query param `empresa_id`: roteia para o tenant correto. Se nao for
    informado ou se o zip nao for achado no tenant pedido, varre os
    tenants conhecidos (APPA, SOLUCOES) antes de devolver 404 - mesmo
    padrao usado em /reupload pra resiliencia a search_path errado.
    """
    # Tenta primeiro o tenant pedido; se 404, tenta o outro tenant antes
    # de propagar o erro. Isso protege contra:
    #  - frontend que esquece de mandar empresa_id na query
    #  - search_path resetando entre upload e extract (pgbouncer/pooler)
    tenants_a_tentar: list[int | None] = []
    if empresa_id is not None:
        tenants_a_tentar.append(empresa_id)
        # adiciona fallback pro outro tenant
        outro = tenant.APPA_ID if empresa_id == tenant.SOLUCOES_ID else tenant.SOLUCOES_ID
        tenants_a_tentar.append(outro)
    else:
        tenants_a_tentar = [tenant.APPA_ID, tenant.SOLUCOES_ID]

    last_404: HTTPException | None = None
    res: dict | None = None
    tenant_usado: int | None = None
    for eid in tenants_a_tentar:
        try:
            res = _extrair_zip_sync(zip_id, somente_s5002=somente_s5002, empresa_id=eid)
            tenant_usado = eid
            break
        except HTTPException as exc:
            if exc.status_code == 404:
                last_404 = exc
                continue
            raise
    if res is None:
        # nao achou em nenhum tenant — adiciona diagnostico pro front
        achou_em: list[str] = []
        for eid in (tenant.APPA_ID, tenant.SOLUCOES_ID):
            try:
                with db.cursor(empresa_id=eid) as c:
                    c.execute(
                        "SELECT id, empresa_id, nome_arquivo_original FROM empresa_zips_brutos WHERE id=%s",
                        (zip_id,),
                    )
                    r = c.fetchone()
                if r:
                    achou_em.append(f"tenant={eid}/empresa_id_interno={r['empresa_id']}/nome={r['nome_arquivo_original']}")
            except Exception as _e:  # noqa: BLE001
                achou_em.append(f"tenant={eid}/erro={_e}")
        diag = "; ".join(achou_em) if achou_em else "nao existe em nenhum tenant conhecido"
        raise HTTPException(
            404,
            f"zip não encontrado (id={zip_id}, tentou tenants={tenants_a_tentar}, diag=[{diag}])",
        )
    # log de atividade (best-effort)
    try:
        with db.cursor() as c:
            c.execute(
                "SELECT empresa_id, nome_arquivo_original, sha256, tamanho_bytes "
                "FROM empresa_zips_brutos WHERE id=%s",
                (zip_id,),
            )
            row = c.fetchone()
        if row:
            _log_atividade(
                row["empresa_id"], "extracao",
                zip_id=zip_id,
                nome_arquivo=row["nome_arquivo_original"],
                sha256=row["sha256"],
                tamanho_bytes=row["tamanho_bytes"],
                total_xmls=res.get("total_xmls"),
                detalhe={
                    "indexados": res.get("indexados"),
                    "duplicados_id_evento": res.get("duplicados_id_evento"),
                    "falhas": res.get("falhas"),
                    "perapur_dominante": res.get("perapur_dominante"),
                    "somente_s5002": somente_s5002,
                },
            )
    except Exception:  # noqa: BLE001
        pass
    return res


# ---------------------------------------------------------------------------
# Analise S-5002 (multi-zip)
# ---------------------------------------------------------------------------

from fastapi import Body  # noqa: E402


@router.post("/zips/analise-s5002")
def analise_s5002(payload: dict = Body(...)):
    """Compara cobertura de S-5002 vs S-1210 nos ZIPs informados.

    Body: { empresa_id: int, zip_ids: list[int] }

    Para cada per_apur que aparece nos ZIPs, conta:
      - cpfs_s1210:           CPFs distintos com S-1210
      - cpfs_s5002:           CPFs distintos com S-5002 (qualquer)
      - cpfs_s5002_ricos:     CPFs com S-5002 e dados_json contendo 'infoIR'
        (ou seja, enriquecidos pelo extrator novo)
      - cpfs_s5002_pobres:    CPFs com S-5002 sem 'infoIR' no dados_json
      - cpfs_faltando_s5002:  CPFs com S-1210 mas SEM S-5002 algum

    Também retorna amostras (até 50) dos faltantes/pobres p/ debug.
    """
    empresa_id = payload.get("empresa_id")
    zip_ids = payload.get("zip_ids") or []
    if not isinstance(empresa_id, int):
        raise HTTPException(400, "empresa_id (int) obrigatório")
    if not isinstance(zip_ids, list) or not zip_ids:
        raise HTTPException(400, "zip_ids (list[int]) obrigatório")
    zip_ids = [int(z) for z in zip_ids]

    with db.cursor(empresa_id=empresa_id) as c:
        # zips informados (valida tenant)
        c.execute(
            """
            SELECT id, nome_arquivo_original, perapur_dominante, total_xmls
            FROM empresa_zips_brutos
            WHERE empresa_id=%s AND id = ANY(%s)
            ORDER BY id
            """,
            (empresa_id, zip_ids),
        )
        zips_info = [dict(r) for r in c.fetchall()]
        if not zips_info:
            raise HTTPException(404, "nenhum zip encontrado nesse tenant")
        valid_ids = [z["id"] for z in zips_info]

        # agrega por per_apur — uma query só com FILTER
        c.execute(
            """
            WITH base AS (
              SELECT per_apur, tipo_evento, cpf,
                     (dados_json ? 'infoIR') AS s5002_rico
              FROM explorador_eventos
              WHERE zip_id = ANY(%s)
                AND tipo_evento IN ('S-1210','S-5002')
                AND cpf IS NOT NULL
                AND per_apur IS NOT NULL
            )
            SELECT per_apur,
              COUNT(DISTINCT cpf) FILTER (WHERE tipo_evento='S-1210') AS cpfs_s1210,
              COUNT(DISTINCT cpf) FILTER (WHERE tipo_evento='S-5002') AS cpfs_s5002,
              COUNT(DISTINCT cpf) FILTER (WHERE tipo_evento='S-5002' AND s5002_rico) AS cpfs_s5002_ricos,
              COUNT(DISTINCT cpf) FILTER (WHERE tipo_evento='S-5002' AND NOT s5002_rico) AS cpfs_s5002_pobres
            FROM base
            GROUP BY per_apur
            ORDER BY per_apur
            """,
            (valid_ids,),
        )
        por_perapur_raw = [dict(r) for r in c.fetchall()]

        # CPFs S-1210 sem S-5002 (faltando) por per_apur — amostra
        c.execute(
            """
            WITH s1210 AS (
              SELECT DISTINCT per_apur, cpf FROM explorador_eventos
              WHERE zip_id = ANY(%s) AND tipo_evento='S-1210'
                AND cpf IS NOT NULL AND per_apur IS NOT NULL
            ),
            s5002 AS (
              SELECT DISTINCT per_apur, cpf FROM explorador_eventos
              WHERE zip_id = ANY(%s) AND tipo_evento='S-5002'
                AND cpf IS NOT NULL AND per_apur IS NOT NULL
            ),
            faltando AS (
              SELECT s.per_apur, s.cpf
              FROM s1210 s
              LEFT JOIN s5002 t USING (per_apur, cpf)
              WHERE t.cpf IS NULL
            )
            SELECT per_apur, cpf,
                   row_number() OVER (PARTITION BY per_apur ORDER BY cpf) AS rn
            FROM faltando
            """,
            (valid_ids, valid_ids),
        )
        falt_rows = c.fetchall()
        amostra_faltando: dict[str, list[str]] = {}
        totais_faltando: dict[str, int] = {}
        for r in falt_rows:
            per = r["per_apur"]
            totais_faltando[per] = totais_faltando.get(per, 0) + 1
            if r["rn"] <= 50:
                amostra_faltando.setdefault(per, []).append(r["cpf"])

        # CPFs S-5002 pobres (sem infoIR) — amostra
        c.execute(
            """
            SELECT per_apur, cpf
            FROM (
              SELECT per_apur, cpf,
                     row_number() OVER (PARTITION BY per_apur ORDER BY cpf) AS rn
              FROM (
                SELECT DISTINCT per_apur, cpf
                FROM explorador_eventos
                WHERE zip_id = ANY(%s)
                  AND tipo_evento='S-5002'
                  AND cpf IS NOT NULL AND per_apur IS NOT NULL
                  AND NOT (dados_json ? 'infoIR')
              ) q
            ) qq
            WHERE rn <= 50
            """,
            (valid_ids,),
        )
        amostra_pobre: dict[str, list[str]] = {}
        for r in c.fetchall():
            amostra_pobre.setdefault(r["per_apur"], []).append(r["cpf"])

    # consolida
    por_perapur = []
    tot_s1210 = tot_s5002 = tot_ricos = tot_pobres = tot_faltando = 0
    for r in por_perapur_raw:
        per = r["per_apur"]
        faltando_n = totais_faltando.get(per, 0)
        item = {
            "per_apur": per,
            "cpfs_s1210": int(r["cpfs_s1210"] or 0),
            "cpfs_s5002": int(r["cpfs_s5002"] or 0),
            "cpfs_s5002_ricos": int(r["cpfs_s5002_ricos"] or 0),
            "cpfs_s5002_pobres": int(r["cpfs_s5002_pobres"] or 0),
            "cpfs_faltando_s5002": faltando_n,
            "amostra_faltando": amostra_faltando.get(per, []),
            "amostra_pobre": amostra_pobre.get(per, []),
        }
        tot_s1210 += item["cpfs_s1210"]
        tot_s5002 += item["cpfs_s5002"]
        tot_ricos += item["cpfs_s5002_ricos"]
        tot_pobres += item["cpfs_s5002_pobres"]
        tot_faltando += faltando_n
        por_perapur.append(item)

    return {
        "ok": True,
        "zips": zips_info,
        "totais": {
            "cpfs_s1210": tot_s1210,
            "cpfs_s5002": tot_s5002,
            "cpfs_s5002_ricos": tot_ricos,
            "cpfs_s5002_pobres": tot_pobres,
            "cpfs_faltando_s5002": tot_faltando,
        },
        "por_perapur": por_perapur,
    }


# ---------------------------------------------------------------------------
# Eventos
# ---------------------------------------------------------------------------

@router.get("/eventos")
def listar_eventos(
    empresa_id: int,
    cpf: str | None = None,
    per_apur: str | None = None,
    tipo_evento: str | None = None,
    zip_id: int | None = None,
    limit: int = 200,
    offset: int = 0,
):
    sql = [
        """
        SELECT e.id, e.tipo_evento, e.cpf, e.per_apur, e.nr_recibo,
               e.id_evento, e.referenciado_recibo, e.zip_id, e.xml_entry_name,
               z.nome_arquivo_original, z.dt_ini, z.dt_fim
        FROM explorador_eventos e
        JOIN empresa_zips_brutos z ON z.id = e.zip_id
        WHERE z.empresa_id = %s
        """
    ]
    params: list[Any] = [empresa_id]
    if cpf:
        sql.append("AND e.cpf = %s"); params.append(cpf)
    if per_apur:
        sql.append("AND e.per_apur = %s"); params.append(per_apur)
    if tipo_evento:
        sql.append("AND e.tipo_evento = %s"); params.append(tipo_evento)
    if zip_id is not None:
        sql.append("AND e.zip_id = %s"); params.append(zip_id)
    sql.append("ORDER BY e.id DESC LIMIT %s OFFSET %s")
    params.extend([limit, offset])

    with db.cursor() as c:
        c.execute(" ".join(sql), tuple(params))
        rows = [dict(r) for r in c.fetchall()]
    for r in rows:
        for k in ("dt_ini", "dt_fim"):
            if r.get(k) is not None:
                r[k] = r[k].isoformat()
    return {"ok": True, "total": len(rows), "items": rows}


@router.get("/zips/{zip_id}/resumo")
def resumo_zip(zip_id: int):
    """Retorna contagem de eventos por tipo + por perApur — pra montar 'pastas'."""
    with db.cursor() as c:
        c.execute(
            "SELECT id, dt_ini, dt_fim, nome_arquivo_original, total_xmls, "
            "extracao_status FROM empresa_zips_brutos WHERE id=%s",
            (zip_id,),
        )
        z = c.fetchone()
        if not z:
            raise HTTPException(404, "zip não encontrado")
        c.execute(
            """
            SELECT tipo_evento, COUNT(*) AS n
            FROM explorador_eventos
            WHERE zip_id=%s
            GROUP BY tipo_evento
            ORDER BY n DESC
            """,
            (zip_id,),
        )
        por_tipo = [dict(r) for r in c.fetchall()]
        c.execute(
            """
            SELECT per_apur, COUNT(*) AS n
            FROM explorador_eventos
            WHERE zip_id=%s AND per_apur IS NOT NULL
            GROUP BY per_apur
            ORDER BY per_apur
            """,
            (zip_id,),
        )
        por_per = [dict(r) for r in c.fetchall()]
        c.execute(
            "SELECT COUNT(DISTINCT cpf) AS n FROM explorador_eventos WHERE zip_id=%s AND cpf IS NOT NULL",
            (zip_id,),
        )
        cpfs = c.fetchone()["n"]
    z_d = dict(z)
    for k in ("dt_ini", "dt_fim"):
        if z_d.get(k) is not None:
            z_d[k] = z_d[k].isoformat()
    return {
        "ok": True,
        "zip": z_d,
        "cpfs_distintos": cpfs,
        "por_tipo": por_tipo,
        "por_per_apur": por_per,
    }


@router.get("/eventos/{evento_id}/xml")
def baixar_xml(evento_id: int):
    """Devolve o XML do evento.

    Estrategia:
      1) se explorador_eventos.xml_oid existe -> stream do Large Object dedicado
         (caminho rapido, byte-a-byte do XML que estava no ZIP);
      2) fallback: extrai sob demanda do ZIP via xml_entry_name.
    """
    with db.cursor() as c:
        c.execute(
            """
            SELECT e.id, e.xml_entry_name, e.zip_id, e.xml_oid, e.xml_size_bytes,
                   z.conteudo_oid, z.tamanho_bytes, z.nome_arquivo_original
            FROM explorador_eventos e
            JOIN empresa_zips_brutos z ON z.id = e.zip_id
            WHERE e.id = %s
            """,
            (evento_id,),
        )
        row = c.fetchone()
    if not row:
        raise HTTPException(404, "evento nao encontrado")

    filename = row["xml_entry_name"] or f"evento_{evento_id}.xml"
    headers = {"Content-Disposition": f'inline; filename="{filename}"'}

    # Caminho 1: temos LO dedicado
    if row.get("xml_oid") is not None:
        conn = db.connect()

        def _gen():
            try:
                yield from storage.iter_lo_bytes(conn, int(row["xml_oid"]))
            finally:
                try:
                    conn.rollback()
                except Exception:  # noqa: BLE001
                    pass
                try:
                    conn.close()
                except Exception:  # noqa: BLE001
                    pass

        return StreamingResponse(_gen(), media_type="application/xml", headers=headers)

    # Caminho 2: fallback do zip
    conn = db.connect()
    try:
        reader = storage.LargeObjectReader(conn, int(row["conteudo_oid"]), int(row["tamanho_bytes"]))
        try:
            with zipfile.ZipFile(reader, mode="r") as zf:
                with zf.open(row["xml_entry_name"]) as fh:
                    data = fh.read()
        finally:
            reader.close()
            try:
                conn.rollback()
            except Exception:  # noqa: BLE001
                pass
    finally:
        conn.close()
    return StreamingResponse(iter([data]), media_type="application/xml", headers=headers)


@router.post("/zips/{zip_id}/backfill-xml")
def backfill_xml_zip(zip_id: int):
    """Backfill: cria xml_oid para eventos do ZIP que ainda nao tem."""
    from . import backfill_xml
    return backfill_xml.backfill_zip(zip_id)


@router.post("/backfill-xml")
def backfill_xml_global(limite_zips: int | None = None):
    """Backfill em massa: percorre todos os zips com eventos sem xml_oid."""
    from . import backfill_xml
    return backfill_xml.backfill_todos(limite_zips=limite_zips)
