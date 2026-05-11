"""Extrator de campos do XML S-1210 (do ZIP de retorno do eSocial).

Le o XML assinado de um S-1210 ja registrado e devolve um dict no formato
esperado por S1210XMLGenerator.gerar, para regerar o evento com Id novo,
indRetif=2 e nrRecibo apontando para a versao ativa.
"""
from __future__ import annotations

from lxml import etree


def _txt(el, xp: str) -> str | None:
    r = el.xpath(xp + "/text()")
    return r[0] if r else None


def _all(el, xp: str):
    return el.xpath(xp)


def extrair_s1210(xml_bytes: bytes) -> dict:
    """Devolve dict com chaves:
        empregador { tpInsc, nrInsc }       (nrInsc = CNPJ raiz 8 digitos)
        beneficiario { cpfBenef }
        per_apur                            ('AAAA-MM')
        info_pgtos [{ dtPgto, tpPgto, perRef?, ideDmDev, vrLiq }, ...]
        info_ir_complem | None              ({ infoIRCR: [...] })
        plan_saude | None                   (dict ou lista)
        nr_recibo_atual | None              (nrRecibo gravado no XML, se houver)
        ind_retif_atual                     ('1' ou '2')
    """
    root = etree.fromstring(xml_bytes)

    evt = root.xpath('//*[local-name()="evtPgtos"]')
    if not evt:
        raise ValueError("evtPgtos nao encontrado no XML")
    evt = evt[0]

    ide_evento = evt.xpath('./*[local-name()="ideEvento"]')[0]
    ide_emp = evt.xpath('./*[local-name()="ideEmpregador"]')[0]
    ide_benef = evt.xpath('./*[local-name()="ideBenef"]')[0]

    per_apur = _txt(ide_evento, './*[local-name()="perApur"]')
    ind_retif = _txt(ide_evento, './*[local-name()="indRetif"]') or "1"
    nr_recibo_atual = _txt(ide_evento, './*[local-name()="nrRecibo"]')

    tp_insc = _txt(ide_emp, './*[local-name()="tpInsc"]') or "1"
    nr_insc = _txt(ide_emp, './*[local-name()="nrInsc"]') or ""
    cpf_benef = _txt(ide_benef, './*[local-name()="cpfBenef"]')

    info_pgtos: list[dict] = []
    for ip in _all(ide_benef, './*[local-name()="infoPgto"]'):
        item = {
            "dtPgto": _txt(ip, './*[local-name()="dtPgto"]'),
            "tpPgto": _txt(ip, './*[local-name()="tpPgto"]'),
            "ideDmDev": _txt(ip, './*[local-name()="ideDmDev"]'),
            "vrLiq": _txt(ip, './*[local-name()="vrLiq"]'),
        }
        per_ref = _txt(ip, './*[local-name()="perRef"]')
        if per_ref:
            item["perRef"] = per_ref
        info_pgtos.append(item)

    info_ir_complem: dict | None = None
    plan_saude_list: list[dict] = []
    irc_nodes = _all(ide_benef, './*[local-name()="infoIRComplem"]')
    if irc_nodes:
        irc = irc_nodes[0]
        irs = []
        for cr in _all(irc, './*[local-name()="infoIRCR"]'):
            d = {"tpCR": _txt(cr, './*[local-name()="tpCR"]')}
            vr = _txt(cr, './*[local-name()="vrCR"]')
            if vr is not None:
                d["vrCR"] = vr
            ded = []
            for dd in _all(cr, './*[local-name()="dedDepen"]'):
                ded.append({
                    "tpRend": _txt(dd, './*[local-name()="tpRend"]'),
                    "cpfDep": _txt(dd, './*[local-name()="cpfDep"]'),
                    "vlrDedDep": _txt(dd, './*[local-name()="vlrDedDep"]'),
                })
            if ded:
                d["dedDepen"] = ded
            pen = []
            for pa in _all(cr, './*[local-name()="penAlim"]'):
                pen.append({
                    "tpRend": _txt(pa, './*[local-name()="tpRend"]'),
                    "cpfDep": _txt(pa, './*[local-name()="cpfDep"]'),
                    "vlrDedPenAlim": _txt(pa, './*[local-name()="vlrDedPenAlim"]'),
                })
            if pen:
                d["penAlim"] = pen
            irs.append(d)
        if irs:
            info_ir_complem = {"infoIRCR": irs}

        for ps in _all(irc, './*[local-name()="planSaude"]'):
            ps_d = {
                "cnpjOper": _txt(ps, './*[local-name()="cnpjOper"]'),
                "regANS": _txt(ps, './*[local-name()="regANS"]'),
                "vlrSaudeTit": _txt(ps, './*[local-name()="vlrSaudeTit"]'),
            }
            deps = []
            for d in _all(ps, './*[local-name()="infoDepSau"]'):
                deps.append({
                    "cpfDep": _txt(d, './*[local-name()="cpfDep"]'),
                    "vlrSaudeDep": _txt(d, './*[local-name()="vlrSaudeDep"]'),
                })
            if deps:
                ps_d["infoDepSau"] = deps
            plan_saude_list.append(ps_d)

    plan_saude: dict | list | None
    if not plan_saude_list:
        plan_saude = None
    elif len(plan_saude_list) == 1:
        plan_saude = plan_saude_list[0]
    else:
        plan_saude = plan_saude_list

    return {
        "empregador": {"tpInsc": int(tp_insc), "nrInsc": (nr_insc or "")[:8]},
        "beneficiario": {"cpfBenef": cpf_benef},
        "per_apur": per_apur,
        "info_pgtos": info_pgtos,
        "info_ir_complem": info_ir_complem,
        "plan_saude": plan_saude,
        "nr_recibo_atual": nr_recibo_atual,
        "ind_retif_atual": ind_retif,
    }


