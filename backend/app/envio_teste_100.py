"""Envio teste 100 CPFs S-1210 (HOMOLOGACAO).

Orquestra:
  1. SELECT 100 HEAD de (empresa_id=1, S-1210, perApur=2025-08), com xml_oid;
  2. Cria timeline_envio v1 (sequencia=1, tipo='envio_massa') + 100 items;
  3. Empacota em lotes de <=40 e chama esocial_client.enviar_lote;
  4. Polling consultar_lote (ate 6 tentativas, 5s entre) por protocolo;
  5. Persiste em timeline_envio_item:
        xml_enviado_oid -> reaproveita explorador_eventos.xml_oid
        xml_retorno_oid -> NOVO LO com o <retornoEvento> recortado por Id
        nr_recibo_novo, erro_codigo, erro_mensagem, status, duracao_ms.

Politica conservadora: ambiente='homologacao'.

Uso:
    python -m app.envio_teste_100 \\
        --cert /caminho/para/certificado.pfx \\
        --senha "${ESOCIAL_CERT_SENHA}" \\
        --cnpj 00000000000000 \\
        --ambiente homologacao
"""
from __future__ import annotations

import argparse
import sys
import time
from typing import Any

import psycopg2.extras

from . import db, esocial_client, storage, tenant
from .xml_diff import eventos_iguais
from .xml_extractor import extrair_s1210
from .xml_s1210 import S1210XMLGenerator
from .xml_signer import S1010XMLSigner


CFG_GRUPO = 3          # eSocial Simplificado: periodicos = grupo 3 (S-1200/S-1210/S-1299)
CFG_LOTE_MAX = 40      # eSocial Simplificado
POLL_TENTATIVAS = 12
POLL_INTERVALO_S = 8


def _carregar_eventos_alvo(conn, empresa_id: int, per_apur: str, limite: int,
                           pular_ja_tentados: bool = False) -> list[dict]:
    internal_empresa_id = tenant.internal_empresa_id(empresa_id)
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as c:
        if pular_ja_tentados:
            c.execute(
                """
                SELECT * FROM (
                  SELECT DISTINCT ON (ev.cpf)
                         ev.id, ev.cpf, ev.nr_recibo, ev.id_evento,
                        ev.xml_oid, ev.xml_bytes, ev.xml_size_bytes
                    FROM explorador_eventos ev
                    JOIN empresa_zips_brutos z ON z.id=ev.zip_id
                   WHERE z.empresa_id=%s
                     AND ev.tipo_evento='S-1210'
                     AND ev.per_apur=%s
                     AND ev.retificado_por_id IS NULL
                     AND (ev.xml_oid IS NOT NULL OR ev.xml_bytes IS NOT NULL)
                     AND NOT EXISTS (
                           SELECT 1
                             FROM timeline_envio_item it
                             JOIN timeline_envio te ON te.id=it.timeline_envio_id
                             JOIN timeline_mes  tm ON tm.id=te.timeline_mes_id
                            WHERE tm.empresa_id=%s
                              AND tm.per_apur=%s
                              AND it.tipo_evento='S-1210'
                              AND it.cpf=ev.cpf
                                                                AND NOT (
                                                                    it.status = 'falha_rede'
                                                                OR (
                                                                    it.status LIKE 'erro%%'
                                                                AND it.erro_codigo = '401'
                                                                AND (
                                                                            it.erro_mensagem ILIKE '%%620:%%'
                                                                     OR it.erro_mensagem ILIKE '%%folha de pagamento%%fechada%%'
                                                                )
                                                                AND EXISTS (
                                                                            SELECT 1
                                                                                FROM explorador_eventos r
                                                                             WHERE r.tipo_evento='S-1298'
                                                                                 AND r.cd_resposta='201'
                                                                                 AND r.per_apur=%s
                                                                                 AND r.dt_processamento >= it.criado_em
                                                                )
                                                                )
                                                            )
                         )
                   ORDER BY ev.cpf ASC, ev.dt_processamento DESC NULLS LAST, ev.id DESC
                ) sub
                LIMIT %s
                """,
                                (internal_empresa_id, per_apur, internal_empresa_id, per_apur, per_apur, limite),
            )
        else:
            c.execute(
                """
                SELECT * FROM (
                  SELECT DISTINCT ON (ev.cpf)
                         ev.id, ev.cpf, ev.nr_recibo, ev.id_evento,
                        ev.xml_oid, ev.xml_bytes, ev.xml_size_bytes
                    FROM explorador_eventos ev
                    JOIN empresa_zips_brutos z ON z.id=ev.zip_id
                   WHERE z.empresa_id=%s
                     AND ev.tipo_evento='S-1210'
                     AND ev.per_apur=%s
                     AND ev.retificado_por_id IS NULL
                     AND (ev.xml_oid IS NOT NULL OR ev.xml_bytes IS NOT NULL)
                   ORDER BY ev.cpf ASC, ev.dt_processamento DESC NULLS LAST, ev.id DESC
                ) sub
                LIMIT %s
                """,
                (internal_empresa_id, per_apur, limite),
            )
        return list(c.fetchall())


