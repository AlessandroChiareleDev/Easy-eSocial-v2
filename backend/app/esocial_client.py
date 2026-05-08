"""Cliente eSocial enxuto para REENVIO de XMLs assinados.

Adaptado de Projeto/python-backend/esocial/esocial_client.py
Foco: aceitar lista de bytes de XML JA assinados (vindos do ZIP do retorno)
e empacotar em UM lote por chamada -> EnviarLoteEventos.

Diferencas do original:
  - sem geracao/assinatura;
  - aceita varios eventos no mesmo <eventos> (limite 40);
  - sem dependencia de zeep (requests puro).
"""
from __future__ import annotations

import os
import re
import tempfile
from dataclasses import dataclass
from typing import Iterable

import requests
import urllib3
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    pkcs12,
)
from lxml import etree

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


URLS = {
    "producao": {
        # endpoints atuais (esocial Simplificado)
        "envio": "https://webservices.envio.esocial.gov.br/servicos/empregador/enviarloteeventos/WsEnviarLoteEventos.svc",
        "consulta": "https://webservices.consulta.esocial.gov.br/servicos/empregador/consultarloteeventos/WsConsultarLoteEventos.svc",
    },
    "homologacao": {
        "envio": "https://webservices.producaorestrita.esocial.gov.br/servicos/empregador/enviarloteeventos/WsEnviarLoteEventos.svc",
        "consulta": "https://webservices.producaorestrita.esocial.gov.br/servicos/empregador/consultarloteeventos/WsConsultarLoteEventos.svc",
    },
}


@dataclass
class EventoLote:
    """Um item do lote: bytes do XML assinado + Id extraido."""
    xml_bytes: bytes
    id_evento: str  # ex: 'ID1094455020000002025091819283700008'


def _extrair_id(xml_bytes: bytes) -> str | None:
    txt = xml_bytes.decode("utf-8", errors="replace")
    m = re.search(r'<evt\w+[^>]*\sId="([^"]+)"', txt)
    return m.group(1) if m else None


def _strip_xml_declaration(xml_bytes: bytes) -> str:
    s = xml_bytes.decode("utf-8")
    s = re.sub(r"^\s*<\?xml[^?]+\?>\s*", "", s)
    return s.strip()


def _pfx_para_pem_temp(cert_path: str, cert_password: str) -> tuple[str, str]:
    """Devolve (cert_pem_path, key_pem_path) em arquivos temporarios."""
    with open(cert_path, "rb") as f:
        pfx = f.read()
    pwd = cert_password.encode() if isinstance(cert_password, str) else cert_password
    key, cert, _ = pkcs12.load_key_and_certificates(pfx, pwd, backend=default_backend())
    cert_t = tempfile.NamedTemporaryFile(mode="wb", delete=False, suffix=".pem")
    key_t = tempfile.NamedTemporaryFile(mode="wb", delete=False, suffix=".pem")
    try:
        cert_t.write(cert.public_bytes(Encoding.PEM)); cert_t.close()
        key_t.write(
            key.private_bytes(
                encoding=Encoding.PEM,
                format=PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=NoEncryption(),
            )
        )
        key_t.close()
    except Exception:
        for p in (cert_t.name, key_t.name):
            try:
                os.unlink(p)
            except Exception:  # noqa: BLE001
                pass
        raise
    return cert_t.name, key_t.name


def _montar_lote_xml(
    eventos: list[EventoLote],
    grupo: int,
    cnpj_empregador: str,
    cnpj_transmissor: str,
) -> str:
    """Monta string do <eSocial><envioLoteEventos>... com varios eventos.

    Regra eSocial (replicada do legado APPA soap_builder.py:151):
      - <ideEmpregador> usa CNPJ RAIZ (8 digitos) -> precisa bater com nrInsc do evento
      - <ideTransmissor> usa CNPJ COMPLETO (14 digitos)
    """
    nr_insc_emp = str(cnpj_empregador)[:8]
    nr_insc_trans = str(cnpj_transmissor)
    eventos_xml = []
    for ev in eventos:
        body = _strip_xml_declaration(ev.xml_bytes)
        eventos_xml.append(f'<evento Id="{ev.id_evento}">{body}</evento>')
    eventos_concat = "\n".join(eventos_xml)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<eSocial xmlns="http://www.esocial.gov.br/schema/lote/eventos/envio/v1_1_1">'
        f'<envioLoteEventos grupo="{grupo}">'
        '<ideEmpregador>'
        f'<tpInsc>1</tpInsc><nrInsc>{nr_insc_emp}</nrInsc>'
        '</ideEmpregador>'
        '<ideTransmissor>'
        f'<tpInsc>1</tpInsc><nrInsc>{nr_insc_trans}</nrInsc>'
        '</ideTransmissor>'
        f'<eventos>{eventos_concat}</eventos>'
        '</envioLoteEventos>'
        '</eSocial>'
    )


