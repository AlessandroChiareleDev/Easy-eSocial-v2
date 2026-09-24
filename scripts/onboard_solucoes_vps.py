from __future__ import annotations

import argparse
import os
import calendar
import hashlib
import json
import re
import sys
import time
import zipfile
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

import psycopg2
import psycopg2.extras

ROOT = Path(__file__).resolve().parents[1]
# Na VPS o backend em producao (com o .env certo) fica em /opt/easy-esocial/backend
BACKEND = Path(os.environ.get("EASY_BACKEND", str(ROOT / "backend")))
sys.path.insert(0, str(BACKEND))

from app import backfill_chain, config, db, storage, tenant  # noqa: E402
from app.esocial_parser import parse_xml_bytes  # noqa: E402
from app.explorador import _extrair_zip_sync  # noqa: E402


CNPJ = "09445502000109"
CNPJ_RAIZ = "09445502"
RAZAO_SOCIAL = "SOLUCOES"
SCHEMA = "solucoes"
# Convencao do tenant.py: API usa empresa_id=2 (roteia p/ schema solucoes),
# mas as linhas dentro do schema guardam empresa_id interno = 1.
EMPRESA_ID = 1
ROUTE_ID = 2
ANO_DEFAULT = 2025
ZIP_DIR = Path(os.environ.get("ZIP_DIR", str(ROOT / "relatorios")))


def log(msg: str) -> None:
    print(msg, flush=True)


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def connect_base():
    if config.SISTEMA_DB_URL:
        return psycopg2.connect(config.SISTEMA_DB_URL)
    if config.SUPABASE_DB_CONFIG:
        return psycopg2.connect(**config.SUPABASE_DB_CONFIG)
    raise RuntimeError("Nenhuma DSN configurada no backend/.env")


def connect_schema(schema: str):
    conn = connect_base()
    with conn.cursor() as cur:
        cur.execute(f'SET search_path TO "{schema}", public')
    conn.commit()
    return conn


def quote_ident(name: str) -> str:
    if not re.fullmatch(r"[a-z][a-z0-9_]{0,62}", name):
        raise ValueError(f"schema invalido: {name}")
    return name


def current_empresa_version(cur, schema: str) -> str | None:
    cur.execute(
        "SELECT 1 FROM information_schema.tables WHERE table_schema=%s AND table_name='schema_meta'",
        (schema,),
    )
    if cur.fetchone() is None:
        return None
    cur.execute(
        f"""
        SELECT version
          FROM {schema}.schema_meta
         WHERE target='empresa'
         ORDER BY split_part(version, '.', 1)::int DESC,
                  split_part(version, '.', 2)::int DESC,
                  split_part(version, '.', 3)::int DESC
         LIMIT 1
        """
    )
    row = cur.fetchone()
    return row[0] if row else None


def version_tuple(version: str | None) -> tuple[int, int, int]:
    if not version:
        return (0, 0, 0)
    parts = [int(p) for p in re.findall(r"\d+", version)[:3]]
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts[:3])


def reset_v1_clone() -> None:
    """Se 'solucoes' for o clone V1 feito no setup (sem empresa_zips_brutos), recria do zero."""
    conn = connect_base()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM information_schema.tables WHERE table_schema=%s AND table_name='empresa_zips_brutos'", (SCHEMA,))
            tem_v2 = cur.fetchone() is not None
            cur.execute("SELECT 1 FROM pg_namespace WHERE nspname=%s", (SCHEMA,))
            existe = cur.fetchone() is not None
            if existe and not tem_v2:
                log(f"[RESET] schema {SCHEMA} e clone V1 sem dados de ZIP; recriando no formato V2")
                cur.execute(f'DROP SCHEMA "{SCHEMA}" CASCADE')
        conn.commit()
    finally:
        conn.close()


def apply_empresa_migration(version: str) -> None:
    schema = quote_ident(SCHEMA)
    sql_path = BACKEND / "migrations" / "empresa" / f"empresa_v{version}.sql"
    if not sql_path.exists():
        raise FileNotFoundError(sql_path)
    conn = connect_base()
    try:
        with conn.cursor() as cur:
            cur.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema}"')
            conn.commit()
            current = current_empresa_version(cur, schema)
            if version_tuple(current) >= version_tuple(version):
                log(f"[MIGRATION] empresa atual={current} cobre v{version} em schema={schema}")
                return
            sql = sql_path.read_text(encoding="utf-8").replace("public.", f"{schema}.")
            log(f"[MIGRATION] aplicando empresa v{version} em schema={schema}")
            cur.execute(sql)
            conn.commit()
            log(f"[MIGRATION] ok empresa v{version}")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def ensure_extra_columns() -> None:
    conn = connect_schema(SCHEMA)
    try:
        with conn.cursor() as cur:
            cur.execute("ALTER TABLE explorador_eventos ADD COLUMN IF NOT EXISTS xml_bytes BYTEA")
            cur.execute("ALTER TABLE empresa_zips_brutos ADD COLUMN IF NOT EXISTS extracao_progresso JSONB")
        conn.commit()
    finally:
        conn.close()