def _ler_xml_lo(conn_lo, oid: int) -> bytes:
    lo = conn_lo.lobject(int(oid), mode="rb")
    try:
        return lo.read()
    finally:
        lo.close()


def _ler_xml_evento(conn_lo, ev: dict) -> bytes:
    xml_bytes = ev.get("xml_bytes")
    if xml_bytes is not None:
        return bytes(xml_bytes)
    xml_oid = ev.get("xml_oid")
    if xml_oid is None:
        raise ValueError(f"evento {ev.get('id')} sem xml_bytes/xml_oid")
    return _ler_xml_lo(conn_lo, int(xml_oid))


def _criar_timeline_envio(conn, empresa_id: int, per_apur: str, total: int) -> tuple[int, int]:
    """Garante timeline_mes e cria timeline_envio v1. Retorna (envio_id, mes_id)."""
    internal_empresa_id = tenant.internal_empresa_id(empresa_id)
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as c:
        c.execute(
            "SELECT id FROM timeline_mes WHERE empresa_id=%s AND per_apur=%s",
            (internal_empresa_id, per_apur),
        )
        m = c.fetchone()
        if not m:
            raise RuntimeError(f"timeline_mes nao existe p/ empresa_id={empresa_id} per_apur={per_apur}")
        mes_id = int(m["id"])

        c.execute(
            "SELECT COALESCE(MAX(sequencia), 0)+1 AS prox FROM timeline_envio WHERE timeline_mes_id=%s",
            (mes_id,),
        )
        seq = int(c.fetchone()["prox"])

        c.execute(
            """
            INSERT INTO timeline_envio
              (timeline_mes_id, sequencia, tipo, status,
               iniciado_em, total_tentados, total_sucesso, total_erro, resumo)
            VALUES
              (%s, %s, 'envio_massa', 'em_andamento',
               now(), %s, 0, 0, %s)
            RETURNING id
            """,
            (mes_id, seq, total,
             psycopg2.extras.Json({
                 "rotulo": "envio_teste_100",
                 "criterio": "100 primeiros HEAD ordem alfabetica de CPF",
                 "modo": "real_homologacao",
             })),
        )
        envio_id = int(c.fetchone()["id"])
    conn.commit()
    return envio_id, mes_id


def _criar_items(conn, envio_id: int, eventos: list[dict]) -> list[int]:
    """Cria timeline_envio_item por CPF. xml_enviado_oid fica NULL ate o
    XML novo ser gerado/assinado durante o processamento do lote.
    """
    item_ids: list[int] = []
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as c:
        for ev in eventos:
            c.execute(
                """
                INSERT INTO timeline_envio_item
                  (timeline_envio_id, cpf, tipo_evento, status,
                   versao_anterior_id, nr_recibo_anterior,
                   xml_enviado_oid)
                VALUES (%s, %s, 'S-1210', 'pendente', %s, %s, NULL)
                RETURNING id
                """,
                (envio_id, ev["cpf"], ev["id"], ev["nr_recibo"]),
            )
            item_ids.append(int(c.fetchone()["id"]))
    conn.commit()
    return item_ids


