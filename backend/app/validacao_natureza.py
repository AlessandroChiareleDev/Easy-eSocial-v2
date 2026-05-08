"""F8.3 — Validacao de naturezas (porte de V1 natureza-validation-service.ts).

Algoritmo de matching:
  1. tokenize() — NFD + remove acentos + colapsa abreviacoes pontilhadas + filtra stopwords
  2. expandTokens() — expande siglas (DSR -> descanso/semanal/remunerado, VT -> transporte/vale, ...)
  3. score 3 pts por match exato, 1 pt por substring, +0.5 se natureza ativa (sem data_fim)
  4. 3 camadas de sugestao: humana (col_f), score, populares (mais usadas em status='OK')

Stage de correcoes vai pra correcoes_staging (status='pendente'). aplicar/ -> analise_natureza_certo.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any

from fastapi import APIRouter, Body, HTTPException, Path, Query, Request

from . import tenant


router = APIRouter(prefix="/api/natureza", tags=["natureza"])


STOPWORDS: set[str] = {
    "de", "do", "da", "dos", "das", "em", "no", "na", "nos", "nas",
    "por", "para", "com", "sem", "sob", "sobre", "entre", "ate",
    "ao", "aos", "a", "as", "um", "uma", "uns", "umas",
    "o", "os", "e", "ou", "que", "se", "nao",
    "mes", "anterior", "ref", "outros", "outras",
}

SIGLAS: dict[str, list[str]] = {
    "dsr": ["descanso", "semanal", "remunerado", "dsr"],
    "dif": ["diferenca"],
    "he":  ["hora", "extra", "extraordinaria"],
    "hs":  ["hora", "extra", "extraordinaria"],
    "cct": ["convencao", "coletiva"],
    "act": ["acordo", "coletivo"],
    "inss": ["previdencia", "social", "inss"],
    "fgts": ["fgts", "garantia"],
    "irrf": ["imposto", "renda", "irrf"],
    "vt":  ["transporte", "vale"],
    "va":  ["alimentacao", "vale"],
    "vr":  ["refeicao", "vale"],
    "pat": ["alimentacao", "pat"],
    "plr": ["lucros", "resultados", "participacao"],
    "ppr": ["lucros", "resultados", "participacao"],
    "desc": ["desconto"],
    "dev": ["devolucao"],
    "reemb": ["reembolso", "ressarcimento"],
    "grat": ["gratificacao"],
    "adic": ["adicional"],
    "adc": ["adicional"],
    "compl": ["complemento"],
    "contrib": ["contribuicao"],
    "sest": ["sest", "senat", "transporte"],
    "senat": ["sest", "senat", "transporte"],
}


_DOTTED_RE = re.compile(r"\b((?:[a-z]\.){2,})", re.IGNORECASE)
_NON_ALPHANUM_RE = re.compile(r"[^a-z0-9\s]")
_WS_RE = re.compile(r"\s+")
_SUGERIDA_RE = re.compile(r"sujer?id[ao]\s*-?\s*(\d{4})", re.IGNORECASE)
_4DIG_RE = re.compile(r"\b(\d{4})\b")


def _strip_accents(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", s)
        if unicodedata.category(c) != "Mn"
    )


def tokenize(text: str) -> list[str]:
    s = _strip_accents(text.lower())
    # colapsa "D.S.R." -> "DSR"
    s = _DOTTED_RE.sub(lambda m: m.group(0).replace(".", ""), s)
    s = _NON_ALPHANUM_RE.sub(" ", s).strip()
    return [t for t in _WS_RE.split(s) if len(t) >= 2 and t not in STOPWORDS]


def expand_tokens(tokens: list[str]) -> list[str]:
    out: dict[str, None] = {}
    for t in tokens:
        out[t] = None
        for syn in SIGLAS.get(t, []):
            out[syn] = None
    return list(out.keys())


def _extrair_codigos_col_f(col_f: str) -> list[str]:
    sugeridos: list[str] = []
    for m in _SUGERIDA_RE.finditer(col_f):
        sugeridos.append(m.group(1))
    outros: list[str] = []
    for m in _4DIG_RE.finditer(col_f):
        c = m.group(1)
        if c not in sugeridos:
            outros.append(c)
    seen: dict[str, None] = {}
    for c in sugeridos + outros:
        seen[c] = None
    return list(seen.keys())


def _cnpj_ativo(request: Request) -> str:
    cnpj = getattr(request.state, "cnpj_ativo", None)
    if not cnpj:
        cnpj = request.headers.get("X-Empresa-CNPJ", "").strip() or None
    if not cnpj:
        raise HTTPException(400, "header X-Empresa-CNPJ ausente")
    return cnpj


# ============================================================
# Endpoints
# ============================================================

@router.get("/rubricas-com-problemas")
def rubricas_com_problemas(
    request: Request,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    apenas_pendentes: bool = Query(default=True),
):
    cnpj = _cnpj_ativo(request)
    extra = "AND cs.id IS NULL" if apenas_pendentes else ""
    with tenant.empresa_conn(cnpj) as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT count(*) FROM analise_natureza a
                LEFT JOIN correcoes_staging cs
                       ON cs.analise_natureza_id = a.id AND cs.status = 'pendente'
                WHERE UPPER(TRIM(a.col_d)) = 'VERIFICAR' {extra}
                """
            )
            total = cur.fetchone()[0]
            cur.execute(
                f"""
                SELECT a.id, a.col_a as codigoevento, a.col_b as nome_evento,
                       a.col_c as natureza_atual, a.col_e as observacao,
                       a.col_f as sugestao_col_f,
                       cs.natureza_nova_codigo || '-' || cs.natureza_nova_nome as natureza_nova,
                       cs.criado_em as data_correcao,
                       cs.usuario_nome
                FROM analise_natureza a
                LEFT JOIN correcoes_staging cs
                       ON cs.analise_natureza_id = a.id AND cs.status = 'pendente'
                WHERE UPPER(TRIM(a.col_d)) = 'VERIFICAR' {extra}
                ORDER BY a.id
                LIMIT %s OFFSET %s
                """,
                (limit, offset),
            )
            cols = [d.name for d in cur.description]
            rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    for r in rows:
        m = re.match(r"^(\d+)", str(r.get("natureza_atual") or ""))
        r["natureza_codigo_atual"] = m.group(1) if m else ""
    return {"total": total, "limit": limit, "offset": offset, "data": rows}


