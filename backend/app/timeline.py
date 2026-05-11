"""Router do Chain Walk v2 — timeline mensal de S-1210."""
from __future__ import annotations

from typing import Any

import psycopg2
import psycopg2.extras
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from . import db, storage, tenant

router = APIRouter(prefix="/api/explorador/timeline", tags=["chain-walk"])


def _serialize(rows: list[dict]) -> list[dict]:
    out = []
    for r in rows:
        d = dict(r)
        for k, v in list(d.items()):
            if hasattr(v, "isoformat"):
                d[k] = v.isoformat()
        out.append(d)
    return out


# ---------------------------------------------------------------------------
# 1) Lista meses disponíveis
# ---------------------------------------------------------------------------
@router.get("/meses")
def listar_meses(empresa_id: int):
    """Lista todos os perApur que têm timeline_mes para a empresa."""
    internal_id = tenant.internal_empresa_id(empresa_id)
    with db.cursor(empresa_id=empresa_id) as c:
        c.execute(
            """
            SELECT m.id, m.per_apur, m.head_envio_id, m.criado_em,
                   COUNT(e.id) FILTER (WHERE e.tipo='envio_massa')      AS envios_massa,
                   COUNT(e.id)                                           AS envios_total,
                   COALESCE(SUM(e.total_sucesso), 0)                     AS total_sucesso,
                   COALESCE(SUM(e.total_erro), 0)                        AS total_erro
              FROM timeline_mes m
              LEFT JOIN timeline_envio e ON e.timeline_mes_id = m.id
             WHERE m.empresa_id = %s
             GROUP BY m.id
             ORDER BY m.per_apur DESC
            """,
            (internal_id,),
        )
        rows = c.fetchall()
    return {"ok": True, "items": _serialize(rows)}


# ---------------------------------------------------------------------------
# 2) Régua de um mês específico
# ---------------------------------------------------------------------------
@router.get("")
def regua_mes(empresa_id: int, per_apur: str = Query(..., min_length=7, max_length=7)):
    internal_id = tenant.internal_empresa_id(empresa_id)
    with db.cursor(empresa_id=empresa_id) as c:
        c.execute(
            "SELECT * FROM timeline_mes WHERE empresa_id=%s AND per_apur=%s",
            (internal_id, per_apur),
        )
        m = c.fetchone()
        if not m:
            raise HTTPException(404, "mês sem timeline ainda — suba um zip desse perApur")
        c.execute(
            """
            SELECT id, sequencia, tipo, status,
                   iniciado_em, finalizado_em,
                   total_tentados, total_sucesso, total_erro, resumo
              FROM timeline_envio
             WHERE timeline_mes_id = %s
             ORDER BY sequencia ASC
            """,
            (m["id"],),
        )
        envios = c.fetchall()
    return {
        "ok": True,
        "timeline_mes": _serialize([m])[0],
        "envios": _serialize(envios),
    }


