"""Envio paralelo S-1210 v2 — polling cumulativo + workers paralelos.

Adaptacao do envio_teste_100 incorporando as licoes do
docs/como enviar s1210 em lotes 1 2 3 4/COMO_FAZER_LOTE3.md (sec 10).

Mudancas chave:
  * Polling CUMULATIVO ate cobrir TODOS os Ids do batch (anti-459)
    waits = [1,1.5,2,3,4] + [5.0]*55  (~5min)
  * 5 workers paralelos (ThreadPoolExecutor) com conexoes DB dedicadas
  * batch=50 (limite hard envioLoteEventos eSocial)
  * Feedback de progresso a cada N (default 250) com taxa CPF/min
  * Protecao 1089 (concorrencia) com 1 retry apos 30s
  * SEM_RETORNO -> status='pendente_consulta' (NAO erro_esocial),
    permite reconsulta posterior sem virar 459 falso.

Uso:
    python -m app.envio_paralelo_v2 \
        --per-apur 2025-08 --limite 500 --workers 5 --batch 50 \
        --cert <path.pfx> --senha <senha> --cnpj <14digitos> \
        --ambiente producao --pular-ja-tentados
"""
from __future__ import annotations

import argparse
import sys
import threading
import time
import concurrent.futures as cf
from dataclasses import dataclass

import psycopg2.extras

from . import db, esocial_client
from .envio_teste_100 import (
    _carregar_eventos_alvo,
    _criar_timeline_envio,
    _criar_items,
    _ler_xml_evento,
    _gravar_xml_enviado,
    _gravar_xml_retorno,
    _set_xml_enviado_oid,
    _atualizar_item,
    _atualizar_envio,
    CFG_GRUPO,
)
from .xml_extractor import extrair_s1210
from .xml_s1210 import S1210XMLGenerator
from .xml_signer import S1010XMLSigner


# ---------- Tunables ----------
DEFAULT_WORKERS = 5
DEFAULT_BATCH = 50
DEFAULT_PROGRESS_EVERY = 250
# Polling cumulativo: ~5min total. Espera ALL CPFs do batch antes de marcar timeout.
POLL_WAITS = [1.0, 1.5, 2.0, 3.0, 4.0] + [5.0] * 55
RETRY_1089_DELAY_S = 30


# ---------- Estado de progresso compartilhado ----------
@dataclass
class Progress:
    total: int
    ok: int = 0
    erro: int = 0
    pendente_consulta: int = 0
    tentados: int = 0  # CPFs cujo lote ja foi processado
    t0: float = 0.0
    last_report_at: int = 0
    every: int = DEFAULT_PROGRESS_EVERY

    def __post_init__(self) -> None:
        self._lock = threading.Lock()

    def add(self, *, ok: int, erro: int, pendente: int, tentados: int) -> None:
        with self._lock:
            self.ok += ok
            self.erro += erro
            self.pendente_consulta += pendente
            self.tentados += tentados
            # Reportar a cada N ou no final
            if self.tentados - self.last_report_at >= self.every or self.tentados >= self.total:
                self.last_report_at = self.tentados
                elapsed = time.time() - self.t0
                vel_s = (self.tentados / elapsed) if elapsed > 0 else 0
                vel_min = vel_s * 60
                taxa_erro = (self.erro / self.tentados * 100) if self.tentados else 0
                print(
                    f"  [PROGRESSO] {self.tentados}/{self.total}  "
                    f"ok={self.ok}  erro={self.erro}  pend_consulta={self.pendente_consulta}  "
                    f"vel={vel_s:.2f} CPF/s ({vel_min:.1f} CPF/min)  taxa_erro={taxa_erro:.1f}%  "
                    f"elapsed={elapsed:.0f}s",
                    flush=True,
                )


