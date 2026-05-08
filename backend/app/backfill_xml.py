"""Backfill: cria 1 Large Object por evento em explorador_eventos.

Lê os ZIPs já armazenados em empresa_zips_brutos, abre on-the-fly e, para
cada evento sem xml_oid, escreve os bytes do XML como novo LO e atualiza a
linha em explorador_eventos com (xml_oid, xml_size_bytes, xml_sha256).

Idempotente: re-rodar pula eventos que já têm xml_oid.

Uso:
    python -m app.backfill_xml [--zip-id N] [--limite N]
"""
from __future__ import annotations

import argparse
import hashlib
import sys
import zipfile
from typing import Iterable

import psycopg2.extras

from . import db, storage


def _eventos_pendentes(conn, zip_id: int) -> list[dict]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as c:
        c.execute(
            """
            SELECT id, xml_entry_name
              FROM explorador_eventos
             WHERE zip_id=%s AND xml_oid IS NULL
               AND xml_entry_name IS NOT NULL
             ORDER BY id ASC
            """,
            (zip_id,),
        )
        return list(c.fetchall())


def _zips_com_pendentes(conn, limite: int | None = None) -> list[dict]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as c:
        sql = """
            SELECT z.id, z.empresa_id, z.conteudo_oid, z.tamanho_bytes,
                   z.nome_arquivo_original,
                   COUNT(e.id) AS pendentes
              FROM empresa_zips_brutos z
              JOIN explorador_eventos e ON e.zip_id = z.id
             WHERE z.extracao_status='ok'
               AND e.xml_oid IS NULL
               AND e.xml_entry_name IS NOT NULL
             GROUP BY z.id
             ORDER BY z.id ASC
        """
        if limite:
            sql += f" LIMIT {int(limite)}"
        c.execute(sql)
        return list(c.fetchall())


def _grava_xml_em_lo(conn_lo, data: bytes) -> tuple[int, int, str]:
    """Cria novo LO e devolve (oid, size, sha256)."""
    sha = hashlib.sha256(data).hexdigest()
    lo = conn_lo.lobject(0, mode="wb")
    oid = lo.oid
    try:
        lo.write(data)
    finally:
        lo.close()
    return oid, len(data), sha


def backfill_zip(zip_id: int, *, conn_db=None, conn_lo=None) -> dict:
    """Faz backfill de todos eventos de um zip. Retorna métricas.

    Usa 3 conexões:
      - conn_db: INSERTs/UPDATEs de metadados (commits livres);
      - conn_lo: mantém aberto o LO do ZIP (transação intocada até o fim);
      - conn_w:  escreve novos LOs (1 por evento) — pode comitar em lotes
                 sem invalidar o reader do zip.
    """
    own_db = conn_db is None
    own_lo = conn_lo is None
    conn_db = conn_db or db.connect()
    conn_lo = conn_lo or db.connect()
    conn_w = db.connect()
    try:
        with conn_db.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as c:
            c.execute(
                "SELECT id, conteudo_oid, tamanho_bytes, nome_arquivo_original "
                "FROM empresa_zips_brutos WHERE id=%s",
                (zip_id,),
            )
            zrow = c.fetchone()
        if not zrow:
            return {"ok": False, "erro": "zip não encontrado", "zip_id": zip_id}

        pendentes = _eventos_pendentes(conn_db, zip_id)
        if not pendentes:
            return {"ok": True, "zip_id": zip_id, "processados": 0, "ja_estavam_ok": True}

        oid = int(zrow["conteudo_oid"])
        size = int(zrow["tamanho_bytes"])

        processados = 0
        falhas = 0
        bytes_total = 0

        reader = storage.LargeObjectReader(conn_lo, oid, size)
        try:
            with zipfile.ZipFile(reader, mode="r") as zf:
                # mapa rápido nome -> bytes (lazy via zf.open)
                for ev in pendentes:
                    name = ev["xml_entry_name"]
                    try:
                        with zf.open(name) as fh:
                            data = fh.read()
                    except KeyError:
                        falhas += 1
                        continue
                    except Exception:  # noqa: BLE001
                        falhas += 1
                        continue
                    try:
                        x_oid, x_size, x_sha = _grava_xml_em_lo(conn_w, data)
                        with conn_db.cursor() as up:
                            up.execute(
                                "UPDATE explorador_eventos "
                                "SET xml_oid=%s, xml_size_bytes=%s, xml_sha256=%s "
                                "WHERE id=%s AND xml_oid IS NULL",
                                (x_oid, x_size, x_sha, ev["id"]),
                            )
                        # commit em lotes pra não inflar transações
                        if processados % 200 == 0:
                            conn_db.commit()
                            conn_w.commit()  # persiste LOs novos sem mexer em conn_lo
                        processados += 1
                        bytes_total += x_size
                    except Exception as e:  # noqa: BLE001
                        falhas += 1
                        conn_db.rollback()
                        conn_w.rollback()
                        print(f"[WARN] falha gravando xml_oid evento={ev['id']}: {e}")
                conn_db.commit()
                conn_w.commit()
        finally:
            reader.close()

        return {
            "ok": True,
            "zip_id": zip_id,
            "processados": processados,
            "falhas": falhas,
            "bytes_total": bytes_total,
        }
    finally:
        try:
            conn_w.close()
        except Exception:  # noqa: BLE001
            pass
        if own_lo:
            try:
                conn_lo.close()
            except Exception:  # noqa: BLE001
                pass
        if own_db:
            try:
                conn_db.close()
            except Exception:  # noqa: BLE001
                pass


def backfill_todos(*, limite_zips: int | None = None) -> dict:
    conn_db = db.connect()
    try:
        zips = _zips_com_pendentes(conn_db, limite_zips)
    finally:
        conn_db.close()
    out = {"ok": True, "zips": [], "total_processados": 0, "total_falhas": 0}
    for z in zips:
        print(
            f"-> zip {z['id']} ({z['nome_arquivo_original']}): "
            f"{z['pendentes']} pendentes"
        )
        r = backfill_zip(int(z["id"]))
        out["zips"].append(r)
        out["total_processados"] += int(r.get("processados", 0))
        out["total_falhas"] += int(r.get("falhas", 0))
        print(f"   OK processados={r.get('processados')} falhas={r.get('falhas')}")
    return out


def main(argv: Iterable[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--zip-id", type=int, default=None)
    ap.add_argument("--limite", type=int, default=None,
                    help="limite de zips quando rodando em massa")
    args = ap.parse_args(list(argv) if argv is not None else None)

    if args.zip_id is not None:
        r = backfill_zip(args.zip_id)
    else:
        r = backfill_todos(limite_zips=args.limite)
    print(r)
    return 0 if r.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