# ---------------------------------------------------------------------------
# 3) Estado de um envio (CPFs e status — para o grid)
# ---------------------------------------------------------------------------
@router.get("/envio/{envio_id}/estado")
def estado_envio(envio_id: int):
    with db.cursor() as c:
        c.execute(
            """
            SELECT e.*, m.per_apur, m.empresa_id
              FROM timeline_envio e
              JOIN timeline_mes m ON m.id = e.timeline_mes_id
             WHERE e.id = %s
            """,
            (envio_id,),
        )
        e = c.fetchone()
        if not e:
            raise HTTPException(404, "envio não encontrado")

        if e["tipo"] == "zip_inicial":
            # estado = todos os S-1210 do mês cuja origem é esse envio
            c.execute(
                """
                SELECT ev.id, ev.cpf, ev.nr_recibo, ev.referenciado_recibo,
                       ev.retificado_por_id,
                       (ev.retificado_por_id IS NULL) AS is_head
                  FROM explorador_eventos ev
                 WHERE ev.tipo_evento = 'S-1210'
                   AND ev.per_apur = %s
                   AND ev.origem_envio_id = %s
                 ORDER BY ev.cpf
                """,
                (e["per_apur"], envio_id),
            )
            evts = c.fetchall()
            items = [
                {
                    "cpf": r["cpf"],
                    "status": "sucesso",
                    "versao_id": r["id"],
                    "nr_recibo": r["nr_recibo"],
                    "is_head": r["is_head"],
                }
                for r in evts
            ]
            totais = {
                "sucesso": len(items),
                "erro_esocial": 0,
                "falha_rede": 0,
                "rejeitado_local": 0,
            }
        else:
            # envio_massa ou individual — lê itens
            c.execute(
                """
                SELECT id, cpf, status, versao_anterior_id, versao_nova_id,
                       nr_recibo_anterior, nr_recibo_novo,
                       erro_codigo, erro_mensagem, criado_em, duracao_ms
                  FROM timeline_envio_item
                 WHERE timeline_envio_id = %s
                 ORDER BY cpf
                """,
                (envio_id,),
            )
            items_raw = c.fetchall()
            items = _serialize(items_raw)
            totais = {"sucesso": 0, "erro_esocial": 0, "falha_rede": 0, "rejeitado_local": 0}
            for it in items:
                if it["status"] in totais:
                    totais[it["status"]] += 1
    return {
        "ok": True,
        "envio": _serialize([e])[0],
        "items": items,
        "totais": totais,
    }


# ---------------------------------------------------------------------------
# 4) Cadeia completa de um (cpf, per_apur, tipo_evento)
# ---------------------------------------------------------------------------
@router.get("/cadeia")
def cadeia_cpf(
    empresa_id: int,
    cpf: str,
    per_apur: str,
    tipo_evento: str = "S-1210",
):
    internal_id = tenant.internal_empresa_id(empresa_id)
    with db.cursor(empresa_id=empresa_id) as c:
        c.execute(
            """
            SELECT ev.id, ev.cpf, ev.per_apur, ev.tipo_evento,
                   ev.nr_recibo, ev.referenciado_recibo AS nr_recibo_anterior,
                   ev.retificado_por_id, ev.origem_envio_id,
                   (ev.retificado_por_id IS NULL) AS is_head,
                   te.sequencia AS envio_sequencia, te.tipo AS envio_tipo,
                   te.iniciado_em
              FROM explorador_eventos ev
              LEFT JOIN timeline_envio te ON te.id = ev.origem_envio_id
             WHERE ev.tipo_evento = %s
               AND ev.cpf = %s
               AND ev.per_apur = %s
             ORDER BY te.sequencia NULLS FIRST, ev.id
            """,
            (tipo_evento, cpf, per_apur),
        )
        versoes = c.fetchall()

        # tentativas (sucesso + erros) — só vão existir após envios futuros
        c.execute(
            """
            SELECT it.id, it.timeline_envio_id, te.sequencia,
                   it.status, it.criado_em,
                   it.nr_recibo_anterior, it.nr_recibo_novo,
                   it.erro_codigo, it.erro_mensagem,
                   (it.xml_enviado_oid IS NOT NULL) AS xml_enviado_disponivel,
                   (it.xml_retorno_oid IS NOT NULL) AS xml_retorno_disponivel
              FROM timeline_envio_item it
              JOIN timeline_envio te ON te.id = it.timeline_envio_id
              JOIN timeline_mes  tm  ON tm.id = te.timeline_mes_id
             WHERE tm.empresa_id = %s
               AND tm.per_apur   = %s
               AND it.cpf        = %s
               AND it.tipo_evento = %s
             ORDER BY te.sequencia, it.id
            """,
            (internal_id, per_apur, cpf, tipo_evento),
        )
        tentativas = c.fetchall()
    return {
        "ok": True,
        "cpf": cpf,
        "per_apur": per_apur,
        "tipo_evento": tipo_evento,
        "versoes": _serialize(versoes),
        "tentativas": _serialize(tentativas),
    }