# ---------- Polling robusto cumulativo ----------
def _polling_cumulativo(
    protocolo: str,
    pacote_ids: set[str],
    *,
    cert_path: str,
    cert_password: str,
    ambiente: str,
    log_prefix: str = "",
) -> tuple[dict[str, dict], int]:
    """Pollingate cobrir todos os Ids do batch ou exaurir POLL_WAITS.

    Retorna (eventos_por_id, attempts_used).
    """
    eventos_acumulados: dict[str, dict] = {}
    attempts_used = 0
    for attempt, wait in enumerate(POLL_WAITS, start=1):
        time.sleep(wait)
        attempts_used = attempt
        try:
            cons = esocial_client.consultar_lote(
                protocolo,
                cert_path=cert_path,
                cert_password=cert_password,
                ambiente=ambiente,
            )
        except Exception as e:  # noqa: BLE001
            print(f"{log_prefix}[poll {attempt}] excecao consultar_lote: {e}", flush=True)
            continue

        for evt in (cons.get("eventos") or []):
            idv = evt.get("id_evento")
            if idv:
                eventos_acumulados[idv] = evt  # acumula

        cd = cons.get("codigo_lote")
        if attempt <= 6 or attempt % 6 == 0:
            print(
                f"{log_prefix}[poll {attempt}] cd_lote={cd} "
                f"acumulado={len(eventos_acumulados)}/{len(pacote_ids)}",
                flush=True,
            )

        # Sai quando temos retorno PRA TODOS os CPFs do batch
        if len(eventos_acumulados) >= len(pacote_ids):
            return eventos_acumulados, attempt
        # Se cd indica falha definitiva (nao 101/201) e ja tem alguma resposta, sai
        if cd and cd not in ("101", "201") and eventos_acumulados:
            return eventos_acumulados, attempt
    return eventos_acumulados, attempts_used


# ---------- Processamento de 1 batch ----------
def _processar_batch_paralelo(
    eventos: list[dict],
    items: list[int],
    *,
    empresa_id: int,
    cert_path: str,
    cert_password: str,
    cnpj: str,
    ambiente: str,
    pfx_data: bytes,
    progress: Progress,
    batch_idx: int,
) -> dict:
    """Espelho de _processar_lote, mas com polling cumulativo + conexoes proprias."""
    log_prefix = f"  [B{batch_idx:02d}] "
    conn_db = db.connect(empresa_id=empresa_id)
    conn_lo = db.connect(empresa_id=empresa_id)
    conn_w = db.connect(empresa_id=empresa_id)
    try:
        return _processar_batch_inner(
            eventos, items,
            cert_path=cert_path, cert_password=cert_password, cnpj=cnpj,
            ambiente=ambiente, pfx_data=pfx_data,
            conn_db=conn_db, conn_lo=conn_lo, conn_w=conn_w,
            progress=progress, log_prefix=log_prefix,
        )
    finally:
        for c in (conn_db, conn_lo, conn_w):
            try:
                c.close()
            except Exception:  # noqa: BLE001
                pass


