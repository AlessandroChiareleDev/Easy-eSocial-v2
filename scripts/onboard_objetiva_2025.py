from __future__ import annotations

import argparse
import calendar
import hashlib
import json
import re
import sys
import time
import zipfile
from datetime import date
from pathlib import Path
from typing import Any

import psycopg2
import psycopg2.extras

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from app import backfill_chain, config, db, storage, tenant  # noqa: E402
from app.certificate_manager import CertificateManager  # noqa: E402
from app.esocial_parser import parse_xml_bytes  # noqa: E402
from app.explorador import _extrair_zip_sync  # noqa: E402


CNPJ = "10874523000110"
SCHEMA = "objetiva"
EMPRESA_ID = 3
ANO_DEFAULT = 2025
DOWNLOADS = Path.home() / "Downloads"
ZIP_DIR = DOWNLOADS / "mes a mes Objetiva zip"
SENHA_FILE = DOWNLOADS / "senha objetiva.txt"


def log(msg: str) -> None:
    print(msg, flush=True)


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


def migration_applied(cur, schema: str, version: str) -> bool:
    cur.execute(
        "SELECT 1 FROM information_schema.tables WHERE table_schema=%s AND table_name='schema_meta'",
        (schema,),
    )
    if cur.fetchone() is None:
        return False
    cur.execute(
        f"SELECT 1 FROM {schema}.schema_meta WHERE target='empresa' AND version=%s",
        (version,),
    )
    return cur.fetchone() is not None


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
            if migration_applied(cur, schema, version):
                log(f"[MIGRATION] empresa v{version} ja aplicada em schema={schema}")
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


def find_cert_files() -> list[Path]:
    files = sorted(DOWNLOADS.glob(f"*{CNPJ}*.pfx")) + sorted(DOWNLOADS.glob(f"*{CNPJ}*.p12"))
    if not files:
        raise FileNotFoundError(f"Certificado com CNPJ {CNPJ} nao encontrado em {DOWNLOADS}")
    return files


def choose_cert(files: list[Path]) -> Path:
    for path in files:
        if "senha" not in path.name.lower():
            return path
    return files[0]


def read_password(files: list[Path]) -> str:
    if SENHA_FILE.exists():
        text = SENHA_FILE.read_text(encoding="utf-8", errors="ignore").strip()
        if text:
            return text
    for path in files:
        match = re.search(r"senha\s+([^\s()]+)", path.stem, flags=re.IGNORECASE)
        if match:
            return match.group(1)
    raise RuntimeError("Senha do certificado nao encontrada: arquivo de senha vazio e nome do PFX sem marcador de senha")


def only_digits(value: str | None) -> str:
    return re.sub(r"\D", "", value or "")


def clean_razao(nome_titular: str | None) -> str:
    raw = (nome_titular or "OBJETIVA").strip()
    raw = re.sub(r"[:\s-]*\d{14}$", "", raw).strip()
    return raw or "OBJETIVA"


def load_certificate_info() -> tuple[Path, bytes, str, dict[str, Any], str]:
    cert_files = find_cert_files()
    cert_path = choose_cert(cert_files)
    password = read_password(cert_files)
    pfx_data = cert_path.read_bytes()
    info = CertificateManager.validate_pfx(pfx_data, password)
    cert_cnpj = only_digits(info.get("cnpj"))
    if cert_cnpj != CNPJ:
        raise RuntimeError(f"CNPJ do certificado ({cert_cnpj or 'vazio'}) difere do esperado {CNPJ}")
    razao = clean_razao(info.get("nome_titular"))
    log(f"[CERT] certificado valido para CNPJ {CNPJ}; titular detectado: {razao}")
    return cert_path, pfx_data, password, info, razao