def _gravar_xml_enviado(conn_w, xml_bytes: bytes) -> int:
    lo = conn_w.lobject(0, mode="wb")
    oid = lo.oid
    try:
        lo.write(xml_bytes)
    finally:
        lo.close()
    return oid


def _set_xml_enviado_oid(conn, item_id: int, oid: int) -> None:
    with conn.cursor() as c:
        c.execute(
            "UPDATE timeline_envio_item SET xml_enviado_oid=%s WHERE id=%s",
            (oid, item_id),
        )
    conn.commit()


def _gravar_xml_retorno(conn_w, xml_str: str) -> int:
    data = xml_str.encode("utf-8")
    lo = conn_w.lobject(0, mode="wb")
    oid = lo.oid
    try:
        lo.write(data)
    finally:
        lo.close()
    return oid


def _atualizar_item(
    conn,
    item_id: int,
    *,
    status: str,
    erro_codigo: str | None = None,
    erro_mensagem: str | None = None,
    nr_recibo_novo: str | None = None,
    xml_retorno_oid: int | None = None,
    duracao_ms: int | None = None,
) -> None:
    with conn.cursor() as c:
        c.execute(
            """
            UPDATE timeline_envio_item
               SET status=%s,
                   erro_codigo=%s,
                   erro_mensagem=%s,
                   nr_recibo_novo=%s,
                   xml_retorno_oid=%s,
                   duracao_ms=%s
             WHERE id=%s
            """,
            (status, erro_codigo, erro_mensagem, nr_recibo_novo,
             xml_retorno_oid, duracao_ms, item_id),
        )
    conn.commit()


def _atualizar_envio(conn, envio_id: int, *, status: str, sucesso: int, erro: int, resumo_extra: dict) -> None:
    with conn.cursor() as c:
        c.execute(
            """
            UPDATE timeline_envio
               SET status=%s,
                   finalizado_em=now(),
                   total_sucesso=%s,
                   total_erro=%s,
                   resumo = resumo || %s::jsonb
             WHERE id=%s
            """,
            (status, sucesso, erro, psycopg2.extras.Json(resumo_extra), envio_id),
        )
    conn.commit()