def provision_sistema() -> list[dict[str, Any]]:
    conn = connect_base()
    users: list[dict[str, Any]] = []
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            flags = {
                "tem_xml_completo": True,
                "origem_dados": "zips_relatorios_repo",
                "empresa_id_legado": ROUTE_ID,
                "origem_zips": "relatorios/relatório XML final soluções",
            }
            cur.execute(
                """
                INSERT INTO sistema.empresas_routing
                    (cnpj, razao_social, schema_name, schema_version, flags, ativo)
                VALUES (%s, %s, %s, '1.1.0', %s::jsonb, TRUE)
                ON CONFLICT (cnpj) DO UPDATE
                   SET razao_social=EXCLUDED.razao_social,
                       schema_name=EXCLUDED.schema_name,
                       schema_version='1.1.0',
                       flags=EXCLUDED.flags,
                       ativo=TRUE,
                       atualizado_em=NOW()
                """,
                (CNPJ, RAZAO_SOCIAL, SCHEMA, json.dumps(flags)),
            )
            cur.execute(
                """
                SELECT id, email, nome, super_admin
                  FROM sistema.users
                 WHERE ativo IS TRUE
                   AND (
                        super_admin IS TRUE
                        OR lower(email) IN ('ana', 'xandeadmin')
                        OR email ILIKE '%%ana%%'
                        OR nome ILIKE '%%ana%%'
                   )
                 ORDER BY super_admin DESC, lower(email)
                """
            )
            users = [dict(r) for r in cur.fetchall()]
            if not users:
                raise RuntimeError("Nenhum usuario ativo encontrado para vincular SOLUCOES")
            for user in users:
                papel = "admin" if user.get("super_admin") else "operador"
                cur.execute(
                    """
                    INSERT INTO sistema.user_empresas (user_id, cnpj, papel)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (user_id, cnpj) DO UPDATE SET papel=EXCLUDED.papel
                    """,
                    (user["id"], CNPJ, papel),
                )
        conn.commit()
        log(f"[SISTEMA] SOLUCOES cadastrada e vinculada para {len(users)} usuario(s)")
        return users
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def set_sequence(cur, table: str, column: str = "id") -> None:
    cur.execute("SELECT pg_get_serial_sequence(%s, %s)", (table, column))
    row = cur.fetchone()
    seq_name = next(iter(row.values())) if isinstance(row, dict) else (row[0] if row else None)
    if seq_name:
        cur.execute(
            f"SELECT setval(%s, GREATEST((SELECT COALESCE(MAX({column}), 1) FROM {table}), 1), true)",
            (seq_name,),
        )


def seed_empresa_schema() -> None:
    conn = connect_schema(SCHEMA)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("DELETE FROM master_empresas WHERE cnpj=%s AND id<>%s", (CNPJ, EMPRESA_ID))
            cur.execute(
                """
                INSERT INTO master_empresas (id, nome, cnpj, db_name, ativo, tipo_estado)
                VALUES (%s, %s, %s, %s, TRUE, 'estado_1')
                ON CONFLICT (id) DO UPDATE
                   SET nome=EXCLUDED.nome,
                       cnpj=EXCLUDED.cnpj,
                       db_name=EXCLUDED.db_name,
                       ativo=TRUE,
                       tipo_estado='estado_1'
                """,
                (EMPRESA_ID, RAZAO_SOCIAL, CNPJ, SCHEMA),
            )
            set_sequence(cur, "master_empresas")

            cur.execute("DELETE FROM config_esocial WHERE cnpj=%s", (CNPJ,))
            cur.execute(
                "INSERT INTO config_esocial (cnpj, ini_valid_padrao, auto_detected) VALUES (%s, %s, TRUE)",
                (CNPJ, "2025-01"),
            )
        conn.commit()
        log("[EMPRESA] master_empresas/config_esocial ok sem certificado")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def zip_files() -> list[Path]:
    if not ZIP_DIR.exists():
        raise FileNotFoundError(ZIP_DIR)
    files = sorted(ZIP_DIR.glob("*.zip"))
    if not files:
        raise RuntimeError(f"Nenhum ZIP encontrado em {ZIP_DIR}")
    return files


