"""Envia S-1298 (Reabertura de Eventos Periodicos) ao eSocial.

Uso:
  python -m app.envio_s1298 --cnpj 09445502000109 --per-apur 2025-08 \
      --cert <path.pfx> --senha <senha> --ambiente producao
"""
from __future__ import annotations

import argparse
import sys
import time

from .xml_s1298 import S1298XMLGenerator
from .xml_signer import S1010XMLSigner
from . import esocial_client


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cnpj", required=True, help="CNPJ completo (14 digitos)")
    ap.add_argument("--per-apur", required=True, help="AAAA-MM")
    ap.add_argument("--ind-apuracao", default="1", choices=["1", "2"],
                    help="1=Mensal, 2=13o")
    ap.add_argument("--cert", required=True)
    ap.add_argument("--senha", required=True)
    ap.add_argument("--ambiente", choices=["homologacao", "producao"], default="homologacao")
    ap.add_argument("--grupo", type=int, default=3,
                    help="Grupo do envioLoteEventos (Simplificado periodicos=3)")
    args = ap.parse_args()

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


if __name__ == "__main__":
    main()
