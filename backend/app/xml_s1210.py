"""
Gerador de XML S-1210 (evtPgtos) — Pagamento de Rendimentos do Trabalho
Namespace: v_S_01_03_00
Finalidade: Informar pagamentos realizados a cada beneficiário no período.
            Suporta indRetif=1 (original) e indRetif=2 (retificação).
"""

from lxml import etree
from datetime import datetime, timezone
import threading

NS = "http://www.esocial.gov.br/schema/evt/evtPgtos/v_S_01_03_00"
NSMAP = {None: NS}

# Contador atomico global por segundo para evitar colisao de @Id em envios
# paralelos (workers/threads). O leiaute eSocial fixa o @Id em 36 chars
# ("ID" + tpInsc(1) + CNPJ(14) + AAAAMMDDhhmmss(14) + seq(5)), entao a unica
# folga para unicidade fica nos 5 digitos do seq (00001..99999 por segundo).
_ID_LOCK = threading.Lock()
_ID_LAST_TS: str = ""
_ID_COUNTER: int = 0


def _sub(parent, tag, text=None):
    """Cria SubElement com namespace qualificado."""
    el = etree.SubElement(parent, f"{{{NS}}}{tag}")
    if text is not None:
        el.text = str(text)
    return el


def _gerar_id(tp_insc: int, nr_insc: str, seq: int = 1) -> str:
    """
    Gera @Id unico no formato eSocial (36 chars).

    NOTA: o argumento `seq` eh ignorado de proposito. Ele era usado como
    "indice dentro do lote" e causava colisao quando varios lotes paralelos
    rodavam no mesmo segundo (erro 543 - "Ja existe um evento com mesmo
    identificador"). Aqui usamos um contador atomico global por segundo,
    compartilhado entre threads, garantindo unicidade ate 99999 eventos/s.
    """
    global _ID_LAST_TS, _ID_COUNTER
    now = datetime.now(timezone.utc)
    nr_insc_padded = nr_insc.ljust(14, "0")[:14]
    ts = now.strftime("%Y%m%d%H%M%S")
    with _ID_LOCK:
        if ts != _ID_LAST_TS:
            _ID_LAST_TS = ts
            _ID_COUNTER = 0
        _ID_COUNTER += 1
        seq_global = _ID_COUNTER
    return f"ID{tp_insc}{nr_insc_padded}{ts}{seq_global:05d}"


def _build_ded_depen(parent, deps: list[dict]):
    """Monta lista de <dedDepen> dentro de <infoIRCR>."""
    for dep in deps:
        dd = _sub(parent, "dedDepen")
        _sub(dd, "tpRend", dep["tpRend"])
        _sub(dd, "cpfDep", dep["cpfDep"])
        _sub(dd, "vlrDedDep", dep["vlrDedDep"])


def _build_pen_alim(parent, pens: list[dict]):
    """Monta lista de <penAlim> dentro de <infoIRCR>."""
    for pen in pens:
        pa = _sub(parent, "penAlim")
        _sub(pa, "tpRend", pen["tpRend"])
        _sub(pa, "cpfDep", pen["cpfDep"])
        _sub(pa, "vlrDedPenAlim", pen["vlrDedPenAlim"])


def _build_plan_saude(parent, plan_saude: dict):
    """Monta <planSaude> dentro de <infoIRComplem>.
    plan_saude: {cnpjOper, regANS, vlrSaudeTit, infoDepSau?[]}
    """
    ps = _sub(parent, "planSaude")
    _sub(ps, "cnpjOper", plan_saude["cnpjOper"])
    _sub(ps, "regANS", plan_saude["regANS"])
    _sub(ps, "vlrSaudeTit", plan_saude["vlrSaudeTit"])
    for dep in plan_saude.get("infoDepSau", []):
        ids = _sub(ps, "infoDepSau")
        _sub(ids, "cpfDep", dep["cpfDep"])
        _sub(ids, "vlrSaudeDep", dep["vlrSaudeDep"])


def _build_plan_saude_entries(parent, plan_saude):
    """Monta um ou mais <planSaude> — aceita dict único ou lista de dicts."""
    if isinstance(plan_saude, dict):
        _build_plan_saude(parent, plan_saude)
    elif isinstance(plan_saude, list):
        for ps in plan_saude:
            _build_plan_saude(parent, ps)


