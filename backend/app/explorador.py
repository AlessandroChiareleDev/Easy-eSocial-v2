"""Router do Explorador — upload, extração, listagem."""
from __future__ import annotations

import json
import re
import zipfile
from datetime import date, datetime
from typing import Any

import psycopg2
import psycopg2.extras
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from . import config, db, storage
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
    with db.cursor(empresa_id=empresa_id) as c:
        c.execute("SELECT id, nome, tipo_estado FROM master_empresas WHERE id=%s", (empresa_id,))
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
        with db.cursor(commit=True, empresa_id=empresa_id) as c:
            c.execute(
                """
                INSERT INTO explorador_atividade
                  (empresa_id, acao, zip_id, nome_arquivo, sha256,
                   tamanho_bytes, total_xmls, detalhe)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    empresa_id, acao, zip_id, nome_arquivo, sha256,
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

        # 2) Dedup por (empresa_id, sha256)
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT id FROM empresa_zips_brutos WHERE empresa_id=%s AND sha256=%s",
                (empresa_id, sha256_hex),
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
                (empresa_id, d_ini, d_fim, seq, nome_original, sha256_hex, total_bytes, oid),
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
            (empresa_id, limit, offset),
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


@router.delete("/zips/{zip_id}")
def deletar_zip(zip_id: int):
    """Apaga zip + eventos indexados + Large Object do conteúdo."""
    conn = db.connect()
    info: dict = {}
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            """SELECT empresa_id, conteudo_oid, nome_arquivo_original,
                      sha256, tamanho_bytes, total_xmls
               FROM empresa_zips_brutos WHERE id=%s""",
            (zip_id,),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "zip não encontrado")
        info = dict(row)
        oid = int(row["conteudo_oid"])
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
        # apaga LO do zip
        storage.unlink_lo(conn, oid)
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
        info["empresa_id"], "exclusao",
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
            (empresa_id, limit),
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

def _extrair_zip_sync(zip_id: int) -> dict:
    """Lê o zip do Large Object e popula explorador_eventos.

    Usa DUAS conexões:
      - conn_lo: mantida em transação aberta para o Large Object permanecer válido.
      - conn_db: para INSERTs/UPDATEs com commits/rollbacks livres.
    """
    conn_db = db.connect()
    conn_lo = db.connect()
    conn_w = db.connect()  # escreve LOs por evento (sem invalidar reader)
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
                                ON CONFLICT (id_evento) WHERE id_evento IS NOT NULL DO NOTHING
                                RETURNING id
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
                                    json.dumps({"nome_tecnico": evt.nome_tecnico}),
                                    zip_id,
                                    name,
                                    evt.referenciado_recibo,
                                    x_oid,
                                    x_size,
                                    x_sha,
                                ),
                            )
                            inserted = cur2.fetchone()
                        if inserted is None:
                            duplicados += 1
                            # houve conflito - o LO criado virou orfao,
                            # remove para nao deixar lixo
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
def extrair_zip(zip_id: int):
    """Extração SÍNCRONA (MVP). Pode demorar para zips grandes."""
    res = _extrair_zip_sync(zip_id)
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
                },
            )
    except Exception:  # noqa: BLE001
        pass
    return res


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
