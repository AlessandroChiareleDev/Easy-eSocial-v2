"""Read-only DB exploration script. Lists schemas, tables, columns, row counts."""
import os
import sys
from pathlib import Path

# Carregar .env
env_path = Path(r"c:\Users\xandao\Documents\GitHub\Easy-Social\.env")
for line in env_path.read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    k, _, v = line.partition("=")
    os.environ[k.strip()] = v.strip()

import psycopg2
import psycopg2.extras

conn = psycopg2.connect(
    host=os.environ["DB_HOST"],
    port=os.environ["DB_PORT"],
    user=os.environ["DB_USER"],
    password=os.environ["DB_PASSWORD"],
    dbname=os.environ["DB_NAME"],
    sslmode="require" if os.environ.get("DB_SSL", "false").lower() == "true" else "prefer",
    connect_timeout=15,
)
conn.set_session(readonly=True, autocommit=True)
cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

# 1. Schemas
print("=" * 80)
print("SCHEMAS (não-sistema)")
print("=" * 80)
cur.execute("""
    SELECT schema_name
    FROM information_schema.schemata
    WHERE schema_name NOT IN ('pg_catalog','information_schema','pg_toast')
      AND schema_name NOT LIKE 'pg_temp_%'
      AND schema_name NOT LIKE 'pg_toast_temp_%'
    ORDER BY schema_name
""")
schemas = [r["schema_name"] for r in cur.fetchall()]
for s in schemas:
    print(f"  - {s}")

# 2. Tables com row count (estimado, da pg_class.reltuples — barato)
print()
print("=" * 80)
print("TABELAS por schema (com row count estimado)")
print("=" * 80)
cur.execute("""
    SELECT n.nspname AS schema, c.relname AS table_name,
           c.reltuples::bigint AS est_rows,
           pg_size_pretty(pg_total_relation_size(c.oid)) AS size
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE c.relkind = 'r'
      AND n.nspname NOT IN ('pg_catalog','information_schema','pg_toast')
      AND n.nspname NOT LIKE 'pg_%'
    ORDER BY n.nspname, c.relname
""")
tables_by_schema: dict[str, list[dict]] = {}
for r in cur.fetchall():
    tables_by_schema.setdefault(r["schema"], []).append(r)
for sch, rows in tables_by_schema.items():
    print(f"\n[{sch}] — {len(rows)} tabelas")
    for r in rows:
        print(f"  {r['table_name']:<55} {r['est_rows']:>12,} rows  ({r['size']})")

# 3. Views
print()
print("=" * 80)
print("VIEWS")
print("=" * 80)
cur.execute("""
    SELECT n.nspname AS schema, c.relname AS view_name
    FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE c.relkind IN ('v','m')
      AND n.nspname NOT IN ('pg_catalog','information_schema')
      AND n.nspname NOT LIKE 'pg_%'
    ORDER BY n.nspname, c.relname
""")
views = cur.fetchall()
for v in views:
    print(f"  {v['schema']}.{v['view_name']}")

print()
print(f"TOTAL: {sum(len(t) for t in tables_by_schema.values())} tabelas / {len(views)} views / {len(schemas)} schemas")
cur.close()
conn.close()
