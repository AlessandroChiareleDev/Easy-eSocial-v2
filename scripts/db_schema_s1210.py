"""Dump schema of S-1210 / pipeline tables + v_s1210_contadores definition."""
import os
from pathlib import Path

env_path = Path(r"c:\Users\xandao\Documents\GitHub\Easy-Social\.env")
for line in env_path.read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    k, _, v = line.partition("=")
    os.environ[k.strip()] = v.strip()

import psycopg2, psycopg2.extras

conn = psycopg2.connect(
    host=os.environ["DB_HOST"], port=os.environ["DB_PORT"],
    user=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"],
    dbname=os.environ["DB_NAME"], sslmode="require", connect_timeout=15,
)
conn.set_session(readonly=True, autocommit=True)
cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

TABLES = [
    "s1210_cpf_scope", "s1210_cpf_envios", "s1210_cpf_blocklist",
    "s1210_cpf_recibo", "s1210_lote1_codfunc_scope", "s1210_operadoras",
    "s1210_xlsx", "esocial_envios", "esocial_depara",
    "pipeline_cpf_results", "pipeline_snapshots", "pipeline_runs",
    "master_empresas", "config_esocial",
]

for t in TABLES:
    cur.execute("""
        SELECT column_name, data_type, character_maximum_length, is_nullable, column_default
        FROM information_schema.columns
        WHERE table_schema='public' AND table_name=%s
        ORDER BY ordinal_position
    """, (t,))
    cols = cur.fetchall()
    if not cols:
        print(f"\n### {t}  — NÃO EXISTE")
        continue
    cur.execute("SELECT COUNT(*) AS n FROM public." + t)
    n = cur.fetchone()["n"]
    print(f"\n### public.{t}  ({n:,} rows)")
    for c in cols:
        nul = "" if c["is_nullable"] == "YES" else " NOT NULL"
        dflt = f" DEFAULT {c['column_default']}" if c["column_default"] else ""
        ln = f"({c['character_maximum_length']})" if c["character_maximum_length"] else ""
        print(f"  {c['column_name']:<32} {c['data_type']}{ln}{nul}{dflt}")

# View v_s1210_contadores
print("\n\n### VIEW public.v_s1210_contadores")
cur.execute("SELECT pg_get_viewdef('public.v_s1210_contadores'::regclass, true) AS def")
print(cur.fetchone()["def"])

# Sample empresas
print("\n\n### master_empresas (amostra)")
cur.execute("SELECT * FROM public.master_empresas LIMIT 5")
for r in cur.fetchall():
    print(" ", dict(r))

# Sample 1 row de cada principal
for t in ["s1210_cpf_scope", "s1210_cpf_envios", "esocial_envios", "pipeline_cpf_results"]:
    print(f"\n### Sample 1 row — {t}")
    cur.execute(f"SELECT * FROM public.{t} LIMIT 1")
    row = cur.fetchone()
    if row:
        for k, v in row.items():
            sv = str(v)
            if len(sv) > 80:
                sv = sv[:80] + "…"
            print(f"  {k:<32} = {sv}")

cur.close(); conn.close()