def provision_sistema(razao: str) -> list[dict[str, Any]]:
    conn = connect_base()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
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
                (
                    CNPJ,
                    razao,
                    SCHEMA,
                    json.dumps({"tem_xml_completo": True, "origem_dados": "zips_usuario", "empresa_id_legado": EMPRESA_ID}),
                ),
            )
            cur.execute(
                """
                SELECT id, email, nome
                  FROM sistema.users
                 WHERE ativo IS TRUE
                   AND (email ILIKE '%%ana%%' OR nome ILIKE '%%ana%%')
                 ORDER BY email
                """
            )
            users = [dict(r) for r in cur.fetchall()]
            if not users:
                raise RuntimeError("Usuario Ana nao encontrado em sistema.users")
            for user in users:
                cur.execute(
                    """
                    INSERT INTO sistema.user_empresas (user_id, cnpj, papel)
                    VALUES (%s, %s, 'operador')
                    ON CONFLICT (user_id, cnpj) DO UPDATE SET papel='operador'
                    """,
                    (user["id"], CNPJ),
                )
        conn.commit()
        log("[SISTEMA] Objetiva cadastrada e vinculada para Ana")
        return users
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def set_sequence(cur, table: str, column: str = "id") -> None:
    cur.execute(
        "SELECT pg_get_serial_sequence(%s, %s)",
        (table, column),
    )
    row = cur.fetchone()
    seq_name = next(iter(row.values())) if isinstance(row, dict) else (row[0] if row else None)
    if seq_name:
        cur.execute(f"SELECT setval(%s, GREATEST((SELECT COALESCE(MAX({column}), 1) FROM {table}), 1), true)", (seq_name,))


def seed_empresa_schema(razao: str, pfx_data: bytes, password: str, cert_info: dict[str, Any]) -> None:
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
                (EMPRESA_ID, razao, CNPJ, SCHEMA),
            )
            set_sequence(cur, "master_empresas")

            cur.execute("DELETE FROM config_esocial WHERE cnpj=%s", (CNPJ,))
            cur.execute(
                "INSERT INTO config_esocial (cnpj, ini_valid_padrao, auto_detected) VALUES (%s, %s, TRUE)",
                (CNPJ, "2025-01"),
            )

            cert_path = CertificateManager.save_certificate(
                pfx_data,
                CNPJ,
                cert_info["numero_serie"],
            )
            senha_encrypted = CertificateManager.encrypt_password(password)
            cur.execute("UPDATE certificados_a1 SET ativo=FALSE WHERE ativo=TRUE")
            cur.execute(
                "DELETE FROM certificados_a1 WHERE cnpj=%s AND numero_serie=%s",
                (CNPJ, cert_info["numero_serie"]),
            )
            cur.execute(
                """
                INSERT INTO certificados_a1
                    (cnpj, titular, emissor, numero_serie, validade_fim,
                     arquivo_path, senha_encrypted, ativo, empresa_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, TRUE, %s)
                RETURNING id
                """,
                (
                    CNPJ,
                    cert_info.get("nome_titular"),
                    cert_info.get("emissor"),
                    cert_info.get("numero_serie"),
                    cert_info.get("validade"),
                    cert_path,
                    senha_encrypted,
                    EMPRESA_ID,
                ),
            )
            cert_id = cur.fetchone()["id"]
            cur.execute("DELETE FROM senha_certificado_salva")
            cur.execute(
                """
                INSERT INTO senha_certificado_salva (senha_encrypted, expires_at)
                VALUES (%s, NOW() + INTERVAL '720 hours')
                """,
                (senha_encrypted,),
            )
        conn.commit()
        log(f"[EMPRESA] master/config/certificado ok (cert_id={cert_id})")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def zip_files() -> list[Path]:
    if not ZIP_DIR.exists():
        raise FileNotFoundError(ZIP_DIR)
    files = sorted(ZIP_DIR.glob("*.zip"))
    if len(files) != 12:
        raise RuntimeError(f"Esperava 12 ZIPs em {ZIP_DIR}; encontrei {len(files)}")
    return files


