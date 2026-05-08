"""Comparacao de corpo de eventos eSocial.

Detecta retificacao "vazia" (XML novo identico ao antigo) que causaria
erro 543 ("Já existe na base de dados do Ambiente Nacional um evento com
mesmo identificador").

Estrategia: extrair apenas o corpo <ideEmpregador>...</ideBenef> do evento
(ignorando <ideEvento> que sempre muda na retificacao por causa do @Id e
nrRecibo), normalizar (remove signature, atributos Id, espacos), e comparar
hash SHA-256.
"""
from __future__ import annotations
import hashlib
import re

_RE_SIGNATURE = re.compile(rb"<ds:Signature.*?</ds:Signature>", re.DOTALL)
_RE_SIGNATURE_S = re.compile(r"<ds:Signature.*?</ds:Signature>", re.DOTALL)
_RE_ID_ATTR = re.compile(r'\s+Id="[^"]+"')
_RE_WS = re.compile(r"\s+")
_RE_CORPO = re.compile(r"<ideEmpregador>.*?</ideBenef>", re.DOTALL)


def _to_str(xml) -> str:
    if isinstance(xml, bytes):
        return xml.decode("utf-8", errors="replace")
    return xml


def corpo_evento_canonico(xml) -> str:
    """Devolve o corpo <ideEmpregador>...</ideBenef> normalizado.

    Retorna string vazia se nao conseguir extrair (XML invalido, etc).
    """
    s = _to_str(xml)
    s = _RE_SIGNATURE_S.sub("", s)
    s = _RE_ID_ATTR.sub("", s)
    s = _RE_WS.sub(" ", s).strip()
    m = _RE_CORPO.search(s)
    return m.group(0) if m else ""


def hash_corpo(xml) -> str:
    canon = corpo_evento_canonico(xml)
    if not canon:
        return ""
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def eventos_iguais(xml_a, xml_b) -> bool:
    """True se o corpo do evento (ignorando ideEvento e signature) e identico."""
    ha = hash_corpo(xml_a)
    hb = hash_corpo(xml_b)
    return bool(ha) and ha == hb