# ---------------------------------------------------------------------------
# 5) Download de XML enviado / retorno por tentativa (item)
# ---------------------------------------------------------------------------
download_router = APIRouter(prefix="/api/explorador", tags=["chain-walk-download"])


def _stream_lo(oid: int, filename: str):
    conn = db.connect()

    def _gen():
        try:
            yield from storage.iter_lo_bytes(conn, int(oid))
        finally:
            try:
                conn.rollback()
            except Exception:  # noqa: BLE001
                pass
            try:
                conn.close()
            except Exception:  # noqa: BLE001
                pass

    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return StreamingResponse(_gen(), media_type="application/xml", headers=headers)


@download_router.get("/tentativa/{item_id}/xml-enviado")
def baixar_xml_enviado(item_id: int):
    with db.cursor() as c:
        c.execute(
            "SELECT cpf, xml_enviado_oid FROM timeline_envio_item WHERE id=%s",
            (item_id,),
        )
        row = c.fetchone()
    if not row:
        raise HTTPException(404, "tentativa nao encontrada")
    if row.get("xml_enviado_oid") is None:
        raise HTTPException(404, "xml_enviado nao disponivel para esta tentativa")
    return _stream_lo(row["xml_enviado_oid"], f"enviado_{row['cpf']}_item{item_id}.xml")


@download_router.get("/tentativa/{item_id}/xml-retorno")
def baixar_xml_retorno(item_id: int):
    with db.cursor() as c:
        c.execute(
            "SELECT cpf, xml_retorno_oid FROM timeline_envio_item WHERE id=%s",
            (item_id,),
        )
        row = c.fetchone()
    if not row:
        raise HTTPException(404, "tentativa nao encontrada")
    if row.get("xml_retorno_oid") is None:
        raise HTTPException(404, "xml_retorno nao disponivel para esta tentativa")
    return _stream_lo(row["xml_retorno_oid"], f"retorno_{row['cpf']}_item{item_id}.xml")


# ---------------------------------------------------------------------------
# 6) S-1210 Anual Overview — para a S1210AnualView (pagina anual)
# ---------------------------------------------------------------------------
s1210_repo_router = APIRouter(prefix="/api/s1210-repo", tags=["s1210-anual"])