def infer_period(path: Path) -> tuple[date, date, str | None, str | None]:
    # Nomes tipo "SOLUCOES_2025-02(01-14).zip" ou "... - 2025-02.zip"
    m = re.search(r"(\d{4})-(\d{2})", path.name)
    ano = int(m.group(1)) if m else ANO_DEFAULT
    mes = int(m.group(2)) if m else 1
    ultimo = calendar.monthrange(ano, mes)[1]
    d = re.search(r"\((\d{2})-(\d{2})\)", path.name)
    d1 = min(max(int(d.group(1)), 1), ultimo) if d else 1
    d2 = min(max(int(d.group(2)), 1), ultimo) if d else ultimo
    per = f"{ano:04d}-{mes:02d}" if m else None
    return date(ano, mes, d1), date(ano, mes, d2), per, None


def upload_zip_if_needed(path: Path, dt_ini: date, dt_fim: date) -> tuple[int, bool]:
    with path.open("rb") as fh:
        conn = db.connect(empresa_id=ROUTE_ID)
        oid = None
        try:
            oid, total_bytes, sha256_hex = storage.write_lo_streaming(conn, fh)
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT id, extracao_status FROM empresa_zips_brutos WHERE empresa_id=%s AND sha256=%s",
                    (EMPRESA_ID, sha256_hex),
                )
                existing = cur.fetchone()
                if existing:
                    cur.execute(
                        "UPDATE empresa_zips_brutos SET dt_ini=%s, dt_fim=%s WHERE id=%s",
                        (dt_ini, dt_fim, existing["id"]),
                    )
                    storage.unlink_lo(conn, oid)
                    conn.commit()
                    log(f"[ZIP] ja existia zip_id={existing['id']} status={existing['extracao_status']} file={path.name}")
                    return int(existing["id"]), False
                cur.execute(
                    """
                    INSERT INTO empresa_zips_brutos
                        (empresa_id, dt_ini, dt_fim, sequencial_esocial,
                         nome_arquivo_original, sha256, tamanho_bytes, conteudo_oid,
                         extracao_status, extracao_progresso)
                    VALUES (%s, %s, %s, NULL, %s, %s, %s, %s, 'pendente', %s)
                    RETURNING id
                    """,
                    (
                        EMPRESA_ID,
                        dt_ini,
                        dt_fim,
                        path.name,
                        sha256_hex,
                        total_bytes,
                        oid,
                        json.dumps({"etapa": "upload concluido", "processados": 0, "total": 0}),
                    ),
                )
                zip_id = int(cur.fetchone()["id"])
            conn.commit()
            log(f"[ZIP] upload ok zip_id={zip_id} bytes={total_bytes} file={path.name}")
            return zip_id, True
        except Exception:
            conn.rollback()
            if oid:
                try:
                    storage.unlink_lo(conn, oid)
                    conn.commit()
                except Exception:
                    conn.rollback()
            raise
        finally:
            conn.close()


def extract_zip_if_needed(zip_id: int, force: bool = False) -> dict[str, Any]:
    with db.cursor(empresa_id=ROUTE_ID) as cur:
        cur.execute(
            "SELECT extracao_status, total_xmls, nome_arquivo_original FROM empresa_zips_brutos WHERE id=%s",
            (zip_id,),
        )
        row = cur.fetchone()
    if not row:
        raise RuntimeError(f"zip_id={zip_id} nao encontrado")
    if row["extracao_status"] == "ok" and not force:
        log(f"[EXTRACT] skip ok zip_id={zip_id} file={row['nome_arquivo_original']} total={row['total_xmls']}")
        return {"ok": True, "zip_id": zip_id, "skipped": True, "total_xmls": row["total_xmls"] or 0}
    log(f"[EXTRACT] iniciando zip_id={zip_id} file={row['nome_arquivo_original']}")
    started = time.time()
    res = _extrair_zip_sync(zip_id, somente_s5002=False, empresa_id=ROUTE_ID)
    log(
        f"[EXTRACT] ok zip_id={zip_id} total={res.get('total_xmls')} "
        f"indexados={res.get('indexados')} dup={res.get('duplicados_id_evento')} "
        f"falhas={res.get('falhas')} em {time.time() - started:.1f}s"
    )
    return res