@router.get("/buscar-similares")
def buscar_similares(
    request: Request,
    nome_evento: str = Query(..., min_length=1),
    codigo_evento: str | None = Query(default=None),
    top_n: int = Query(default=10, ge=1, le=50),
):
    cnpj = _cnpj_ativo(request)

    with tenant.empresa_conn(cnpj) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, codigo, nome, descricao, data_inicio, data_fim "
                "FROM naturezas_esocial ORDER BY codigo"
            )
            naturezas = cur.fetchall()
            naturezas_map: dict[str, tuple] = {row[1]: row for row in naturezas}

            # Camada 1: sugestao humana
            sugestao_humana: dict[str, Any] | None = None
            sugestao_texto: str | None = None
            usados: set[str] = set()
            if codigo_evento:
                cur.execute(
                    """
                    SELECT col_f FROM analise_natureza
                     WHERE col_a = %s AND UPPER(TRIM(col_d)) = 'VERIFICAR'
                       AND col_f IS NOT NULL
                       AND TRIM(col_f) <> '' AND TRIM(col_f) <> '-'
                     LIMIT 1
                    """,
                    (codigo_evento,),
                )
                row = cur.fetchone()
                if row and row[0]:
                    col_f = row[0]
                    sugestao_texto = col_f
                    codigos = _extrair_codigos_col_f(col_f)
                    melhor = None
                    for cod in codigos:
                        nat = naturezas_map.get(cod)
                        if not nat:
                            continue
                        if not nat[5]:  # data_fim NULL = ativa
                            melhor = nat
                            break
                        if melhor is None:
                            melhor = nat
                    if melhor:
                        sugestao_humana = {
                            "id": melhor[0], "codigo": melhor[1], "nome": melhor[2],
                            "descricao": melhor[3],
                            "data_inicio": melhor[4].isoformat() if melhor[4] else None,
                            "data_fim": melhor[5].isoformat() if melhor[5] else None,
                            "score": 100, "origem": "sugestao_humana",
                        }
                        usados.add(melhor[1])

            # Camada 2: score
            tokens_evento = expand_tokens(tokenize(nome_evento))
            scored: list[dict[str, Any]] = []
            for nat in naturezas:
                _id, codigo, nome, descricao, data_ini, data_fim = nat
                if codigo in usados:
                    continue
                tokens_nat = tokenize(f"{nome} {descricao or ''}")
                score = 0.0
                matched: set[str] = set()
                for t in tokens_evento:
                    for nt in tokens_nat:
                        if nt == t:
                            if t not in matched:
                                score += 3
                                matched.add(t)
                        elif nt in t or t in nt:
                            key = f"{t}~{nt}"
                            if key not in matched:
                                score += 1
                                matched.add(key)
                if not data_fim:
                    score += 0.5
                if score > 0.5:
                    scored.append({
                        "id": _id, "codigo": codigo, "nome": nome, "descricao": descricao,
                        "data_inicio": data_ini.isoformat() if data_ini else None,
                        "data_fim": data_fim.isoformat() if data_fim else None,
                        "score": score, "origem": "score",
                    })
            scored.sort(key=lambda x: x["score"], reverse=True)
            top_score = scored[:8]
            for s in top_score:
                usados.add(s["codigo"])

            # Camada 3: populares
            restantes = top_n - len(top_score) - (1 if sugestao_humana else 0)
            populares: list[dict[str, Any]] = []
            if restantes > 0:
                cur.execute(
                    """
                    SELECT SUBSTRING(col_c FROM '^(\\d+)') AS codigo, COUNT(*) AS freq
                      FROM analise_natureza
                     WHERE UPPER(TRIM(col_d)) = 'OK' AND col_c IS NOT NULL
                     GROUP BY SUBSTRING(col_c FROM '^(\\d+)')
                     ORDER BY freq DESC
                     LIMIT %s
                    """,
                    (restantes + len(usados),),
                )
                for prow in cur.fetchall():
                    codigo = prow[0]
                    if not codigo or codigo in usados:
                        continue
                    if len(populares) >= restantes:
                        break
                    nat = naturezas_map.get(codigo)
                    if not nat:
                        continue
                    populares.append({
                        "id": nat[0], "codigo": nat[1], "nome": nat[2], "descricao": nat[3],
                        "data_inicio": nat[4].isoformat() if nat[4] else None,
                        "data_fim": nat[5].isoformat() if nat[5] else None,
                        "score": 0, "origem": "popular",
                    })
                    usados.add(nat[1])

    return {
        "sugestao_humana": sugestao_humana,
        "sugestao_texto": sugestao_texto,
        "resultados": top_score + populares,
    }