def extrair_s5002(xml_bytes: bytes) -> dict:
    """Extrai campos do S-5002 (evtIrrfBenefRet, retorno consolidado de IR).

    Devolve dict com chaves usadas pelo modal do S-1210 Anual:
      cpfBenef
      perApur                       ('AAAA-MM')
      id_evento
      infoIR  [{ tpInfoIR, valor }]
      totApurMen_CRMen, totApurMen_vlrRendTrib,
      totApurMen_vlrPrevOficial, totApurMen_vlrCRMen
    """
    root = etree.fromstring(xml_bytes)
    evt_list = root.xpath('//*[local-name()="evtIrrfBenefRet"]')
    if not evt_list:
        return {}
    evt = evt_list[0]
    id_ev = evt.attrib.get("Id")

    ide_evento = evt.xpath('./*[local-name()="ideEvento"]')
    ide_benef = evt.xpath('./*[local-name()="ideTrabalhador"]') or evt.xpath('./*[local-name()="ideBenef"]')

    per_apur = None
    if ide_evento:
        per_apur = _txt(ide_evento[0], './*[local-name()="perApur"]')

    cpf_benef = None
    if ide_benef:
        cpf_benef = (
            _txt(ide_benef[0], './*[local-name()="cpfBenef"]')
            or _txt(ide_benef[0], './*[local-name()="cpfTrab"]')
        )

    info_ir_list: list[dict] = []
    for ii in evt.xpath('.//*[local-name()="infoIR"]'):
        tp = _txt(ii, './*[local-name()="tpInfoIR"]')
        vl = _txt(ii, './*[local-name()="valor"]')
        if tp is None and vl is None:
            continue
        info_ir_list.append({"tpInfoIR": tp, "valor": vl})

    cr_men = None
    vlr_rend_trib = None
    vlr_prev_oficial = None
    vlr_cr_men = None
    consolid = evt.xpath('.//*[local-name()="consolidApurMen"]')
    if consolid:
        c = consolid[0]
        cr_men = _txt(c, './*[local-name()="CRMen"]')
        vlr_rend_trib = _txt(c, './*[local-name()="vlrRendTrib"]')
        vlr_prev_oficial = _txt(c, './*[local-name()="vlrPrevOficial"]')
        vlr_cr_men = _txt(c, './*[local-name()="vlrCRMen"]')

    return {
        "id_evento": id_ev,
        "cpfBenef": cpf_benef,
        "perApur": per_apur,
        "infoIR": info_ir_list,
        "totApurMen_CRMen": cr_men,
        "totApurMen_vlrRendTrib": vlr_rend_trib,
        "totApurMen_vlrPrevOficial": vlr_prev_oficial,
        "totApurMen_vlrCRMen": vlr_cr_men,
    }
