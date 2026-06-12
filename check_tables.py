import sys
import json
import os

sys.path.append(os.path.join(os.getcwd(), 'backend'))
from app import db

def inspect():
    results = []
    for eid in [1, 2]:
        try:
            with db.cursor(empresa_id=eid) as cur:
                # Primeiro listar tabelas pra ver se estamos no schema certo e qual o nome delas
                cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema NOT IN ('information_schema', 'pg_catalog')")
                tables = [r['table_name'] for r in cur.fetchall()]
                
                # Check tables and search_path
                cur.execute("SHOW search_path")
                search_path = cur.fetchone()

                results.append({
                    "empresa_id_context": eid,
                    "search_path": search_path,
                    "tables_found": [t for t in tables if 'timeline' in t or 'envio' in t]
                })
        except Exception as e:
            results.append({"empresa_id_context": eid, "error": str(e)})
            
    print(json.dumps(results, indent=2, default=str))

if __name__ == "__main__":
    inspect()