def _build_info_ir_complem(parent, info_ir: dict, plan_saude=None):
    """Monta <infoIRComplem> com uma ou mais <infoIRCR> e opcional <planSaude>."""
    irc = _sub(parent, "infoIRComplem")
    for cr in info_ir.get("infoIRCR", []):
        ircr = _sub(irc, "infoIRCR")
        _sub(ircr, "tpCR", cr["tpCR"])
        if cr.get("vrCR"):
            _sub(ircr, "vrCR", cr["vrCR"])
        if cr.get("dedDepen"):
            _build_ded_depen(ircr, cr["dedDepen"])
        if cr.get("penAlim"):
            _build_pen_alim(ircr, cr["penAlim"])
    if plan_saude:
        _build_plan_saude_entries(irc, plan_saude)


class S1210XMLGenerator:
    """Gera XML S-1210 evtPgtos (Pagamento de Rendimentos do Trabalho)"""

    AMBIENTES_VALIDOS = {"1", "2"}
    IND_RETIF_VALIDOS = {"1", "2"}
    TP_PGTO_VALIDOS = {"1", "2", "3", "4", "5", "6", "7", "8", "9"}

    @staticmethod
    def gerar(
        empregador: dict,
        beneficiario: dict,
        info_pgtos: list[dict],
        per_apur: str,
        ind_retif: str = "1",
        nr_recibo: str = None,
        info_ir_complem: dict = None,
        plan_saude: dict = None,
        seq: int = 1,
        tp_amb: str = "2",
    ) -> bytes:
        """
        Gera XML S-1210 para pagamento de rendimentos de um beneficiário.

        Args:
            empregador: dict com tpInsc e nrInsc (CNPJ raiz 8 dígitos)
            beneficiario: dict com cpfBenef (CPF 11 dígitos)
            info_pgtos: lista de pagamentos — cada um com:
                - dtPgto: data do pagamento (AAAA-MM-DD)
                - tpPgto: tipo do pagamento (1-9)
                - perRef: período de referência (AAAA-MM)
                - ideDmDev: identificador do demonstrativo (referência ao S-1200)
                - vrLiq: valor líquido pago
            per_apur: período de apuração (AAAA-MM)
            ind_retif: "1" = original, "2" = retificação
            nr_recibo: nrRecibo do evento original (obrigatório se indRetif=2)
            info_ir_complem: (opcional) complemento de IR — dict com:
                - infoIRCR: lista de dicts com tpCR, vrCR?, dedDepen?[]
            seq: sequencial para ID do evento
            tp_amb: "1" = produção, "2" = homologação

        Returns:
            XML como bytes (UTF-8)
        """
        # --- Validações ---
        if tp_amb not in S1210XMLGenerator.AMBIENTES_VALIDOS:
            raise ValueError(f"tpAmb inválido: {tp_amb}. Use '1' (produção) ou '2' (homologação)")
        if ind_retif not in S1210XMLGenerator.IND_RETIF_VALIDOS:
            raise ValueError(f"indRetif inválido: {ind_retif}. Use '1' (original) ou '2' (retificação)")
        if not per_apur or len(per_apur) != 7 or per_apur[4] != "-":
            raise ValueError(f"perApur inválido: {per_apur}. Formato esperado: AAAA-MM")
        if ind_retif == "2" and not nr_recibo:
            raise ValueError("nrRecibo é obrigatório quando indRetif=2 (retificação)")

        cpf = str(beneficiario.get("cpfBenef", ""))
        if not cpf or len(cpf) != 11 or not cpf.isdigit():
            raise ValueError(f"cpfBenef inválido: '{cpf}'. Deve ter 11 dígitos numéricos")
        if not info_pgtos:
            raise ValueError("info_pgtos não pode ser vazio — pelo menos um pagamento é obrigatório")

        tp_insc = int(empregador["tpInsc"])
        nr_insc = str(empregador["nrInsc"])  # CNPJ completo (14) ou raiz (8) — caller decide

        evt_id = _gerar_id(tp_insc, nr_insc, seq)

        # --- Root ---
        root = etree.Element(f"{{{NS}}}eSocial", nsmap=NSMAP)
        evt = _sub(root, "evtPgtos")
        evt.set("Id", evt_id)

        # --- ideEvento ---
        ide_evento = _sub(evt, "ideEvento")
        _sub(ide_evento, "indRetif", ind_retif)
        if ind_retif == "2":
            _sub(ide_evento, "nrRecibo", nr_recibo)
        _sub(ide_evento, "perApur", per_apur)
        _sub(ide_evento, "tpAmb", tp_amb)
        _sub(ide_evento, "procEmi", "1")
        _sub(ide_evento, "verProc", "EasySocial_1.0")

        # --- ideEmpregador ---
        ide_emp = _sub(evt, "ideEmpregador")
        _sub(ide_emp, "tpInsc", str(tp_insc))
        _sub(ide_emp, "nrInsc", nr_insc)

        # --- ideBenef ---
        ide_benef = _sub(evt, "ideBenef")
        _sub(ide_benef, "cpfBenef", cpf)

        # --- infoPgto (um ou mais pagamentos) ---
        for pgto in info_pgtos:
            ip = _sub(ide_benef, "infoPgto")
            _sub(ip, "dtPgto", pgto["dtPgto"])
            _sub(ip, "tpPgto", pgto["tpPgto"])
            if pgto.get("perRef"):
                _sub(ip, "perRef", pgto["perRef"])
            _sub(ip, "ideDmDev", pgto["ideDmDev"])
            _sub(ip, "vrLiq", pgto["vrLiq"])

        # --- infoIRComplem (opcional) ---
        if info_ir_complem and info_ir_complem.get("infoIRCR"):
            _build_info_ir_complem(ide_benef, info_ir_complem, plan_saude)
        elif plan_saude:
            # planSaude sem infoIRCR — precisa criar infoIRComplem só com planSaude
            irc = _sub(ide_benef, "infoIRComplem")
            _build_plan_saude_entries(irc, plan_saude)

        return etree.tostring(root, xml_declaration=True, encoding="UTF-8")

    @staticmethod
    def gerar_retificacao(
        empregador: dict,
        beneficiario: dict,
        info_pgtos: list[dict],
        per_apur: str,
        nr_recibo: str,
        info_ir_complem: dict = None,
        plan_saude: dict = None,
        seq: int = 1,
        tp_amb: str = "2",
    ) -> bytes:
        """Atalho para gerar S-1210 de retificação (indRetif=2)."""
        return S1210XMLGenerator.gerar(
            empregador=empregador,
            beneficiario=beneficiario,
            info_pgtos=info_pgtos,
            per_apur=per_apur,
            ind_retif="2",
            nr_recibo=nr_recibo,
            info_ir_complem=info_ir_complem,
            plan_saude=plan_saude,
            seq=seq,
            tp_amb=tp_amb,
        )

    @staticmethod
    def gerar_lote(
        empregador: dict,
        eventos: list[dict],
        tp_amb: str = "2",
    ) -> list[bytes]:
        """
        Gera lote de XMLs S-1210 para múltiplos beneficiários.

        Args:
            empregador: dict com tpInsc e nrInsc
            eventos: lista de dicts, cada um com:
                - beneficiario: {cpfBenef}
                - info_pgtos: lista de pagamentos
                - per_apur: período de apuração (AAAA-MM)
                - ind_retif: "1" ou "2" (default "1")
                - nr_recibo: obrigatório se indRetif=2
                - info_ir_complem: (opcional) complemento IR
            tp_amb: "1" = produção, "2" = homologação

        Returns:
            Lista de XMLs como bytes (UTF-8)
        """
        if len(eventos) > 50:
            raise ValueError(f"Lote máximo: 50 eventos. Recebido: {len(eventos)}")

        return [
            S1210XMLGenerator.gerar(
                empregador=empregador,
                beneficiario=ev["beneficiario"],
                info_pgtos=ev["info_pgtos"],
                per_apur=ev["per_apur"],
                ind_retif=ev.get("ind_retif", "1"),
                nr_recibo=ev.get("nr_recibo"),
                info_ir_complem=ev.get("info_ir_complem"),
                seq=i,
                tp_amb=tp_amb,
            )
            for i, ev in enumerate(eventos, start=1)
        ]