def infer_period(path: Path) -> tuple[date, date, str | None]:
    name = path.name.lower()
    match = re.search(r"(\d{2})-(\d{2}).*?(\d{2})-(\d{2})", name)
    start_day = int(match.group(1)) if match else 1
    start_month = int(match.group(2)) if match else 1
    end_day = int(match.group(3)) if match else calendar.monthrange(ANO_DEFAULT, start_month)[1]
    end_month = int(match.group(4)) if match else start_month
    detected_per: str | None = None
    try:
        with zipfile.ZipFile(path, "r") as zf:
            for entry in zf.namelist():
                if not entry.lower().endswith(".xml"):
                    continue
                try:
                    evt = parse_xml_bytes(zf.read(entry))
                except Exception:
                    evt = None
                if evt and evt.per_apur and re.fullmatch(r"\d{4}-\d{2}", evt.per_apur):
                    detected_per = evt.per_apur
                    break
    except Exception:
        detected_per = None
    max_start = calendar.monthrange(ANO_DEFAULT, start_month)[1]
    max_end = calendar.monthrange(ANO_DEFAULT, end_month)[1]
    return (
        date(ANO_DEFAULT, start_month, min(start_day, max_start)),
        date(ANO_DEFAULT, end_month, min(end_day, max_end)),
        detected_per,
    )