@router.post("/{rubrica_id}/corrigir")
def corrigir_rubrica(
    request: Request,
    rubrica_id: int = Path(..., ge=1),
    payload: dict[str, Any] = Body(...),
):
    cnpj = _cnpj_ativo(request)
    cod_novo = str(payload.get("natureza_nova_codigo", "")).strip()
    nome_novo = str(payload.get("natureza_nova_nome", "")).strip()
    motivo = str(payload.get("motivo") or "")
    usuario = payload.get("usuario_nome") or "sistema"
    usuario_id = payload.get("usuario_id")
    if not cod_novo:
        raise HTTPException(400, "natureza_nova_codigo obrigatorio")

    with tenant.empresa_conn(cnpj) as conn:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT col_a, col_b, col_c FROM analise_natureza WHERE id = %s",
                    (rubrica_id,),
                )
                row = cur.fetchone()
                if not row:
                    raise HTTPException(404, "rubrica nao encontrada")
                codigoevento, nome_evento, natureza_anterior = row
                cur.execute(
                    """
                    INSERT INTO correcoes_staging
                       (analise_natureza_id, codigoevento, nome_evento, natureza_anterior,
                        natureza_nova_codigo, natureza_nova_nome, motivo,
                        usuario_id, usuario_nome, status)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'pendente')
                    ON CONFLICT (analise_natureza_id) DO UPDATE SET
                       natureza_nova_codigo = EXCLUDED.natureza_nova_codigo,
                       natureza_nova_nome   = EXCLUDED.natureza_nova_nome,
                       motivo               = EXCLUDED.motivo,
                       usuario_id           = EXCLUDED.usuario_id,
                       usuario_nome         = EXCLUDED.usuario_nome,
                       status               = 'pendente',
                       criado_em            = CURRENT_TIMESTAMP,
                       aplicado_em          = NULL
                    """,
                    (rubrica_id, codigoevento, nome_evento, natureza_anterior,
                     cod_novo, nome_novo, motivo, usuario_id, usuario),
                )
            conn.commit()
        except HTTPException:
            conn.rollback()
            raise
        except Exception as e:  # noqa: BLE001
            conn.rollback()
            raise HTTPException(500, f"falha: {e}")
    return {"ok": True}


@router.delete("/{rubrica_id}/correcao")
def desfazer_correcao(request: Request, rubrica_id: int = Path(..., ge=1)):
    cnpj = _cnpj_ativo(request)
    with tenant.empresa_conn(cnpj) as conn:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM correcoes_staging "
                    "WHERE analise_natureza_id = %s AND status = 'pendente'",
                    (rubrica_id,),
                )
                deleted = cur.rowcount
            conn.commit()
        except Exception as e:  # noqa: BLE001
            conn.rollback()
            raise HTTPException(500, f"falha: {e}")
    return {"ok": True, "deleted": deleted}