def _processar_batch_inner(
    eventos: list[dict],
    items: list[int],
    *,
    cert_path: str,
    cert_password: str,
    cnpj: str,
    ambiente: str,
    pfx_data: bytes,
    conn_db,
    conn_lo,
    conn_w,
    progress: Progress,
    log_prefix: str,
    is_retry_1089: bool = False,
) -> dict:
    pacote: list[esocial_client.EventoLote] = []
    pares = []
    falhas_prep: list[tuple[int, str, str]] = []

    for seq, (item_id, ev) in enumerate(zip(items, eventos), start=1):
        try:
            xml_antigo = _ler_xml_evento(conn_lo, ev)
            campos = extrair_s1210(xml_antigo)
        except Exception as e:  # noqa: BLE001
            falhas_prep.append((item_id, "extrair_xml", f"{type(e).__name__}: {e}"))
            continue

        nr_recibo_ativo = ev.get("nr_recibo") or campos.get("nr_recibo_atual")
        if not nr_recibo_ativo:
            falhas_prep.append((item_id, "sem_nr_recibo", f"CPF {ev['cpf']} sem nrRecibo"))
            continue

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

        try:
            xml_assinado = S1010XMLSigner.assinar(xml_novo, pfx_data, cert_password)
        except Exception as e:  # noqa: BLE001
            falhas_prep.append((item_id, "assinar_xml", f"{type(e).__name__}: {e}"))
            continue

        id_evt = esocial_client._extrair_id(xml_assinado)
        if not id_evt:
            falhas_prep.append((item_id, "extrair_id", "Id nao encontrado apos assinar"))
            continue

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

    for item_id, etapa, msg in falhas_prep:
        _atualizar_item(
            conn_db, item_id,
            status="erro_preparo",
            erro_codigo=etapa[:32],
            erro_mensagem=msg[:1000],
            duracao_ms=0,
        )

    if not pacote:
        progress.add(ok=0, erro=len(falhas_prep), pendente=0, tentados=len(falhas_prep))
        return {"ok": 0, "erro": len(falhas_prep), "pend": 0}

    t0 = time.time()
    print(f"{log_prefix}POST EnviarLote ({len(pacote)} eventos, amb={ambiente})", flush=True)
    try:
        res = esocial_client.enviar_lote(
            pacote,
            cert_path=cert_path,
            cert_password=cert_password,
            cnpj_empregador=cnpj,
            ambiente=ambiente,
            grupo=CFG_GRUPO,
        )
    except Exception as e:  # noqa: BLE001
        msg = f"{type(e).__name__}: {e}"
        for item_id, _ev, _eo in pares:
            _atualizar_item(conn_db, item_id, status="falha_rede",
                            erro_codigo="EXC", erro_mensagem=msg[:1000])
        progress.add(ok=0, erro=len(pares) + len(falhas_prep), pendente=0,
                     tentados=len(pares) + len(falhas_prep))
        return {"ok": 0, "erro": len(pares) + len(falhas_prep), "pend": 0}

    durac_envio_ms = int((time.time() - t0) * 1000)
    print(f"{log_prefix}resp http={res.get('http_status')} cd={res.get('codigo_resposta')} "
          f"proto={res.get('protocolo')}", flush=True)

    if not res.get("sucesso"):
        codigo = res.get("codigo_resposta") or "ERRO_LOTE"
        msg = res.get("descricao") or res.get("erro") or "lote rejeitado"
        ocs = res.get("ocorrencias") or []
        if ocs:
            msg += " | " + "; ".join(f"{o['codigo']}: {o['descricao']}" for o in ocs[:3])
        xml_ret_oid = None
        if res.get("response_xml"):
            try:
                xml_ret_oid = _gravar_xml_retorno(conn_w, res["response_xml"])
                conn_w.commit()
            except Exception:  # noqa: BLE001
                pass
        for item_id, _ev, _eo in pares:
            _atualizar_item(
                conn_db, item_id,
                status="erro_esocial" if res.get("http_status") == 200 else "falha_rede",
                erro_codigo=str(codigo)[:32],
                erro_mensagem=str(msg)[:1000],
                xml_retorno_oid=xml_ret_oid,
                duracao_ms=durac_envio_ms // max(len(pares), 1),
            )
        progress.add(ok=0, erro=len(pares) + len(falhas_prep), pendente=0,
                     tentados=len(pares) + len(falhas_prep))
        return {"ok": 0, "erro": len(pares) + len(falhas_prep), "pend": 0}

    protocolo = res["protocolo"]
    print(f"{log_prefix}polling proto={protocolo}", flush=True)

    pacote_ids = {eo.id_evento for eo in pacote}
    by_id, attempts = _polling_cumulativo(
        protocolo, pacote_ids,
        cert_path=cert_path, cert_password=cert_password, ambiente=ambiente,
        log_prefix=log_prefix,
    )

    sucesso_count = 0
    erro_count = 0
    pend_count = 0
    cpfs_1089: list[tuple[int, dict, esocial_client.EventoLote]] = []

    for item_id, ev, eo in pares:
        match = by_id.get(eo.id_evento)
        durac = durac_envio_ms // max(len(pares), 1)

        if not match:
            # SEM_RETORNO: anti-459. Marca pendente_consulta, NAO erro_esocial.
            _atualizar_item(
                conn_db, item_id,
                status="pendente_consulta",
                erro_codigo="SEM_RETORNO",
                erro_mensagem=f"sem retorno apos {attempts} tentativas (~{int(sum(POLL_WAITS[:attempts]))}s)",
                duracao_ms=durac,
            )
            pend_count += 1
            continue

        xml_ret_oid = None
        if match.get("xml_retorno"):
            try:
                xml_ret_oid = _gravar_xml_retorno(conn_w, match["xml_retorno"])
                conn_w.commit()
            except Exception:  # noqa: BLE001
                pass

        codigo = match.get("codigo")

        # 1089 = mesmo evento em 2 lotes simultaneos. Faz retry isolado uma vez.
        if codigo == "1089" and not is_retry_1089:
            cpfs_1089.append((item_id, ev, eo))
            continue

        if codigo == "201":
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
            msg_partes = [f"{codigo}: {match.get('descricao')}"]
            for oc in ocs[:5]:
                msg_partes.append(f"  - {oc['codigo']}: {oc['descricao']}")
            _atualizar_item(
                conn_db, item_id,
                status="erro_esocial",
                erro_codigo=str(codigo or "")[:32],
                erro_mensagem=" | ".join(msg_partes)[:1000],
                xml_retorno_oid=xml_ret_oid,
                duracao_ms=durac,
            )
            erro_count += 1

    # Retry concorrencia 1089
    if cpfs_1089:
        print(f"{log_prefix}1089 detectado em {len(cpfs_1089)} CPF(s), aguardando "
              f"{RETRY_1089_DELAY_S}s para retry...", flush=True)
        time.sleep(RETRY_1089_DELAY_S)
        sub_eventos = [ev for _, ev, _ in cpfs_1089]
        sub_items = [iid for iid, _, _ in cpfs_1089]
        # Re-resolve buscando o evento no eSocial via consulta direta NAO disponivel aqui;
        # entao reenvia mesmo (com novo Id por causa do timestamp seq). 1 unica tentativa.
        sub_res = _processar_batch_inner(
            sub_eventos, sub_items,
            cert_path=cert_path, cert_password=cert_password, cnpj=cnpj,
            ambiente=ambiente, pfx_data=pfx_data,
            conn_db=conn_db, conn_lo=conn_lo, conn_w=conn_w,
            progress=Progress(total=len(cpfs_1089)),  # progress isolado p/ nao duplicar
            log_prefix=log_prefix + "[retry1089] ",
            is_retry_1089=True,
        )
        sucesso_count += sub_res["ok"]
        erro_count += sub_res["erro"]
        pend_count += sub_res["pend"]

    progress.add(
        ok=sucesso_count,
        erro=erro_count + len(falhas_prep),
        pendente=pend_count,
        tentados=sucesso_count + erro_count + pend_count + len(falhas_prep),
    )
    return {"ok": sucesso_count, "erro": erro_count + len(falhas_prep), "pend": pend_count}