def upload_zip_if_needed(path: Path, dt_ini: date, dt_fim: date) -> tuple[int, bool]:
    with path.open("rb") as fh:
        conn = db.connect(empresa_id=EMPRESA_ID)
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


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        while True:
            chunk = file.read(8 * 1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def repair_zip_dates() -> None:
    files = zip_files()
    conn = db.connect(empresa_id=EMPRESA_ID)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            for path in files:
                dt_ini, dt_fim, detected_per = infer_period(path)
                sha = file_sha256(path)
                cur.execute(
                    """
                    UPDATE empresa_zips_brutos
                       SET dt_ini=%s, dt_fim=%s
                     WHERE empresa_id=%s AND sha256=%s
                    RETURNING id, nome_arquivo_original
                    """,
                    (dt_ini, dt_fim, EMPRESA_ID, sha),
                )
                row = cur.fetchone()
                if row:
                    log(f"[REPAIR] zip_id={row['id']} {path.name} -> {dt_ini}..{dt_fim} per_detectado={detected_per or '?'}")
                else:
                    log(f"[REPAIR] nao encontrado no banco: {path.name}")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def extract_zip_if_needed(zip_id: int, force: bool = False) -> dict[str, Any]:
    with db.cursor(empresa_id=EMPRESA_ID) as cur:
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
    res = _extrair_zip_sync(zip_id, somente_s5002=False, empresa_id=EMPRESA_ID)
    log(f"[EXTRACT] ok zip_id={zip_id} total={res.get('total_xmls')} indexados={res.get('indexados')} dup={res.get('duplicados_id_evento')} falhas={res.get('falhas')} em {time.time() - started:.1f}s")
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
                 WHERE tipo_evento='S-1299' AND cd_resposta='201' AND per_apur LIKE '2025-%%'
                 ORDER BY per_apur, dt_processamento DESC NULLS LAST, id DESC
                """
            )
            map_1299 = {r["per_apur"]: dict(r) for r in cur.fetchall()}
            cur.execute(
                """
                SELECT DISTINCT ON (per_apur) per_apur, nr_recibo, dt_processamento
                  FROM explorador_eventos
                 WHERE tipo_evento='S-1298' AND cd_resposta='201' AND per_apur LIKE '2025-%%'
                 ORDER BY per_apur, dt_processamento DESC NULLS LAST, id DESC
                """
            )
            map_1298 = {r["per_apur"]: dict(r) for r in cur.fetchall()}
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
                 WHERE per_apur LIKE '2025-%%'
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
            cur.execute("SELECT COUNT(*) AS n FROM timeline_envio te JOIN timeline_mes tm ON tm.id=te.timeline_mes_id WHERE tm.empresa_id=%s", (EMPRESA_ID,))
            timeline_envio = int(cur.fetchone()["n"])
            cur.execute("SELECT COUNT(*) AS n FROM certificados_a1 WHERE ativo IS TRUE AND cnpj=%s", (CNPJ,))
            certs = int(cur.fetchone()["n"])
            cur.execute(
                """
                SELECT per_apur, COUNT(DISTINCT cpf) AS cpfs_head
                  FROM explorador_eventos
                 WHERE tipo_evento='S-1210' AND retificado_por_id IS NULL AND per_apur LIKE '2025-%%'
                 GROUP BY per_apur ORDER BY per_apur
                """
            )
            heads = [dict(r) for r in cur.fetchall()]
        return {
            "zips": zips,
            "eventos": eventos,
            "timeline_mes": timeline_mes,
            "timeline_envio": timeline_envio,
            "certificados_ativos": certs,
            "s1210_heads": heads,
            "counts": counts,
        }
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-import", action="store_true")
    parser.add_argument("--force-extract", action="store_true")
    parser.add_argument("--repair-zip-dates", action="store_true")
    args = parser.parse_args()

    if getattr(tenant, "OBJETIVA_ID", None) != EMPRESA_ID:
        raise RuntimeError("tenant.py ainda nao esta com OBJETIVA_ID=3 carregado")

    cert_path, pfx_data, password, cert_info, razao = load_certificate_info()
    log(f"[INPUT] certificado={cert_path.name}; zip_dir={ZIP_DIR}")
    files = zip_files()
    log(f"[INPUT] {len(files)} ZIPs encontrados")

    if args.repair_zip_dates:
        repair_zip_dates()
        final = validate_final()
        out_path = ROOT / "docs" / "OBJETIVA_ONBOARDING_2025_AUDITORIA.json"
        out_path.write_text(json.dumps(final, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        log(f"[VALIDATE] zips={final['zips']} eventos={final['eventos']} timeline_mes={final['timeline_mes']} timeline_envio={final['timeline_envio']} certs={final['certificados_ativos']}")
        log(f"[VALIDATE] auditoria={out_path}")
        return 0

    apply_empresa_migration("1.0.0")
    apply_empresa_migration("1.1.0")
    ensure_extra_columns()
    provision_sistema(razao)
    seed_empresa_schema(razao, pfx_data, password, cert_info)

    zip_ids: list[int] = []
    if not args.skip_import:
        for index, path in enumerate(files, start=1):
            dt_ini, dt_fim, detected_per = infer_period(path)
            log(f"[ZIP {index:02d}/12] {path.name} periodo={dt_ini}..{dt_fim} per_detectado={detected_per or '?'}")
            zip_id, _inserted = upload_zip_if_needed(path, dt_ini, dt_fim)
            zip_ids.append(zip_id)
            extract_zip_if_needed(zip_id, force=args.force_extract)

        conn = db.connect(empresa_id=EMPRESA_ID)
        try:
            backfill_res = backfill_chain.backfill_empresa(conn, EMPRESA_ID)
            log(f"[BACKFILL] {backfill_res}")
        finally:
            conn.close()
        sync_fechamento_status()

    final = validate_final()
    out_path = ROOT / "docs" / "OBJETIVA_ONBOARDING_2025_AUDITORIA.json"
    out_path.write_text(json.dumps(final, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    log(f"[VALIDATE] zips={final['zips']} eventos={final['eventos']} timeline_mes={final['timeline_mes']} timeline_envio={final['timeline_envio']} certs={final['certificados_ativos']}")
    log(f"[VALIDATE] auditoria={out_path}")
    log("[DONE] Objetiva provisionada/importada sem chamadas ao eSocial")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