def enviar_lote(
    eventos: list[EventoLote],
    *,
    cert_path: str,
    cert_password: str,
    cnpj_empregador: str,
    cnpj_transmissor: str | None = None,
    ambiente: str = "homologacao",
    grupo: int = 2,
    timeout_s: int = 90,
) -> dict:
    """Envia 1 lote (lista de eventos ja assinados) ao eSocial.

    Retorna dict com:
      sucesso: bool, codigo_resposta, descricao, protocolo, dh_recepcao,
      ocorrencias, response_xml, lote_xml (para auditoria).
    """
    if not eventos:
        return {"sucesso": False, "erro": "lote vazio"}
    if cnpj_transmissor is None:
        cnpj_transmissor = cnpj_empregador

    lote_xml = _montar_lote_xml(eventos, grupo, cnpj_empregador, cnpj_transmissor)
    lote_sem_decl = re.sub(r"<\?xml[^?]+\?>\s*", "", lote_xml)

    soap = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" '
        'xmlns:v1="http://www.esocial.gov.br/servicos/empregador/lote/eventos/envio/v1_1_0">'
        '<soapenv:Header/>'
        '<soapenv:Body>'
        '<v1:EnviarLoteEventos>'
        f'<v1:loteEventos>{lote_sem_decl}</v1:loteEventos>'
        '</v1:EnviarLoteEventos>'
        '</soapenv:Body>'
        '</soapenv:Envelope>'
    )
    headers = {
        "Content-Type": "text/xml; charset=utf-8",
        "SOAPAction": (
            "http://www.esocial.gov.br/servicos/empregador/lote/eventos/envio/"
            "v1_1_0/ServicoEnviarLoteEventos/EnviarLoteEventos"
        ),
    }
    cert_pem, key_pem = _pfx_para_pem_temp(cert_path, cert_password)
    try:
        r = requests.post(
            URLS[ambiente]["envio"],
            data=soap.encode("utf-8"),
            headers=headers,
            cert=(cert_pem, key_pem),
            verify=False,
            timeout=timeout_s,
        )
    except Exception as e:  # noqa: BLE001
        return {
            "sucesso": False,
            "erro": f"falha_rede: {type(e).__name__}: {e}",
            "lote_xml": lote_xml,
        }
    finally:
        for p in (cert_pem, key_pem):
            try:
                os.unlink(p)
            except Exception:  # noqa: BLE001
                pass

    out = _parse_resposta_envio(r.text, status_http=r.status_code)
    out["lote_xml"] = lote_xml
    return out


def _parse_resposta_envio(response_text: str, *, status_http: int) -> dict:
    base = {"http_status": status_http, "response_xml": response_text or ""}
    if not response_text or not response_text.strip():
        return {**base, "sucesso": False, "erro": "resposta vazia"}
    try:
        x = etree.fromstring(response_text.encode("utf-8"))
    except Exception as e:  # noqa: BLE001
        return {**base, "sucesso": False, "erro": f"xml invalido: {e}"}

    def _xp(xp: str) -> list[str]:
        return x.xpath(xp)  # type: ignore[no-any-return]

    cd = _xp('//*[local-name()="cdResposta"]/text()')
    desc = _xp('//*[local-name()="descResposta"]/text()')
    proto = _xp('//*[local-name()="protocoloEnvio"]/text()') or _xp(
        '//*[local-name()="nrProtocolo"]/text()'
    )
    dh = _xp('//*[local-name()="dhRecepcao"]/text()')
    ocorr = []
    for oc in x.xpath('//*[local-name()="ocorrencia"]'):
        codigo = oc.xpath('.//*[local-name()="codigo"]/text()')
        descr = oc.xpath('.//*[local-name()="descricao"]/text()')
        tipo = oc.xpath('.//*[local-name()="tipo"]/text()')
        if codigo:
            ocorr.append(
                {
                    "codigo": codigo[0],
                    "descricao": descr[0] if descr else "",
                    "tipo": tipo[0] if tipo else "",
                }
            )

    sucesso = bool(cd and cd[0] == "201")
    return {
        **base,
        "sucesso": sucesso,
        "codigo_resposta": cd[0] if cd else None,
        "descricao": desc[0] if desc else None,
        "protocolo": proto[0] if proto else None,
        "dh_recepcao": dh[0] if dh else None,
        "ocorrencias": ocorr,
    }