@router.get("/progresso")
def progresso(request: Request):
    cnpj = _cnpj_ativo(request)
    with tenant.empresa_conn(cnpj) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                  count(*) FILTER (WHERE UPPER(TRIM(a.col_d)) = 'VERIFICAR'),
                  count(*) FILTER (WHERE UPPER(TRIM(a.col_d)) = 'VERIFICAR' AND cs.id IS NOT NULL),
                  count(*) FILTER (WHERE UPPER(TRIM(a.col_d)) = 'VERIFICAR' AND cs.id IS NULL)
                FROM analise_natureza a
                LEFT JOIN correcoes_staging cs
                       ON cs.analise_natureza_id = a.id AND cs.status = 'pendente'
                """
            )
            total, corr, pend = cur.fetchone()
    pct = round((corr / total) * 100) if total else 0
    return {
        "total_verificar": total,
        "total_corrigidas": corr,
        "total_pendentes": pend,
        "percentual": pct,
    }


@router.get("/relatorio")
def relatorio_final(request: Request):
    cnpj = _cnpj_ativo(request)
    with tenant.empresa_conn(cnpj) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT cs.analise_natureza_id AS id, cs.codigoevento, cs.nome_evento,
                       cs.natureza_anterior,
                       CASE WHEN cs.natureza_nova_codigo = '0' THEN '(vazio)'
                            ELSE cs.natureza_nova_codigo || '-' || cs.natureza_nova_nome
                       END AS natureza_nova,
                       cs.usuario_nome, cs.criado_em AS data_correcao,
                       cs.motivo, cs.status
                  FROM correcoes_staging cs
                 ORDER BY cs.criado_em DESC
                """
            )
            cols = [d.name for d in cur.description]
            data = [dict(zip(cols, r)) for r in cur.fetchall()]
    return {"data": data}


@router.post("/aplicar")
def aplicar_correcoes(request: Request):
    cnpj = _cnpj_ativo(request)
    with tenant.empresa_conn(cnpj) as conn:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, analise_natureza_id, codigoevento, natureza_anterior,
                           natureza_nova_codigo, natureza_nova_nome, motivo, usuario_nome
                      FROM correcoes_staging WHERE status = 'pendente'
                    """
                )
                pendentes = cur.fetchall()
                aplicadas = 0
                for cs in pendentes:
                    (cs_id, anat_id, codevt, nat_ant,
                     cod_novo, nome_novo, motivo, usuario) = cs
                    natureza_full = "" if cod_novo == "0" else f"{cod_novo}-{nome_novo}"
                    cur.execute(
                        """
                        UPDATE analise_natureza_certo
                           SET col_c = %s,
                               natureza_anterior = %s,
                               natureza_nova = %s,
                               col_d = 'OK',
                               usuario_correcao = %s,
                               data_correcao = CURRENT_TIMESTAMP
                         WHERE id = %s
                        """,
                        (natureza_full, nat_ant, natureza_full, usuario, anat_id),
                    )
                    cur.execute(
                        """
                        INSERT INTO auditoria_naturezas
                          (analise_natureza_id, codigoevento, natureza_anterior,
                           natureza_nova, usuario, motivo)
                        VALUES (%s,%s,%s,%s,%s,%s)
                        """,
                        (anat_id, codevt, nat_ant, natureza_full, usuario, motivo or ""),
                    )
                    cur.execute(
                        "UPDATE correcoes_staging SET status='aplicada', "
                        "aplicado_em = CURRENT_TIMESTAMP WHERE id = %s",
                        (cs_id,),
                    )
                    aplicadas += 1
            conn.commit()
        except Exception as e:  # noqa: BLE001
            conn.rollback()
            raise HTTPException(500, f"falha: {e}")
    return {"ok": True, "aplicadas": aplicadas}


@router.get("/naturezas")
def listar_naturezas(request: Request):
    cnpj = _cnpj_ativo(request)
    with tenant.empresa_conn(cnpj) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, codigo, nome, descricao, data_inicio, data_fim "
                "FROM naturezas_esocial ORDER BY codigo"
            )
            cols = [d.name for d in cur.description]
            rows = []
            for r in cur.fetchall():
                d = dict(zip(cols, r))
                if d.get("data_inicio"):
                    d["data_inicio"] = d["data_inicio"].isoformat()
                if d.get("data_fim"):
                    d["data_fim"] = d["data_fim"].isoformat()
                rows.append(d)
    return {"data": rows}


@router.get("/naturezas/{codigo}")
def buscar_por_codigo(request: Request, codigo: str = Path(...)):
    cnpj = _cnpj_ativo(request)
    with tenant.empresa_conn(cnpj) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, codigo, nome, descricao, data_inicio, data_fim "
                "FROM naturezas_esocial WHERE codigo = %s",
                (codigo,),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(404, "natureza nao encontrada")
            cols = [d.name for d in cur.description]
            d = dict(zip(cols, row))
            if d.get("data_inicio"):
                d["data_inicio"] = d["data_inicio"].isoformat()
            if d.get("data_fim"):
                d["data_fim"] = d["data_fim"].isoformat()
    return {"data": d}