@s1210_repo_router.get("/anual/overview")
def s1210_anual_overview(ano: int, empresa_id: int):
    """Overview anual S-1210 (12 meses x 1 lote MVP).

    Lógica espelhada do V1 (`v_s1210_contadores`):
      - universo (total) = CPFs HEAD do mes (1 row por CPF)
      - status corrente  = ULTIMO envio por CPF (DISTINCT ON cpf ORDER BY criado_em DESC)
      - conta ok/erro/enviando/pendente baseado no status do ultimo envio
      - tentativas anteriores nao inflam contagem

    Mapeamento status timeline_envio_item -> contador:
      sucesso              -> ok
      erro_esocial / erro* -> erro
      enviando/processando -> enviando
      demais / NULL        -> pendente

    empresa_id (V1):
      1 = APPA      -> Supabase
      2 = SOLUCOES  -> Local (internal_empresa_id=1)
    """
    from . import tenant
    cfg = tenant.get_db_config_for_empresa(empresa_id)
    internal_id = tenant.internal_empresa_id(empresa_id)

    meses_out = []
    conn = psycopg2.connect(**cfg)
    try:
        for m in range(1, 13):
            per = f"{ano}-{m:02d}"
            lotes_out: list[dict] = []
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as c:
                # 1) LEGACY V1: agrupado por lote_num (s1210_cpf_scope tem lote_num)
                legacy_rows: list[dict] = []
                try:
                    c.execute(
                        """
                        WITH scope AS (
                            SELECT lote_num, cpf
                              FROM s1210_cpf_scope
                             WHERE empresa_id=%s AND per_apur=%s AND cpf IS NOT NULL
                        ),
                        ult AS (
                            SELECT DISTINCT ON (cpf) cpf, lote_num, status, codigo_resposta
                              FROM s1210_cpf_envios
                             WHERE empresa_id=%s AND per_apur=%s
                             ORDER BY cpf, enviado_em DESC NULLS LAST, id DESC
                        )
                        SELECT
                          COALESCE(s.lote_num, 1)                                       AS lote_num,
                          COUNT(*)                                                      AS total,
                          COUNT(*) FILTER (WHERE u.status IN ('ok','ok_recuperado'))    AS ok,
                          COUNT(*) FILTER (WHERE u.status LIKE 'erro%%')                AS erro,
                          COUNT(*) FILTER (WHERE u.status IN ('enviando','processando')) AS enviando,
                          COUNT(*) FILTER (WHERE u.status = 'na')                       AS na,
                          COUNT(*) FILTER (WHERE u.status IS NULL)                      AS pendente,
                          COUNT(*) FILTER (WHERE u.status LIKE 'erro%%'
                                             AND u.codigo_resposta IN ('401','459'))    AS recibo_retificado,
                          COUNT(*) FILTER (WHERE u.status LIKE 'erro%%'
                                             AND u.codigo_resposta = '202')             AS aceito_com_aviso
                          FROM scope s
                          LEFT JOIN ult u ON u.cpf = s.cpf
                         GROUP BY COALESCE(s.lote_num, 1)
                         ORDER BY lote_num
                        """,
                        (internal_id, per, internal_id, per),
                    )
                    legacy_rows = list(c.fetchall())
                except Exception:
                    conn.rollback()

                # 2) Fallback V2 (timeline) — só quando legacy vazio
                if not legacy_rows:
                    try:
                        c.execute(
                            """
                            WITH scope AS (
                                SELECT DISTINCT ev.cpf
                                  FROM explorador_eventos ev
                                 WHERE ev.tipo_evento='S-1210'
                                   AND ev.per_apur=%s
                                   AND ev.retificado_por_id IS NULL
                                   AND ev.cpf IS NOT NULL
                            ),
                            ult AS (
                                SELECT DISTINCT ON (it.cpf) it.cpf, it.status, it.erro_codigo
                                  FROM timeline_envio_item it
                                  JOIN timeline_envio te ON te.id=it.timeline_envio_id
                                  JOIN timeline_mes tm   ON tm.id=te.timeline_mes_id
                                 WHERE tm.empresa_id=%s
                                   AND tm.per_apur=%s
                                   AND it.tipo_evento='S-1210'
                                 ORDER BY it.cpf, it.criado_em DESC, it.id DESC
                            )
                            SELECT
                              1                                                             AS lote_num,
                              COUNT(*)                                                      AS total,
                              COUNT(*) FILTER (WHERE u.status = 'sucesso')                  AS ok,
                              COUNT(*) FILTER (WHERE u.status LIKE 'erro%%')                AS erro,
                              COUNT(*) FILTER (WHERE u.status IN ('enviando','processando')) AS enviando,
                              0                                                             AS na,
                              COUNT(*) FILTER (WHERE u.status IS NULL
                                                 OR u.status NOT IN ('sucesso','enviando','processando')
                                                 AND u.status NOT LIKE 'erro%%')           AS pendente,
                              COUNT(*) FILTER (WHERE u.status LIKE 'erro%%'
                                                 AND u.erro_codigo IN ('401','459'))        AS recibo_retificado,
                              COUNT(*) FILTER (WHERE u.status LIKE 'erro%%'
                                                 AND u.erro_codigo = '202')                 AS aceito_com_aviso
                              FROM scope s
                              LEFT JOIN ult u ON u.cpf = s.cpf
                            """,
                            (per, internal_id, per),
                        )
                        row = c.fetchone()
                        if row and (row.get("total") or 0) > 0:
                            legacy_rows = [row]
                    except Exception:
                        conn.rollback()

            for row in legacy_rows:
                total = int(row.get("total") or 0)
                ok = int(row.get("ok") or 0)
                erro = int(row.get("erro") or 0)
                enviando = int(row.get("enviando") or 0)
                pendente = int(row.get("pendente") or 0)
                na = int(row.get("na") or 0)
                # Estado considerando N/A como "resolvido" (lote pode ser
                # 100% N/A — ex.: APPA L4 fev/mar 2025: 2 CPFs sem fato gerador,
                # ambos com status='na' → lote esta concluido, nao "pronto").
                resolvidos = ok + na + erro
                if total == 0:
                    estado = "sem_dados"
                elif enviando > 0:
                    estado = "processando"
                elif pendente > 0:
                    estado = "pronto_para_processar"
                elif erro > 0:
                    estado = "concluido_com_erros"
                elif resolvidos >= total:
                    estado = "concluido"
                else:
                    estado = "pronto_para_processar"
                lotes_out.append({
                    "per_apur": per,
                    "lote_num": int(row.get("lote_num") or 1),
                    "total": total,
                    "ok": ok,
                    "erro": erro,
                    "enviando": enviando,
                    "pendente": pendente,
                    "na": na,
                    "recibo_retificado": int(row.get("recibo_retificado") or 0),
                    "aceito_com_aviso": int(row.get("aceito_com_aviso") or 0),
                    "tem_xlsx": False,
                    "estado": estado,
                })

            if not lotes_out:
                lotes_out = [{
                    "per_apur": per, "lote_num": 1,
                    "total": 0, "ok": 0, "erro": 0, "enviando": 0,
                    "pendente": 0, "na": 0,
                    "recibo_retificado": 0, "aceito_com_aviso": 0,
                    "tem_xlsx": False, "estado": "sem_dados",
                }]

            meses_out.append({"per_apur": per, "lotes": lotes_out})

        # ------------------------------------------------------------------
        # Enriquecer cada mes com status de fechamento (S-1299/S-1298).
        # Fontes (em ordem de preferencia):
        #   1) public.s1299_fechamento_status  (marcacao manual/sync)
        #   2) public.explorador_eventos       (ultimo evento valido cd=201)
        # ------------------------------------------------------------------
        fechamento_map: dict[str, dict] = {}
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as c:
            try:
                c.execute(
                    """
                    SELECT per_apur, fechado, nr_recibo, confirmado_em, origem
                      FROM s1299_fechamento_status
                     WHERE empresa_id=%s AND per_apur LIKE %s
                    """,
                    (internal_id, f"{ano}-%"),
                )
                for r in c.fetchall():
                    fechamento_map[r["per_apur"]] = {
                        "fechado": bool(r.get("fechado")),
                        "nr_recibo_fechamento": r.get("nr_recibo"),
                        "fechamento_origem": r.get("origem"),
                        "fechamento_em": (
                            r["confirmado_em"].isoformat()
                            if r.get("confirmado_em") else None
                        ),
                    }
            except Exception:
                conn.rollback()

        # Recibos reais do explorador_eventos (ultimo cd=201 por per_apur)
        recibos_1299: dict[str, dict] = {}
        recibos_1298: dict[str, dict] = {}
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as c:
            try:
                c.execute(
                    """
                    SELECT DISTINCT ON (per_apur)
                           per_apur, nr_recibo, dt_processamento
                      FROM explorador_eventos
                     WHERE tipo_evento='S-1299'
                       AND cd_resposta='201'
                       AND per_apur LIKE %s
                     ORDER BY per_apur, dt_processamento DESC
                    """,
                    (f"{ano}-%",),
                )
                for r in c.fetchall():
                    recibos_1299[r["per_apur"]] = {
                        "nr_recibo": r.get("nr_recibo"),
                        "dt": (
                            r["dt_processamento"].isoformat()
                            if r.get("dt_processamento") else None
                        ),
                    }
            except Exception:
                conn.rollback()
            try:
                c.execute(
                    """
                    SELECT DISTINCT ON (per_apur)
                           per_apur, nr_recibo, dt_processamento
                      FROM explorador_eventos
                     WHERE tipo_evento='S-1298'
                       AND cd_resposta='201'
                       AND per_apur LIKE %s
                     ORDER BY per_apur, dt_processamento DESC
                    """,
                    (f"{ano}-%",),
                )
                for r in c.fetchall():
                    recibos_1298[r["per_apur"]] = {
                        "nr_recibo": r.get("nr_recibo"),
                        "dt": (
                            r["dt_processamento"].isoformat()
                            if r.get("dt_processamento") else None
                        ),
                    }
            except Exception:
                conn.rollback()

        for mes in meses_out:
            per = mes["per_apur"]
            info = fechamento_map.get(per, {})
            r99 = recibos_1299.get(per)
            r98 = recibos_1298.get(per)
            # Estado real: comparar dt do ultimo S-1298 vs S-1299
            estado_atual = info.get("fechado")
            if r99 and r98:
                estado_atual = (r99["dt"] or "") >= (r98["dt"] or "")
            elif r99:
                estado_atual = True
            elif r98:
                estado_atual = False
            mes["fechado"] = bool(estado_atual) if estado_atual is not None else bool(info.get("fechado"))
            mes["nr_recibo_fechamento"] = (
                (r99 or {}).get("nr_recibo") or info.get("nr_recibo_fechamento")
            )
            mes["dt_fechamento"] = (r99 or {}).get("dt") or info.get("fechamento_em")
            mes["nr_recibo_abertura"] = (r98 or {}).get("nr_recibo")
            mes["dt_abertura"] = (r98 or {}).get("dt")
            mes["fechamento_origem"] = info.get("fechamento_origem")
    finally:
        try:
            conn.close()
        except Exception:  # noqa: BLE001
            pass
    return {"ano": ano, "empresa_id": empresa_id, "meses": meses_out}