# ---------- Orquestracao paralela ----------
def rodar_paralelo(
    *,
    empresa_id: int,
    per_apur: str,
    limite: int,
    cert_path: str,
    cert_password: str,
    cnpj: str,
    ambiente: str,
    pular_ja_tentados: bool = False,
    workers: int = DEFAULT_WORKERS,
    batch_size: int = DEFAULT_BATCH,
    progress_every: int = DEFAULT_PROGRESS_EVERY,
) -> dict:
    if batch_size > 50:
        print(f"!! batch_size={batch_size} > 50 (limite hard eSocial), forcando 50")
        batch_size = 50
    if workers > 5:
        print(f"!! workers={workers} > 5 (limite seguro pool DB), forcando 5")
        workers = 5

    # 1) carregar eventos + criar timeline + items (via conexao admin)
    conn_admin = db.connect(empresa_id=empresa_id)
    try:
        eventos = _carregar_eventos_alvo(
            conn_admin, empresa_id, per_apur, limite,
            pular_ja_tentados=pular_ja_tentados,
        )
        if not eventos:
            return {"ok": False, "erro": "nenhum evento HEAD encontrado"}
        print(f"=> selecionados {len(eventos)} eventos S-1210 HEAD per_apur={per_apur}", flush=True)

        envio_id, mes_id = _criar_timeline_envio(conn_admin, empresa_id, per_apur, len(eventos))
        print(f"=> timeline_envio criado id={envio_id} (mes={mes_id})", flush=True)

        item_ids = _criar_items(conn_admin, envio_id, eventos)
        print(f"=> {len(item_ids)} items pendente", flush=True)
    finally:
        conn_admin.close()

    # 2) preparar batches
    batches: list[tuple[int, list[dict], list[int]]] = []
    for idx, i in enumerate(range(0, len(eventos), batch_size), start=1):
        batches.append((idx, eventos[i:i + batch_size], item_ids[i:i + batch_size]))
    print(f"=> {len(batches)} batches de ate {batch_size} CPFs, workers={workers}", flush=True)

    # 3) progresso compartilhado
    progress = Progress(total=len(eventos), every=progress_every, t0=time.time())

    # 4) carregar pfx 1x
    with open(cert_path, "rb") as fh:
        pfx_data = fh.read()

    # 5) executar em paralelo
    sucesso_total = 0
    erro_total = 0
    pend_total = 0
    with cf.ThreadPoolExecutor(max_workers=workers, thread_name_prefix="env-w") as ex:
        futs = {
            ex.submit(
                _processar_batch_paralelo,
                evs, ids,
                empresa_id=empresa_id,
                cert_path=cert_path, cert_password=cert_password, cnpj=cnpj,
                ambiente=ambiente, pfx_data=pfx_data,
                progress=progress, batch_idx=idx,
            ): idx
            for idx, evs, ids in batches
        }
        for fut in cf.as_completed(futs):
            idx = futs[fut]
            try:
                r = fut.result()
                sucesso_total += r["ok"]
                erro_total += r["erro"]
                pend_total += r["pend"]
            except Exception as e:  # noqa: BLE001
                print(f"!! batch {idx} EXCECAO: {type(e).__name__}: {e}", flush=True)
                erro_total += 1

    # 6) histograma + finalizar envio
    conn_admin = db.connect(empresa_id=empresa_id)
    try:
        histograma: dict[str, int] = {}
        with conn_admin.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as c:
            c.execute(
                "SELECT erro_codigo, COUNT(*) AS n FROM timeline_envio_item "
                "WHERE timeline_envio_id=%s AND erro_codigo IS NOT NULL "
                "GROUP BY erro_codigo ORDER BY n DESC",
                (envio_id,),
            )
            for r in c.fetchall():
                histograma[str(r["erro_codigo"])] = int(r["n"])

        _atualizar_envio(
            conn_admin, envio_id,
            status="concluido", sucesso=sucesso_total, erro=erro_total + pend_total,
            resumo_extra={
                "histograma_erros": histograma,
                "workers": workers,
                "batch_size": batch_size,
                "pendente_consulta": pend_total,
            },
        )
    finally:
        conn_admin.close()

    elapsed = time.time() - progress.t0
    vel_s = len(eventos) / elapsed if elapsed > 0 else 0
    vel_min = vel_s * 60
    print("\n=== RESUMO PARALELO ===")
    print(f"envio_id          : {envio_id}")
    print(f"sucesso           : {sucesso_total}")
    print(f"erro              : {erro_total}")
    print(f"pendente_consulta : {pend_total}  (rodar reconsulta antes de tratar como erro!)")
    print(f"elapsed           : {elapsed:.0f}s ({vel_s:.2f} CPF/s, {vel_min:.1f} CPF/min)")
    print(f"histograma erros  : {histograma}")
    return {
        "ok": True, "envio_id": envio_id,
        "sucesso": sucesso_total, "erro": erro_total, "pendente_consulta": pend_total,
        "histograma": histograma, "elapsed_s": elapsed,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--empresa-id", type=int, default=1)
    ap.add_argument("--per-apur", default="2025-08")
    ap.add_argument("--limite", type=int, default=500)
    ap.add_argument("--cert", required=True)
    ap.add_argument("--senha", required=True)
    ap.add_argument("--cnpj", required=True)
    ap.add_argument("--ambiente", default="producao", choices=["homologacao", "producao"])
    ap.add_argument("--pular-ja-tentados", action="store_true")
    ap.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    ap.add_argument("--batch", type=int, default=DEFAULT_BATCH)
    ap.add_argument("--progress-every", type=int, default=DEFAULT_PROGRESS_EVERY)
    args = ap.parse_args(argv)
    r = rodar_paralelo(
        empresa_id=args.empresa_id,
        per_apur=args.per_apur,
        limite=args.limite,
        cert_path=args.cert,
        cert_password=args.senha,
        cnpj=args.cnpj,
        ambiente=args.ambiente,
        pular_ja_tentados=args.pular_ja_tentados,
        workers=args.workers,
        batch_size=args.batch,
        progress_every=args.progress_every,
    )
    return 0 if r.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