def _processar_lote(
    eventos: list[dict],
    items: list[int],
    *,
    cert_path: str,
    cert_password: str,
    cnpj: str,
    ambiente: str,
    conn_db,
    conn_lo,
    conn_w,
) -> dict:
    """Envia 1 lote, faz polling, atualiza items. Retorna sumario.

    Para cada CPF: ler XML antigo do LO -> extrair campos -> REGERAR XML
    novo (Id novo via timestamp + indRetif=2 + nrRecibo do evento ativo)
    -> ASSINAR via signxml -> empacotar.
    """
    with open(cert_path, "rb") as fh:
        pfx_data = fh.read()

    pacote: list[esocial_client.EventoLote] = []
    pares = []  # (item_id, ev, EventoLote)
    falhas_prep: list[tuple[int, str, str]] = []  # (item_id, etapa, msg)

    for seq, (item_id, ev) in enumerate(zip(items, eventos), start=1):
        try:
            xml_antigo = _ler_xml_evento(conn_lo, ev)
            campos = extrair_s1210(xml_antigo)
        except Exception as e:  # noqa: BLE001
            falhas_prep.append((item_id, "extrair_xml", f"{type(e).__name__}: {e}"))
            continue

        nr_recibo_ativo = ev.get("nr_recibo") or campos.get("nr_recibo_atual")
        if not nr_recibo_ativo:
            falhas_prep.append((item_id, "sem_nr_recibo",
                               f"CPF {ev['cpf']} sem nrRecibo p/ retificar"))
            continue

        # IMPORTANTE: ideEmpregador do EVENTO precisa bater com o original que
        # gerou o nrRecibo (caso contrario eSocial nao acha o evento -> erro 459).
        # O extractor ja devolve nrInsc=raiz (8) do XML antigo. Mantemos.
        # Resultado: @Id e ideEmpregador do evento ficam com raiz+zeros, igual ao original.
        # (O envelope do LOTE pode usar CNPJ completo, isso ja foi aceito antes.)

        try:
            xml_novo = S1210XMLGenerator.gerar(
                empregador=campos["empregador"],
                beneficiario=campos["beneficiario"],
                info_pgtos=campos["info_pgtos"],
                per_apur=campos["per_apur"],
                ind_retif="2",
                nr_recibo=nr_recibo_ativo,
                info_ir_complem=campos["info_ir_complem"],
                plan_saude=campos["plan_saude"],
                seq=seq,
                tp_amb="1" if ambiente == "producao" else "2",
            )
        except Exception as e:  # noqa: BLE001
            falhas_prep.append((item_id, "gerar_xml", f"{type(e).__name__}: {e}"))
            continue

        # GUARD-RAIL erro 543: se o corpo do evento que vamos enviar e identico
        # ao que ja esta no eSocial (xml_antigo), o eSocial rejeita com regra 543
        # ("Ja existe evento com mesmo identificador"). Pular sem enviar.
        try:
            if eventos_iguais(xml_antigo, xml_novo):
                falhas_prep.append((item_id, "sem_mudanca",
                                    "XML novo identico ao anterior (skip 543)"))
                continue
        except Exception:  # noqa: BLE001
            # se a comparacao falhar, segue o envio normal (fallback seguro)
            pass

        try:
            xml_assinado = S1010XMLSigner.assinar(xml_novo, pfx_data, cert_password)
        except Exception as e:  # noqa: BLE001
            falhas_prep.append((item_id, "assinar_xml", f"{type(e).__name__}: {e}"))
            continue

        id_evt = esocial_client._extrair_id(xml_assinado)
        if not id_evt:
            falhas_prep.append((item_id, "extrair_id", "Id nao encontrado apos assinar"))
            continue

        # grava XML novo no banco e linka no item
        try:
            oid_novo = _gravar_xml_enviado(conn_w, xml_assinado)
            conn_w.commit()
            _set_xml_enviado_oid(conn_db, item_id, oid_novo)
        except Exception as e:  # noqa: BLE001
            falhas_prep.append((item_id, "gravar_xml_enviado", f"{type(e).__name__}: {e}"))
            continue

        eo = esocial_client.EventoLote(xml_bytes=xml_assinado, id_evento=id_evt)
        pacote.append(eo)
        pares.append((item_id, ev, eo))

    # marca falhas de preparo
    sem_mudanca_count = 0
    for item_id, etapa, msg in falhas_prep:
        if etapa == "sem_mudanca":
            _atualizar_item(
                conn_db, item_id,
                status="sem_mudanca",
                erro_codigo="SEM_MUDANCA",
                erro_mensagem=msg[:1000],
                duracao_ms=0,
            )
            sem_mudanca_count += 1
        else:
            _atualizar_item(
                conn_db, item_id,
                status="erro_preparo",
                erro_codigo=etapa[:32],
                erro_mensagem=msg[:1000],
                duracao_ms=0,
            )

    if not pacote:
        return {"lote_ok": False, "sucesso": 0, "erro": len(falhas_prep) - sem_mudanca_count,
                "sem_mudanca": sem_mudanca_count}

    t0 = time.time()
    print(f"  -> POST EnviarLoteEventos ({len(pacote)} eventos) ambiente={ambiente}")
    res = esocial_client.enviar_lote(
        pacote,
        cert_path=cert_path,
        cert_password=cert_password,
        cnpj_empregador=cnpj,
        ambiente=ambiente,
        grupo=CFG_GRUPO,
    )
    durac_envio_ms = int((time.time() - t0) * 1000)
    print(f"     resp http={res.get('http_status')} cd={res.get('codigo_resposta')} "
          f"desc={res.get('descricao')} proto={res.get('protocolo')}")

    if not res.get("sucesso"):
        # lote rejeitado: marcar todos os items
        codigo = res.get("codigo_resposta") or "ERRO_LOTE"
        msg = res.get("descricao") or res.get("erro") or "lote rejeitado pelo eSocial"
        # se houver ocorrencias gerais, anexar
        ocs = res.get("ocorrencias") or []
        if ocs:
            msg += " | " + "; ".join(f"{o['codigo']}: {o['descricao']}" for o in ocs[:3])
        # gravar xml de retorno do lote como xml_retorno_oid (mesmo p/ todos)
        xml_ret_oid = None
        if res.get("response_xml"):
            try:
                xml_ret_oid = _gravar_xml_retorno(conn_w, res["response_xml"])
                conn_w.commit()
            except Exception:  # noqa: BLE001
                xml_ret_oid = None
        for item_id, ev, _eo in pares:
            _atualizar_item(
                conn_db, item_id,
                status="erro_esocial" if res.get("http_status") == 200 else "falha_rede",
                erro_codigo=str(codigo)[:32],
                erro_mensagem=str(msg)[:1000],
                xml_retorno_oid=xml_ret_oid,
                duracao_ms=durac_envio_ms // max(len(pares), 1),
            )
        return {"lote_ok": False, "sucesso": 0,
                "erro": len(pares) + len(falhas_prep) - sem_mudanca_count,
                "sem_mudanca": sem_mudanca_count}

    protocolo = res["protocolo"]
    print(f"     polling protocolo={protocolo}")

    # polling
    consulta = None
    for tentativa in range(POLL_TENTATIVAS):
        time.sleep(POLL_INTERVALO_S)
        consulta = esocial_client.consultar_lote(
            protocolo,
            cert_path=cert_path,
            cert_password=cert_password,
            ambiente=ambiente,
        )
        cd = consulta.get("codigo_lote")
        print(f"       [{tentativa+1}/{POLL_TENTATIVAS}] cd_lote={cd} "
              f"eventos_retorno={len(consulta.get('eventos') or [])}")
        if cd == "201":
            break
        if cd and cd != "101":  # 101 = ainda em processamento
            break

    eventos_ret = (consulta or {}).get("eventos") or []
    by_id: dict[str, dict] = {}
    for er in eventos_ret:
        if er.get("id_evento"):
            by_id[er["id_evento"]] = er

    sucesso_count = 0
    erro_count = 0
    for item_id, ev, eo in pares:
        match = by_id.get(eo.id_evento)
        durac = (durac_envio_ms + POLL_INTERVALO_S * 1000) // max(len(pares), 1)
        if not match:
            _atualizar_item(
                conn_db, item_id,
                status="pendente",
                erro_codigo="SEM_RETORNO",
                erro_mensagem="protocolo nao trouxe retornoEvento p/ este Id",
                duracao_ms=durac,
            )
            erro_count += 1
            continue

        # grava xml retorno por evento
        xml_ret_oid = None
        if match.get("xml_retorno"):
            try:
                xml_ret_oid = _gravar_xml_retorno(conn_w, match["xml_retorno"])
                conn_w.commit()
            except Exception:  # noqa: BLE001
                xml_ret_oid = None

        if match.get("codigo") == "201":
            _atualizar_item(
                conn_db, item_id,
                status="sucesso",
                nr_recibo_novo=match.get("nr_recibo"),
                xml_retorno_oid=xml_ret_oid,
                duracao_ms=durac,
            )
            sucesso_count += 1
        else:
            ocs = match.get("ocorrencias") or []
            msg_partes = [f"{match.get('codigo')}: {match.get('descricao')}"]
            for oc in ocs[:5]:
                msg_partes.append(f"  - {oc['codigo']}: {oc['descricao']}")
            _atualizar_item(
                conn_db, item_id,
                status="erro_esocial",
                erro_codigo=str(match.get("codigo") or "")[:32],
                erro_mensagem=" | ".join(msg_partes)[:1000],
                xml_retorno_oid=xml_ret_oid,
                duracao_ms=durac,
            )
            erro_count += 1

    return {"lote_ok": True, "sucesso": sucesso_count,
            "erro": erro_count + len(falhas_prep) - sem_mudanca_count,
            "sem_mudanca": sem_mudanca_count, "protocolo": protocolo}


