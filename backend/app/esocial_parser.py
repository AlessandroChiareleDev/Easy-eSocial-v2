"""Parser leve de XMLs de retorno eSocial.

Estratégia: parsear com lxml ignorando namespace (local-name) e extrair
campos comuns. NÃO valida schema. Apenas indexa pra busca/timeline.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from typing import Any

from lxml import etree

# Mapa nome_técnico_evento -> código eSocial (para busca)
EVENTO_PATTERNS = {
    "evtAdmissao": "S-2200",
    "evtAdmPrelim": "S-2190",
    "evtAltCadastral": "S-2205",
    "evtAltContratual": "S-2206",
    "evtAfastTemp": "S-2230",
    "evtMudancaCPF": "S-2298",
    "evtDeslig": "S-2299",
    "evtRemun": "S-1200",
    "evtPgtos": "S-1210",
    "evtAqProd": "S-1250",
    "evtComProd": "S-1260",
    "evtCS": "S-1280",
    "evtBenPrRP": "S-2410",
    "evtCdBenPrRP": "S-2416",
    "evtCdBenPRP": "S-2420",
    "evtTSVInicio": "S-2300",
    "evtTSVAltContr": "S-2306",
    "evtTSVTermino": "S-2399",
    "evtIrrfBenef": "S-1207",
    "evtBasesTrab": "S-5001",
    "evtBasesFGTS": "S-5003",
    "evtIrrfBenefRet": "S-5002",
    "evtCS_Tom": "S-5011",
    "evtIrrfTrab": "S-5012",
    "evtFGTSConting": "S-5013",
    "evtRemunRPPS": "S-1202",
    "evtRmnRPPS": "S-1202",
    "evtTabRubrica": "S-1010",
    "evtTabLotacao": "S-1020",
    "evtInfoEmpregador": "S-1000",
    "evtFechaEvPer": "S-1299",
    "evtAbreEvPer": "S-1298",
    "evtExclusao": "S-3000",
    "evtBenIn": "S-2405",
}


def _local(tag: str) -> str:
    """Remove namespace prefix de uma tag."""
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def _find_first_local(elem: etree._Element, name: str) -> etree._Element | None:
    """Busca primeiro descendente cujo local-name == name."""
    for el in elem.iter():
        if _local(el.tag) == name:
            return el
    return None


def _find_text(elem: etree._Element, name: str) -> str | None:
    el = _find_first_local(elem, name)
    if el is not None and el.text:
        return el.text.strip()
    return None


def _find_attr(elem: etree._Element, name: str, attr: str) -> str | None:
    el = _find_first_local(elem, name)
    if el is not None:
        v = el.attrib.get(attr)
        return v.strip() if v else None
    return None


@dataclass
class EventoExtracted:
    tipo_evento: str  # Ex: "S-1210" ou nome técnico se desconhecido
    nome_tecnico: str | None  # Ex: "evtPgtos"
    id_evento: str | None
    cpf: str | None
    per_apur: str | None
    nr_recibo: str | None
    referenciado_recibo: str | None
    cd_resposta: str | None
    dt_processamento: str | None
    extras: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def parse_xml_bytes(data: bytes) -> EventoExtracted | None:
    """Parseia XML de retorno do eSocial e extrai campos-chave.

    Retorna None se não for XML válido.
    """
    try:
        root = etree.fromstring(data)
    except etree.XMLSyntaxError:
        return None

    # 1) Encontrar o elemento de evento (evt*)
    evt_el = None
    nome_tec = None
    for el in root.iter():
        ln = _local(el.tag)
        if ln.startswith("evt") and ln in EVENTO_PATTERNS:
            evt_el = el
            nome_tec = ln
            break
    # Fallback: qualquer evt*
    if evt_el is None:
        for el in root.iter():
            ln = _local(el.tag)
            if ln.startswith("evt"):
                evt_el = el
                nome_tec = ln
                break

    tipo = EVENTO_PATTERNS.get(nome_tec, nome_tec or "desconhecido")
    id_evento = evt_el.attrib.get("Id") if evt_el is not None else None

    cpf = _find_text(root, "cpfTrab") or _find_text(root, "cpfBenef") or _find_text(root, "cpfBen")
    per_apur = _find_text(root, "perApur") or _find_text(root, "perRef") or _find_text(root, "perAcumulado")

    # nrRecibo: pode ser <nrRecibo>...</nrRecibo>, <nrRec>..</nrRec>, ou attr nrRec em <recibo>
    nr_recibo = (
        _find_text(root, "nrRecibo")
        or _find_text(root, "nrRec")
        or _find_attr(root, "recibo", "nrRec")
    )

    # Referência (S-3000 → evento excluído; S-1210 → S-1200; etc.)
    referenciado = (
        _find_text(root, "nrRecArqBase")
        or _find_text(root, "nrReciboEvtRetif")
        or _find_attr(root, "ideEvento", "nrRecArqBase")
    )

    cd_resposta = _find_text(root, "cdResposta") or _find_attr(root, "status", "cdResposta")
    dt_proc = _find_text(root, "dhProcessamento") or _find_text(root, "dtProcessamento")

    return EventoExtracted(
        tipo_evento=tipo,
        nome_tecnico=nome_tec,
        id_evento=id_evento,
        cpf=cpf,
        per_apur=per_apur,
        nr_recibo=nr_recibo,
        referenciado_recibo=referenciado,
        cd_resposta=cd_resposta,
        dt_processamento=dt_proc,
        extras={},
    )
