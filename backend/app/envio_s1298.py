"""Envia S-1298 (Reabertura de Eventos Periodicos) ao eSocial.

Uso:
  python -m app.envio_s1298 --cnpj 09445502000109 --per-apur 2025-08 \
      --cert <path.pfx> --senha <senha> --ambiente producao
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time

from .xml_s1298 import S1298XMLGenerator
from .xml_signer import S1010XMLSigner
from . import db, esocial_client, tenant
from .certificate_manager import CertificateManager


def _load_certificado(empresa_id: int, cert_id: int | None):
    conn = db.connect(empresa_id=empresa_id)
    try:
        with conn.cursor() as cur:
            if cert_id is not None:
                cur.execute(
                    """
                    SELECT id, cnpj, arquivo_path, senha_encrypted
                      FROM certificados_a1
                     WHERE id=%s
                    """,
                    (cert_id,),
                )
            else:
                cur.execute(
                    """
                    SELECT id, cnpj, arquivo_path, senha_encrypted
                      FROM certificados_a1
                     WHERE ativo IS TRUE
                     ORDER BY id DESC
                     LIMIT 1
                    """
                )
            row = cur.fetchone()
    finally:
        conn.close()
    if not row:
        alvo = f"id={cert_id}" if cert_id is not None else "ativo"
        raise RuntimeError(f"certificado {alvo} nao encontrado")
    senha = CertificateManager.decrypt_password(row[3])
    return {
        "id": row[0],
        "cnpj": row[1],
        "cert_path": row[2],
        "senha": senha,
    }


def _salvar_reabertura(
    *,
    empresa_id: int,
    per_apur: str,
    id_evento: str | None,
    xml_assinado: bytes,
    protocolo: str | None,
    envio: dict,
    consulta: dict | None,
) -> dict:
    evento = None
    for ev_ret in (consulta or {}).get("eventos") or []:
        if not id_evento or ev_ret.get("id_evento") == id_evento:
            evento = ev_ret
            break
    if evento is None and (consulta or {}).get("eventos"):
        evento = (consulta or {}).get("eventos")[0]

    codigo = (evento or {}).get("codigo") or envio.get("codigo_resposta")
    descricao = (evento or {}).get("descricao") or envio.get("descricao")
    recibo = (evento or {}).get("nr_recibo")
    ocorrencias = (evento or {}).get("ocorrencias") or envio.get("ocorrencias") or []
    xml_retorno = (evento or {}).get("xml_retorno")

    dados = {
        "origem": "envio_s1298",
        "protocolo": protocolo,
        "codigo": codigo,
        "descricao": descricao,
        "ocorrencias": ocorrencias,
        "consulta": consulta,
        "envio": {
            "codigo_resposta": envio.get("codigo_resposta"),
            "descricao": envio.get("descricao"),
            "dh_recepcao": envio.get("dh_recepcao"),
            "http_status": envio.get("http_status"),
        },
        "xml_retorno": xml_retorno,
    }

    internal_empresa_id = tenant.internal_empresa_id(empresa_id)
    sha = hashlib.sha256(xml_assinado).hexdigest()
    conn = db.connect(empresa_id=empresa_id)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO explorador_eventos
                  (tipo_evento, cpf, per_apur, nr_recibo, id_evento,
                   dt_processamento, cd_resposta, arquivo_origem, dados_json,
                   xml_entry_name, xml_bytes, xml_size_bytes, xml_sha256)
                VALUES
                  ('S-1298', NULL, %s, %s, %s, NOW(), %s, %s, %s::jsonb,
                   %s, %s, %s, %s)
                ON CONFLICT (id_evento) WHERE id_evento IS NOT NULL DO UPDATE
                   SET nr_recibo = COALESCE(EXCLUDED.nr_recibo, explorador_eventos.nr_recibo),
                       dt_processamento = EXCLUDED.dt_processamento,
                       cd_resposta = EXCLUDED.cd_resposta,
                       arquivo_origem = EXCLUDED.arquivo_origem,
                       dados_json = EXCLUDED.dados_json,
                       xml_entry_name = EXCLUDED.xml_entry_name,
                       xml_bytes = EXCLUDED.xml_bytes,
                       xml_size_bytes = EXCLUDED.xml_size_bytes,
                       xml_sha256 = EXCLUDED.xml_sha256
                RETURNING id
                """,
                (
                    per_apur,
                    recibo,
                    id_evento,
                    codigo,
                    f"s1298_reabertura_{per_apur}.xml",
                    json.dumps(dados, ensure_ascii=False),
                    f"s1298_reabertura_{per_apur}.xml",
                    xml_assinado,
                    len(xml_assinado),
                    sha,
                ),
            )
            evento_db_id = cur.fetchone()[0]
            cur.execute(
                """
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
                """
            )
            if codigo == "201":
                cur.execute(
                    """
                    INSERT INTO s1299_fechamento_status
                          (empresa_id, per_apur, fechado, protocolo, nr_recibo, origem, confirmado_em)
                    VALUES (%s, %s, FALSE, %s, %s, 's1298_envio', NOW())
                    ON CONFLICT (empresa_id, per_apur) DO UPDATE
                       SET fechado = FALSE,
                           protocolo = EXCLUDED.protocolo,
                           nr_recibo = COALESCE(EXCLUDED.nr_recibo, s1299_fechamento_status.nr_recibo),
                           origem = 's1298_envio',
                           confirmado_em = NOW()
                    """,
                    (internal_empresa_id, per_apur, protocolo, recibo),
                )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return {
        "evento_db_id": evento_db_id,
        "codigo": codigo,
        "descricao": descricao,
        "nr_recibo": recibo,
        "ocorrencias": ocorrencias,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cnpj", help="CNPJ completo (14 digitos)")
    ap.add_argument("--per-apur", required=True, help="AAAA-MM")
    ap.add_argument("--ind-apuracao", default="1", choices=["1", "2"],
                    help="1=Mensal, 2=13o")
    ap.add_argument("--cert")
    ap.add_argument("--senha")
    ap.add_argument("--cert-id", type=int, default=None)
    ap.add_argument("--empresa-id", type=int, default=tenant.APPA_ID)
    ap.add_argument("--registrar-evento", action="store_true")
    ap.add_argument("--ambiente", choices=["homologacao", "producao"], default="homologacao")
    ap.add_argument("--grupo", type=int, default=3,
                    help="Grupo do envioLoteEventos (Simplificado periodicos=3)")
    args = ap.parse_args()

    if args.cert_id is not None:
        cert_info = _load_certificado(args.empresa_id, args.cert_id)
        args.cert = cert_info["cert_path"]
        args.senha = cert_info["senha"]
        if not args.cnpj:
            args.cnpj = cert_info["cnpj"]
    if not args.cnpj or not args.cert or not args.senha:
        ap.error("informe --cnpj/--cert/--senha ou use --cert-id")

    cnpj = args.cnpj
    cnpj_raiz = cnpj[:8]
    tp_amb = "1" if args.ambiente == "producao" else "2"

    with open(args.cert, "rb") as f:
        pfx = f.read()

    print(f"=> S-1298 reabertura per_apur={args.per_apur} cnpj_raiz={cnpj_raiz} ambiente={args.ambiente}")

    xml_bytes = S1298XMLGenerator.gerar(
        empregador={"tpInsc": 1, "nrInsc": cnpj_raiz},
        per_apur=args.per_apur,
        ind_apuracao=args.ind_apuracao,
        seq=1,
        tp_amb=tp_amb,
    )
    xml_assinado = S1010XMLSigner.assinar(xml_bytes, pfx, args.senha)
    id_evt = esocial_client._extrair_id(xml_assinado)
    print(f"   Id={id_evt}")

    ev = esocial_client.EventoLote(xml_bytes=xml_assinado, id_evento=id_evt)
    res = esocial_client.enviar_lote(
        [ev],
        cert_path=args.cert,
        cert_password=args.senha,
        cnpj_empregador=cnpj,
        ambiente=args.ambiente,
        grupo=args.grupo,
    )
    print(f"-> POST cd={res.get('codigo_resposta')} desc={res.get('descricao')} "
          f"proto={res.get('protocolo')}")
    if res.get("ocorrencias"):
        for o in res["ocorrencias"]:
            print(f"   OC {o['codigo']}: {o['descricao'][:200]}")
    if not res.get("sucesso"):
        print("LOTE REJEITADO")
        sys.exit(2)

    protocolo = res.get("protocolo")
    print(f"\n=> polling consultar_lote {protocolo}")
    consulta = None
    for tent in range(1, 13):
        time.sleep(8)
        consulta = esocial_client.consultar_lote(
            protocolo,
            cert_path=args.cert,
            cert_password=args.senha,
            ambiente=args.ambiente,
        )
        cd = consulta.get("codigo_lote")
        evs = consulta.get("eventos") or []
        print(f"   [{tent}/12] cd_lote={cd} eventos={len(evs)}")
        if cd and cd != "104":  # 104 = em processamento
            break

    print()
    for ev_ret in (consulta or {}).get("eventos") or []:
        cd = ev_ret.get("codigo")
        ds = ev_ret.get("descricao")
        recibo = ev_ret.get("nr_recibo")
        print(f"   evento cd={cd} desc={ds} recibo={recibo}")
        for o in ev_ret.get("ocorrencias") or []:
            print(f"      OC {o['codigo']}: {o['descricao'][:200]}")

    if args.registrar_evento:
        salvo = _salvar_reabertura(
            empresa_id=args.empresa_id,
            per_apur=args.per_apur,
            id_evento=id_evt,
            xml_assinado=xml_assinado,
            protocolo=protocolo,
            envio=res,
            consulta=consulta,
        )
        print(
            f"\n=> salvo explorador_eventos id={salvo['evento_db_id']} "
            f"cd={salvo['codigo']} recibo={salvo['nr_recibo']}"
        )
        if salvo.get("ocorrencias"):
            for o in salvo["ocorrencias"]:
                print(f"   SALVO OC {o.get('codigo')}: {str(o.get('descricao', ''))[:200]}")


if __name__ == "__main__":
    main()
