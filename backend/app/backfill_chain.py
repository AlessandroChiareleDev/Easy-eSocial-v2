"""Backfill da timeline (Chain Walk v2).

Para cada (empresa_id, per_apur) com eventos S-1210:
  1) cria timeline_mes (UPSERT)
  2) cria timeline_envio sequencia=0 tipo='zip_inicial'
  3) marca explorador_eventos.origem_envio_id
  4) atualiza head_envio_id
  5) detecta cadeias internas via referenciado_recibo

Idempotente: se já existir bolinha v0 para o mês, só preenche o que faltar.
"""
from __future__ import annotations

import sys
from typing import Any

import psycopg2.extras

from . import db


def backfill_empresa(conn, empresa_id: int) -> dict[str, Any]:
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # 1) Lista (empresa, per_apur) distintos via zip
    cur.execute(
        """
        SELECT z.empresa_id, e.per_apur, COUNT(*) AS n
          FROM explorador_eventos e
          JOIN empresa_zips_brutos z ON z.id = e.zip_id
         WHERE e.tipo_evento = 'S-1210'
           AND z.empresa_id = %s
           AND e.per_apur IS NOT NULL
         GROUP BY z.empresa_id, e.per_apur
         ORDER BY e.per_apur
        """,
        (empresa_id,),
    )
    grupos = cur.fetchall()
    if not grupos:
        return {"empresa_id": empresa_id, "meses": 0, "msg": "sem S-1210"}

    meses_processados = 0
    cadeias_conectadas_total = 0

    for g in grupos:
        per_apur = g["per_apur"]

        # 2) UPSERT timeline_mes
        cur.execute(
            """
            INSERT INTO timeline_mes (empresa_id, per_apur)
            VALUES (%s, %s)
            ON CONFLICT (empresa_id, per_apur) DO UPDATE
              SET per_apur = EXCLUDED.per_apur
            RETURNING id, head_envio_id
            """,
            (empresa_id, per_apur),
        )
        tm = cur.fetchone()
        timeline_mes_id = tm["id"]

        # 3) Verifica se já existe bolinha sequencia=0
        cur.execute(
            "SELECT id FROM timeline_envio WHERE timeline_mes_id=%s AND sequencia=0",
            (timeline_mes_id,),
        )
        row = cur.fetchone()
        if row:
            envio_id = row["id"]
        else:
            # contadores: pega total S-1210 do mês para essa empresa
            cur.execute(
                """
                SELECT COUNT(*) AS n
                  FROM explorador_eventos e
                  JOIN empresa_zips_brutos z ON z.id = e.zip_id
                 WHERE e.tipo_evento='S-1210'
                   AND e.per_apur=%s
                   AND z.empresa_id=%s
                """,
                (per_apur, empresa_id),
            )
            total = cur.fetchone()["n"]
            cur.execute(
                """
                INSERT INTO timeline_envio
                  (timeline_mes_id, sequencia, tipo, status,
                   total_tentados, total_sucesso, total_erro, finalizado_em)
                VALUES (%s, 0, 'zip_inicial', 'concluido', %s, %s, 0, NOW())
                RETURNING id
                """,
                (timeline_mes_id, total, total),
            )
            envio_id = cur.fetchone()["id"]

        # 4) marca origem_envio_id nos eventos S-1210 desse mês que ainda não têm
        cur.execute(
            """
            UPDATE explorador_eventos AS e
               SET origem_envio_id = %s
              FROM empresa_zips_brutos z
             WHERE z.id = e.zip_id
               AND z.empresa_id = %s
               AND e.tipo_evento = 'S-1210'
               AND e.per_apur = %s
               AND e.origem_envio_id IS NULL
            """,
            (envio_id, empresa_id, per_apur),
        )

        # 5) atualiza head_envio_id sempre para o ultimo envio (maior sequencia)
        cur.execute(
            """
            UPDATE timeline_mes m
               SET head_envio_id = sub.id
              FROM (
                SELECT te.id
                  FROM timeline_envio te
                 WHERE te.timeline_mes_id = %s
                 ORDER BY te.sequencia DESC
                 LIMIT 1
              ) sub
             WHERE m.id = %s
            """,
            (timeline_mes_id, timeline_mes_id),
        )

        # 6) cadeias internas — referenciado_recibo aponta para outra versão do mesmo CPF
        cur.execute(
            """
            UPDATE explorador_eventos AS antigo
               SET retificado_por_id = novo.id
              FROM explorador_eventos AS novo,
                   empresa_zips_brutos z_a, empresa_zips_brutos z_n
             WHERE z_a.id = antigo.zip_id
               AND z_n.id = novo.zip_id
               AND z_a.empresa_id = %s
               AND z_n.empresa_id = %s
               AND antigo.per_apur = %s
               AND novo.per_apur = %s
               AND antigo.tipo_evento = 'S-1210'
               AND novo.tipo_evento  = 'S-1210'
               AND antigo.cpf = novo.cpf
               AND novo.referenciado_recibo IS NOT NULL
               AND novo.referenciado_recibo = antigo.nr_recibo
               AND antigo.id <> novo.id
               AND antigo.retificado_por_id IS NULL
            """,
            (empresa_id, empresa_id, per_apur, per_apur),
        )
        cadeias_conectadas_total += cur.rowcount

        meses_processados += 1

    conn.commit()
    cur.close()
    return {
        "empresa_id": empresa_id,
        "meses": meses_processados,
        "cadeias_conectadas": cadeias_conectadas_total,
    }


def backfill_todas() -> list[dict[str, Any]]:
    conn = db.connect()
    out = []
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT id FROM master_empresas ORDER BY id")
        ids = [r["id"] for r in cur.fetchall()]
        cur.close()
        for emp_id in ids:
            out.append(backfill_empresa(conn, emp_id))
    finally:
        conn.close()
    return out


if __name__ == "__main__":
    res = backfill_todas()
    for r in res:
        print(r)
    sys.exit(0)