@s1210_repo_router.post("/anual/sync-fechamento")
def s1210_sync_fechamento(ano: int, empresa_id: int):
    """Escaneia explorador_eventos e atualiza s1299_fechamento_status.

    Para cada per_apur do ano:
      - pega o ULTIMO S-1298 valido (cd_resposta=201) -> dt_abertura
      - pega o ULTIMO S-1299 valido (cd_resposta=201) -> dt_fechamento
      - se ambos: fechado = dt_fechamento >= dt_abertura
      - se só S-1299: fechado=True
      - se só S-1298: fechado=False (mes reaberto)
    Cria a tabela se nao existir e UPSERT.
    """
    from . import tenant
    cfg = tenant.get_db_config_for_empresa(empresa_id)
    internal_id = tenant.internal_empresa_id(empresa_id)

    atualizados = []
    conn = psycopg2.connect(**cfg)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as c:
            c.execute("""
                CREATE TABLE IF NOT EXISTS s1299_fechamento_status (
                  empresa_id    INT          NOT NULL,
                  per_apur      VARCHAR(7)   NOT NULL,
                  fechado       BOOLEAN      NOT NULL DEFAULT FALSE,
                  protocolo     VARCHAR(100),
                  nr_recibo     VARCHAR(100),
                  confirmado_em TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
                  origem        VARCHAR(40)  DEFAULT 'sync',
                  PRIMARY KEY (empresa_id, per_apur)
                )
            """)
            conn.commit()
            c.execute(
                """
                SELECT DISTINCT ON (per_apur)
                       per_apur, nr_recibo, dt_processamento
                  FROM explorador_eventos
                 WHERE tipo_evento='S-1299' AND cd_resposta='201'
                   AND per_apur LIKE %s
                 ORDER BY per_apur, dt_processamento DESC
                """,
                (f"{ano}-%",),
            )
            map_1299 = {r["per_apur"]: r for r in c.fetchall()}
            c.execute(
                """
                SELECT DISTINCT ON (per_apur)
                       per_apur, nr_recibo, dt_processamento
                  FROM explorador_eventos
                 WHERE tipo_evento='S-1298' AND cd_resposta='201'
                   AND per_apur LIKE %s
                 ORDER BY per_apur, dt_processamento DESC
                """,
                (f"{ano}-%",),
            )
            map_1298 = {r["per_apur"]: r for r in c.fetchall()}

            pers = set(map_1299) | set(map_1298)
            for per in sorted(pers):
                r99 = map_1299.get(per)
                r98 = map_1298.get(per)
                if r99 and r98:
                    fechado = r99["dt_processamento"] >= r98["dt_processamento"]
                elif r99:
                    fechado = True
                else:
                    fechado = False
                nr_recibo = (r99 or {}).get("nr_recibo") if fechado else (r98 or {}).get("nr_recibo")
                c.execute(
                    """
                    INSERT INTO s1299_fechamento_status
                          (empresa_id, per_apur, fechado, nr_recibo, origem, confirmado_em)
                    VALUES (%s, %s, %s, %s, 'sync', NOW())
                    ON CONFLICT (empresa_id, per_apur) DO UPDATE
                       SET fechado       = EXCLUDED.fechado,
                           nr_recibo     = COALESCE(EXCLUDED.nr_recibo, s1299_fechamento_status.nr_recibo),
                           origem        = 'sync',
                           confirmado_em = NOW()
                    """,
                    (internal_id, per, fechado, nr_recibo),
                )
                atualizados.append({
                    "per_apur": per,
                    "fechado": fechado,
                    "nr_recibo": nr_recibo,
                })
            conn.commit()
    finally:
        try:
            conn.close()
        except Exception:  # noqa: BLE001
            pass
    return {
        "ok": True,
        "ano": ano,
        "empresa_id": empresa_id,
        "total": len(atualizados),
        "atualizados": atualizados,
    }