def consultar_lote(
    protocolo: str,
    *,
    cert_path: str,
    cert_password: str,
    ambiente: str = "homologacao",
    timeout_s: int = 90,
) -> dict:
    """Consulta lote via ConsultarLoteEventos."""
    soap = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" '
        'xmlns:v1="http://www.esocial.gov.br/servicos/empregador/lote/eventos/envio/consulta/'
        'retornoProcessamento/v1_1_0">'
        '<soapenv:Header/>'
        '<soapenv:Body>'
        '<v1:ConsultarLoteEventos>'
        '<v1:consulta>'
        '<eSocial xmlns="http://www.esocial.gov.br/schema/lote/eventos/envio/consulta/'
        'retornoProcessamento/v1_0_0">'
        '<consultaLoteEventos>'
        f'<protocoloEnvio>{protocolo}</protocoloEnvio>'
        '</consultaLoteEventos>'
        '</eSocial>'
        '</v1:consulta>'
        '</v1:ConsultarLoteEventos>'
        '</soapenv:Body>'
        '</soapenv:Envelope>'
    )
    headers = {
        "Content-Type": "text/xml; charset=utf-8",
        "SOAPAction": (
            "http://www.esocial.gov.br/servicos/empregador/lote/eventos/envio/consulta/"
            "retornoProcessamento/v1_1_0/ServicoConsultarLoteEventos/ConsultarLoteEventos"
        ),
    }
    cert_pem, key_pem = _pfx_para_pem_temp(cert_path, cert_password)
    try:
        r = requests.post(
            URLS[ambiente]["consulta"],
            data=soap.encode("utf-8"),
            headers=headers,
            cert=(cert_pem, key_pem),
            verify=False,
            timeout=timeout_s,
        )
    except Exception as e:  # noqa: BLE001
        return {"sucesso": False, "erro": f"falha_rede: {type(e).__name__}: {e}"}
    finally:
        for p in (cert_pem, key_pem):
            try:
                os.unlink(p)
            except Exception:  # noqa: BLE001
                pass

    base = {"http_status": r.status_code, "response_xml": r.text or ""}
    if r.status_code != 200:
        return {**base, "sucesso": False, "erro": f"http {r.status_code}"}

    try:
        x = etree.fromstring(r.text.encode("utf-8"))
    except Exception as e:  # noqa: BLE001
        return {**base, "sucesso": False, "erro": f"xml invalido: {e}"}

    lote_cd = x.xpath(
        '//*[local-name()="retornoProcessamentoLoteEventos"]'
        '/*[local-name()="status"]/*[local-name()="cdResposta"]/text()'
    )
    lote_desc = x.xpath(
        '//*[local-name()="retornoProcessamentoLoteEventos"]'
        '/*[local-name()="status"]/*[local-name()="descResposta"]/text()'
    )

    eventos_out = []
    # Estrutura real:
    #   retornoProcessamentoLoteEventos
    #     retornoEventos
    #       evento Id="...">
    #         retornoEvento
    #           eSocial>retornoEvento>... (cdResposta, descResposta, recibo, ocs)
    # O @Id fica em <evento> e os campos no <retornoEvento> filho.
    eventos_nodes = x.xpath(
        '//*[local-name()="retornoProcessamentoLoteEventos"]'
        '/*[local-name()="retornoEventos"]'
        '/*[local-name()="evento"]'
    )
    for ev_node in eventos_nodes:
        ide = ev_node.get("Id")
        # bloco retornoEvento (pode ter eSocial>retornoEvento aninhado)
        cd = ev_node.xpath('.//*[local-name()="processamento"]/*[local-name()="cdResposta"]/text()')
        ds = ev_node.xpath('.//*[local-name()="processamento"]/*[local-name()="descResposta"]/text()')
        recibo = ev_node.xpath('.//*[local-name()="recibo"]/*[local-name()="nrRecibo"]/text()')
        ocs = []
        for oc in ev_node.xpath('.//*[local-name()="ocorrencia"]'):
            codigo = oc.xpath('.//*[local-name()="codigo"]/text()')
            descr = oc.xpath('.//*[local-name()="descricao"]/text()')
            tipo = oc.xpath('.//*[local-name()="tipo"]/text()')
            if codigo:
                ocs.append(
                    {
                        "codigo": codigo[0],
                        "descricao": descr[0] if descr else "",
                        "tipo": tipo[0] if tipo else "",
                    }
                )
        ev_xml = etree.tostring(ev_node, encoding="utf-8").decode("utf-8")
        eventos_out.append(
            {
                "id_evento": ide,
                "codigo": cd[0] if cd else None,
                "descricao": ds[0] if ds else None,
                "nr_recibo": recibo[0] if recibo else None,
                "ocorrencias": ocs,
                "xml_retorno": ev_xml,
            }
        )

    return {
        **base,
        "sucesso": bool(lote_cd and lote_cd[0] == "201"),
        "codigo_lote": lote_cd[0] if lote_cd else None,
        "descricao_lote": lote_desc[0] if lote_desc else None,
        "eventos": eventos_out,
    }