def rodar(
    *,
    empresa_id: int,
    per_apur: str,
    limite: int,
    cert_path: str,
    cert_password: str,
    cnpj: str,
    ambiente: str,
    pular_ja_tentados: bool = False,
) -> dict:
    conn_db = db.connect(empresa_id=empresa_id)
    conn_lo = db.connect(empresa_id=empresa_id)
    conn_w = db.connect(empresa_id=empresa_id)
    try:
        eventos = _carregar_eventos_alvo(conn_db, empresa_id, per_apur, limite, pular_ja_tentados=pular_ja_tentados)
        if not eventos:
            return {"ok": False, "erro": "nenhum evento HEAD encontrado"}
        print(f"=> selecionados {len(eventos)} eventos S-1210 HEAD per_apur={per_apur}")

        envio_id, mes_id = _criar_timeline_envio(conn_db, empresa_id, per_apur, len(eventos))
        print(f"=> timeline_envio criado id={envio_id} (timeline_mes={mes_id})")

        item_ids = _criar_items(conn_db, envio_id, eventos)
        print(f"=> {len(item_ids)} timeline_envio_item criados (status=pendente)")

        # particionar
        sucesso_total = 0
        erro_total = 0
        protocolos: list[str] = []

        for i in range(0, len(eventos), CFG_LOTE_MAX):
            chunk_evt = eventos[i:i + CFG_LOTE_MAX]
            chunk_ids = item_ids[i:i + CFG_LOTE_MAX]
            print(f"\n>> Lote {i // CFG_LOTE_MAX + 1} ({len(chunk_evt)} eventos)")
            r = _processar_lote(
                chunk_evt, chunk_ids,
                cert_path=cert_path, cert_password=cert_password, cnpj=cnpj,
                ambiente=ambiente,
                conn_db=conn_db, conn_lo=conn_lo, conn_w=conn_w,
            )
            sucesso_total += r["sucesso"]
            erro_total += r["erro"]
            if r.get("protocolo"):
                protocolos.append(r["protocolo"])

        # histograma de erros
        histograma: dict[str, int] = {}
        with conn_db.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as c:
            c.execute(
                "SELECT erro_codigo, COUNT(*) AS n FROM timeline_envio_item "
                "WHERE timeline_envio_id=%s AND erro_codigo IS NOT NULL "
                "GROUP BY erro_codigo ORDER BY n DESC",
                (envio_id,),
            )
            for r in c.fetchall():
                histograma[str(r["erro_codigo"])] = int(r["n"])

        _atualizar_envio(
            conn_db, envio_id,
            status="concluido",
            sucesso=sucesso_total, erro=erro_total,
            resumo_extra={"protocolos": protocolos, "histograma_erros": histograma},
        )

        print("\n=== RESUMO ===")
        print(f"envio_id        : {envio_id}")
        print(f"protocolos      : {protocolos}")
        print(f"sucesso         : {sucesso_total}")
        print(f"erro            : {erro_total}")
        print(f"histograma erros: {histograma}")
        return {
            "ok": True, "envio_id": envio_id, "sucesso": sucesso_total,
            "erro": erro_total, "protocolos": protocolos, "histograma": histograma,
        }
    finally:
        for c in (conn_db, conn_lo, conn_w):
            try:
                c.close()
            except Exception:  # noqa: BLE001
                pass


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--empresa-id", type=int, default=1)
    ap.add_argument("--per-apur", default="2025-08")
    ap.add_argument("--limite", type=int, default=100)
    ap.add_argument("--cert", required=True)
    ap.add_argument("--senha", required=True)
    ap.add_argument("--cnpj", required=True, help="CNPJ raiz/14 do empregador (so digitos)")
    ap.add_argument("--ambiente", default="homologacao", choices=["homologacao", "producao"])
    ap.add_argument("--pular-ja-tentados", action="store_true",
                    help="Exclui CPFs que ja tem item em timeline_envio_item p/ esse per_apur")
    args = ap.parse_args(argv)
    r = rodar(
        empresa_id=args.empresa_id,
        per_apur=args.per_apur,
        limite=args.limite,
        cert_path=args.cert,
        cert_password=args.senha,
        cnpj=args.cnpj,
        ambiente=args.ambiente,
        pular_ja_tentados=args.pular_ja_tentados,
    )
    return 0 if r.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