def sync_fechamento_status() -> None:
    conn = connect_schema(SCHEMA)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS s1299_fechamento_status (
                  empresa_id    INT          NOT NULL,
                  per_apur      VARCHAR(7)   NOT NULL,
                  fechado       BOOLEAN      NOT NULL DEFAULT FALSE,
                  protocolo     VARCHAR(100),
                  nr_recibo     VARCHAR(100),
                  confirmado_em TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
                  origem        VARCHAR(40)  DEFAULT 'sync',
                  PRIMARY KEY (empresa_id, per_apur)
                )
                """
            )
            cur.execute(
                """
                SELECT DISTINCT ON (per_apur) per_apur, nr_recibo, dt_processamento
                  FROM explorador_eventos
                 WHERE tipo_evento='S-1299' AND cd_resposta='201'
                 ORDER BY per_apur, dt_processamento DESC NULLS LAST, id DESC
                """
            )
            map_1299 = {r["per_apur"]: dict(r) for r in cur.fetchall() if r["per_apur"]}
            cur.execute(
                """
                SELECT DISTINCT ON (per_apur) per_apur, nr_recibo, dt_processamento
                  FROM explorador_eventos
                 WHERE tipo_evento='S-1298' AND cd_resposta='201'
                 ORDER BY per_apur, dt_processamento DESC NULLS LAST, id DESC
                """
            )
            map_1298 = {r["per_apur"]: dict(r) for r in cur.fetchall() if r["per_apur"]}
            for per in sorted(set(map_1299) | set(map_1298)):
                r99 = map_1299.get(per)
                r98 = map_1298.get(per)
                if r99 and r98:
                    fechado = r99["dt_processamento"] >= r98["dt_processamento"]
                elif r99:
                    fechado = True
                else:
                    fechado = False
                nr_recibo = (r99 or r98 or {}).get("nr_recibo")
                cur.execute(
                    """
                    INSERT INTO s1299_fechamento_status
                        (empresa_id, per_apur, fechado, nr_recibo, origem, confirmado_em)
                    VALUES (%s, %s, %s, %s, 'sync', NOW())
                    ON CONFLICT (empresa_id, per_apur) DO UPDATE
                       SET fechado=EXCLUDED.fechado,
                           nr_recibo=EXCLUDED.nr_recibo,
                           origem='sync',
                           confirmado_em=NOW()
                    """,
                    (EMPRESA_ID, per, fechado, nr_recibo),
                )
        conn.commit()
        log("[FECHAMENTO] cache S-1299/S-1298 sincronizado")
    finally:
        conn.close()


def validate_final() -> dict[str, Any]:
    conn = connect_schema(SCHEMA)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT tipo_evento, per_apur, COUNT(*) AS linhas, COUNT(DISTINCT cpf) AS cpfs
                  FROM explorador_eventos
                 GROUP BY tipo_evento, per_apur
                 ORDER BY per_apur, tipo_evento
                """
            )
            counts = [dict(r) for r in cur.fetchall()]
            cur.execute("SELECT COUNT(*) AS n FROM empresa_zips_brutos WHERE empresa_id=%s", (EMPRESA_ID,))
            zips = int(cur.fetchone()["n"])
            cur.execute("SELECT COUNT(*) AS n FROM explorador_eventos")
            eventos = int(cur.fetchone()["n"])
            cur.execute("SELECT COUNT(*) AS n FROM timeline_mes WHERE empresa_id=%s", (EMPRESA_ID,))
            timeline_mes = int(cur.fetchone()["n"])
            cur.execute(
                "SELECT COUNT(*) AS n FROM timeline_envio te JOIN timeline_mes tm ON tm.id=te.timeline_mes_id WHERE tm.empresa_id=%s",
                (EMPRESA_ID,),
            )
            timeline_envio = int(cur.fetchone()["n"])
            cur.execute(
                """
                SELECT per_apur, COUNT(DISTINCT cpf) AS cpfs_head
                  FROM explorador_eventos
                 WHERE tipo_evento='S-1210' AND retificado_por_id IS NULL
                 GROUP BY per_apur ORDER BY per_apur
                """
            )
            s1210_heads = [dict(r) for r in cur.fetchall()]
            cur.execute(
                """
                SELECT substring(pg.dt_pgto from 1 for 7) AS dtpgto_mes,
                       COUNT(DISTINCT e.id) AS eventos_s1210,
                       COUNT(DISTINCT e.cpf) AS cpfs,
                       COUNT(*) AS tags_dtpgto
                  FROM explorador_eventos e
                  CROSS JOIN LATERAL jsonb_array_elements(COALESCE(e.dados_json->'pagamentos', '[]'::jsonb)) AS p(info)
                                    CROSS JOIN LATERAL (SELECT COALESCE(p.info->>'dtPgto', p.info->>'dt_pgto') AS dt_pgto) AS pg
                 WHERE e.tipo_evento='S-1210'
                   AND pg.dt_pgto IS NOT NULL
                 GROUP BY substring(pg.dt_pgto from 1 for 7)
                 ORDER BY dtpgto_mes
                """
            )
            s1210_dtpgto = [dict(r) for r in cur.fetchall()]
            cur.execute(
                """
                SELECT COUNT(*) AS n
                  FROM explorador_eventos e
                 WHERE e.tipo_evento='S-1210'
                   AND NOT EXISTS (
                       SELECT 1
                         FROM jsonb_array_elements(COALESCE(e.dados_json->'pagamentos', '[]'::jsonb)) AS p(info)
                                                WHERE p.info ? 'dtPgto' OR p.info ? 'dt_pgto'
                   )
                """
            )
            s1210_sem_dtpgto = int(cur.fetchone()["n"])
        meses_dtpgto_2025 = {
            r["dtpgto_mes"] for r in s1210_dtpgto if str(r.get("dtpgto_mes") or "").startswith("2025-")
        }
        expected_2025 = {f"2025-{m:02d}" for m in range(1, 13)}
        return {
            "empresa": {"cnpj": CNPJ, "cnpj_raiz": CNPJ_RAIZ, "razao_social": RAZAO_SOCIAL, "schema": SCHEMA, "empresa_id": EMPRESA_ID},
            "zips": zips,
            "eventos": eventos,
            "timeline_mes": timeline_mes,
            "timeline_envio": timeline_envio,
            "s1210_heads_per_apur": s1210_heads,
            "s1210_por_dtpgto": s1210_dtpgto,
            "s1210_sem_dtpgto": s1210_sem_dtpgto,
            "s1210_dtpgto_2025_faltando": sorted(expected_2025 - meses_dtpgto_2025),
            "counts": counts,
        }
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-import", action="store_true")
    parser.add_argument("--force-extract", action="store_true")
    args = parser.parse_args()

    if getattr(tenant, "SOLUCOES_ID", None) != ROUTE_ID or tenant.internal_empresa_id(ROUTE_ID) != EMPRESA_ID:
        raise RuntimeError("tenant.py nao bate com SOLUCOES_ID=2 / interno=1")

    files = zip_files()
    log(f"[INPUT] zip_dir={ZIP_DIR}")
    log(f"[INPUT] {len(files)} ZIPs encontrados")

    reset_v1_clone()
    apply_empresa_migration("1.0.0")
    apply_empresa_migration("1.1.0")
    ensure_extra_columns()
    provision_sistema()
    seed_empresa_schema()

    zip_ids: list[int] = []
    if not args.skip_import:
        for index, path in enumerate(files, start=1):
            dt_ini, dt_fim, detected_per, detected_dtpgto = infer_period(path)
            log(
                f"[ZIP {index:02d}/{len(files):02d}] {path.name} periodo={dt_ini}..{dt_fim} "
                f"per_detectado={detected_per or '?'} dtpgto_detectado={detected_dtpgto or '?'}"
            )
            zip_id, _inserted = upload_zip_if_needed(path, dt_ini, dt_fim)
            zip_ids.append(zip_id)
            extract_zip_if_needed(zip_id, force=args.force_extract)

        conn = db.connect(empresa_id=ROUTE_ID)
        try:
            backfill_res = backfill_chain.backfill_empresa(conn, EMPRESA_ID)
            log(f"[BACKFILL] {backfill_res}")
        finally:
            conn.close()
        sync_fechamento_status()

    final = validate_final()
    out_path = Path(os.environ.get("OUT_JSON", str(ROOT / "docs" / "SOLUCOES_ONBOARDING_VPS.json")))
    out_path.write_text(json.dumps(final, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    log(
        f"[VALIDATE] zips={final['zips']} eventos={final['eventos']} "
        f"timeline_mes={final['timeline_mes']} timeline_envio={final['timeline_envio']} "
        f"sem_dtpgto={final['s1210_sem_dtpgto']} faltando_dtpgto={final['s1210_dtpgto_2025_faltando']}"
    )
    log(f"[VALIDATE] auditoria={out_path}")
    log("[DONE] SOLUCOES importada dos ZIPs sem chamadas ao eSocial")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())