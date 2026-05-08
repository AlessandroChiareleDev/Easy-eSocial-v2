"""Reprocessa um timeline_envio rodando consultar_lote nos protocolos
salvos em resumo->protocolos e atualizando os items pelo @Id casado.

Uso:
  python -m app.reprocessar_envio --envio-id 12 \\
      --cert ... --senha ... --ambiente producao
"""
from __future__ import annotations
import argparse
import json
import sys
import time

import psycopg2.extras

from . import db, esocial_client, storage


def _gravar_xml_retorno(conn_w, xml_str: str) -> int:
    data = xml_str.encode("utf-8")
    lo = conn_w.lobject(0, mode="wb")
    oid = lo.oid
    try:
        lo.write(data)
    finally:
        lo.close()
    return oid


def _ler_xml_lo(conn_lo, oid: int) -> bytes:
    lo = conn_lo.lobject(int(oid), mode="rb")
    try:
        return lo.read()
    finally:
        lo.close()


def _id_evento_do_xml(xml_bytes: bytes) -> str | None:
    return esocial_client._extrair_id(xml_bytes)


def reprocessar(envio_id: int, *, cert_path: str, cert_password: str,
                ambiente: str) -> dict:
    conn_db = db.connect()
    conn_lo = db.connect()
    conn_w = db.connect()
    try:
        with conn_db.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as c:
            c.execute("SELECT * FROM timeline_envio WHERE id=%s", (envio_id,))
            envio = c.fetchone()
            if not envio:
                raise SystemExit(f"envio {envio_id} nao existe")
            protocolos = (envio.get("resumo") or {}).get("protocolos") or []
            print(f"envio {envio_id}: {len(protocolos)} protocolos -> {protocolos}")

            c.execute(
                """SELECT id, cpf, xml_enviado_oid
                     FROM timeline_envio_item
                    WHERE timeline_envio_id=%s
                    ORDER BY id""",
                (envio_id,),
            )
            items = list(c.fetchall())
            print(f"envio {envio_id}: {len(items)} items")

        # mapa id_evento -> item_id (lendo xml_enviado_oid)
        id_to_item: dict[str, dict] = {}
        for it in items:
            if not it.get("xml_enviado_oid"):
                continue
            try:
                xml = _ler_xml_lo(conn_lo, int(it["xml_enviado_oid"]))
                ide = _id_evento_do_xml(xml)
                if ide:
                    id_to_item[ide] = it
            except Exception as e:  # noqa: BLE001
                print(f"  WARN item {it['id']} cpf={it['cpf']}: {e}")
        print(f"envio {envio_id}: mapa id_evento->item com {len(id_to_item)} entradas")

        sucesso_total = 0
        erro_total = 0

        for proto in protocolos:
            print(f"\n>> consultar_lote proto={proto}")
            res = esocial_client.consultar_lote(
                proto, cert_path=cert_path, cert_password=cert_password,
                ambiente=ambiente,
            )
            print(f"   cd_lote={res.get('codigo_lote')} eventos={len(res.get('eventos') or [])}")
            for er in res.get("eventos") or []:
                ide = er.get("id_evento")
                if not ide or ide not in id_to_item:
                    continue
                it = id_to_item[ide]
                xml_ret_oid = None
                if er.get("xml_retorno"):
                    try:
                        xml_ret_oid = _gravar_xml_retorno(conn_w, er["xml_retorno"])
                        conn_w.commit()
                    except Exception:  # noqa: BLE001
                        xml_ret_oid = None

                if er.get("codigo") == "201":
                    with conn_db.cursor() as c2:
                        c2.execute(
                            """UPDATE timeline_envio_item
                                 SET status='sucesso',
                                     nr_recibo_novo=%s,
                                     xml_retorno_oid=COALESCE(%s, xml_retorno_oid),
                                     erro_codigo=NULL,
                                     erro_mensagem=NULL
                               WHERE id=%s""",
                            (er.get("nr_recibo"), xml_ret_oid, it["id"]),
                        )
                    conn_db.commit()
                    sucesso_total += 1
                else:
                    ocs = er.get("ocorrencias") or []
                    msg_partes = [f"{er.get('codigo')}: {er.get('descricao')}"]
                    for oc in ocs[:5]:
                        msg_partes.append(f"  - {oc['codigo']}: {oc['descricao']}")
                    with conn_db.cursor() as c2:
                        c2.execute(
                            """UPDATE timeline_envio_item
                                 SET status='erro_esocial',
                                     erro_codigo=%s,
                                     erro_mensagem=%s,
                                     xml_retorno_oid=COALESCE(%s, xml_retorno_oid)
                               WHERE id=%s""",
                            (str(er.get("codigo") or "")[:32],
                             " | ".join(msg_partes)[:1000],
                             xml_ret_oid, it["id"]),
                        )
                    conn_db.commit()
                    erro_total += 1

        # atualiza totalizadores do envio
        with conn_db.cursor() as c:
            c.execute(
                """UPDATE timeline_envio
                     SET total_sucesso=%s, total_erro=%s,
                         status='concluido',
                         resumo = resumo || jsonb_build_object('reprocessado_em', now()::text)
                   WHERE id=%s""",
                (sucesso_total, erro_total, envio_id),
            )
        conn_db.commit()

        # histograma
        with conn_db.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as c:
            c.execute(
                """SELECT status, COUNT(*) n FROM timeline_envio_item
                    WHERE timeline_envio_id=%s GROUP BY status""",
                (envio_id,),
            )
            dist = {r["status"]: r["n"] for r in c.fetchall()}
        print(f"\n=== envio {envio_id} reprocessado ===")
        print(f"sucesso={sucesso_total} erro={erro_total}")
        print(f"distribuicao status no banco: {dist}")
        return {"envio_id": envio_id, "sucesso": sucesso_total,
                "erro": erro_total, "distribuicao": dist}
    finally:
        for c in (conn_db, conn_lo, conn_w):
            try:
                c.close()
            except Exception:  # noqa: BLE001
                pass


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--envio-id", type=int, required=True)
    ap.add_argument("--cert", required=True)
    ap.add_argument("--senha", required=True)
    ap.add_argument("--ambiente", default="producao",
                    choices=["homologacao", "producao"])
    args = ap.parse_args(argv)
    reprocessar(args.envio_id, cert_path=args.cert,
                cert_password=args.senha, ambiente=args.ambiente)
    return 0


if __name__ == "__main__":
    sys.exit(main())