@s1210_repo_router.get("/cpfs-do-mes")
def s1210_cpfs_do_mes(per_apur: str, empresa_id: int, lote_num: int = 1):
    """Lista CPFs S-1210 HEAD do mes (1 row por CPF), com status do ultimo envio.

    Resposta compativel com o V1 (`/api/s1210-repo/cpfs-do-mes`):
      { empresa_id, per_apur, total, cpfs: [...] }
    Cada CPF traz status normalizado: ok|erro|enviando|na|pendente.
    """
    from . import tenant
    cfg = tenant.get_db_config_for_empresa(empresa_id)
    internal_id = tenant.internal_empresa_id(empresa_id)

    cpfs_rows: list[dict] = []
    ultimo_por_cpf: dict[str, dict] = {}
    legacy_used = False
    conn = psycopg2.connect(**cfg)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as c:
            # 1) LEGACY: s1210_cpf_scope + s1210_cpf_envios (filtrado por lote)
            try:
                c.execute(
                    """
                    SELECT cpf, nome, matricula, row_number
                      FROM s1210_cpf_scope
                     WHERE empresa_id=%s AND per_apur=%s AND lote_num=%s AND cpf IS NOT NULL
                     ORDER BY row_number NULLS LAST, cpf
                    """,
                    (internal_id, per_apur, lote_num),
                )
                cpfs_rows = list(c.fetchall())
                if cpfs_rows:
                    legacy_used = True
            except Exception:
                conn.rollback()
                cpfs_rows = []

            if legacy_used:
                try:
                    c.execute(
                        """
                        SELECT DISTINCT ON (cpf)
                               cpf, status, nr_recibo_usado, nr_recibo_novo,
                               codigo_resposta AS erro_codigo,
                               descricao_resposta AS erro_mensagem,
                               enviado_em AS criado_em
                          FROM s1210_cpf_envios
                         WHERE empresa_id=%s AND per_apur=%s
                         ORDER BY cpf, enviado_em DESC NULLS LAST, id DESC
                        """,
                        (internal_id, per_apur),
                    )
                    for r in c.fetchall():
                        ultimo_por_cpf[r["cpf"]] = dict(r)
                except Exception:
                    conn.rollback()
            else:
                # 2) Fallback V2: explorador_eventos + timeline_envio_item
                try:
                    c.execute(
                        """
                        SELECT DISTINCT ON (ev.cpf)
                               ev.id, ev.cpf, ev.nr_recibo, ev.referenciado_recibo,
                               ev.dt_processamento
                          FROM explorador_eventos ev
                         WHERE ev.tipo_evento='S-1210'
                           AND ev.per_apur=%s
                           AND ev.retificado_por_id IS NULL
                           AND ev.cpf IS NOT NULL
                         ORDER BY ev.cpf, ev.dt_processamento DESC NULLS LAST, ev.id DESC
                        """,
                        (per_apur,),
                    )
                    cpfs_rows = list(c.fetchall())
                except Exception:
                    conn.rollback()
                    cpfs_rows = []

                try:
                    c.execute(
                        """
                        SELECT DISTINCT ON (it.cpf)
                               it.cpf, it.status, it.nr_recibo_anterior AS nr_recibo_usado, it.nr_recibo_novo,
                               it.erro_codigo, it.erro_mensagem,
                               it.criado_em, it.timeline_envio_id
                          FROM timeline_envio_item it
                          JOIN timeline_envio te ON te.id=it.timeline_envio_id
                          JOIN timeline_mes tm ON tm.id=te.timeline_mes_id
                         WHERE tm.empresa_id=%s AND tm.per_apur=%s
                           AND it.tipo_evento='S-1210'
                         ORDER BY it.cpf, it.criado_em DESC, it.id DESC
                        """,
                        (internal_id, per_apur),
                    )
                    for r in c.fetchall():
                        ultimo_por_cpf[r["cpf"]] = dict(r)
                except Exception:
                    conn.rollback()
    finally:
        try:
            conn.close()
        except Exception:  # noqa: BLE001
            pass

    def _norm_status(s: str | None) -> str:
        if s is None:
            return "pendente"
        if s in ("sucesso", "ok", "ok_recuperado"):
            return "ok"
        if s.startswith("erro"):
            return "erro"
        if s in ("enviando", "processando"):
            return "enviando"
        if s == "na":
            return "na"
        return "pendente"

    cpfs_out = []
    for r in cpfs_rows:
        u = ultimo_por_cpf.get(r["cpf"])
        criado = u["criado_em"].isoformat() if u and hasattr(u.get("criado_em"), "isoformat") else (u and u.get("criado_em")) or None
        cpfs_out.append({
            "cpf": r["cpf"],
            "nome": None,
            "matricula": None,
            "lote_num": lote_num,
            "row_number": None,
            "tem_xml": bool(r.get("nr_recibo")),
            "nr_recibo_xml": r.get("nr_recibo"),
            "status": _norm_status(u["status"] if u else None),
            "nr_recibo_usado": (u or {}).get("nr_recibo_usado"),
            "nr_recibo_novo": (u or {}).get("nr_recibo_novo"),
            "erro_codigo": (u or {}).get("erro_codigo"),
            "descricao_resposta": (u or {}).get("erro_mensagem"),
            "erro_descricao": (u or {}).get("erro_mensagem"),
            "enviado_em": criado,
        })

    return {
        "ok": True,
        "per_apur": per_apur,
        "empresa_id": empresa_id,
        "lote_num": lote_num,
        "total": len(cpfs_out),
        "cpfs": cpfs_out,
    }
