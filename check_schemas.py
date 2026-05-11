import psycopg2
db_url = "postgresql://postgres:EsoV2_CoxRHWQ1z6iucG7ZyvdqFIbN@db.kjbgiwnlvqnrfdozjvhq.supabase.co:5432/postgres?sslmode=require"
sql = """
SELECT schema_name 
FROM information_schema.schemata 
WHERE schema_name NOT IN ('information_schema', 'pg_catalog');
"""
try:
    conn = psycopg2.connect(db_url)
    cur = conn.cursor()
    cur.execute(sql)
    print("Schemas encontrados:", [r[0] for r in cur.fetchall()])
    
    # Tentar listar tabelas no schema 'solucoes' ou similar
    cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema IN ('solucoes', 'public', 'appa') LIMIT 20;")
    print("Algumas tabelas:", [r[0] for r in cur.fetchall()])
    
    cur.close()
    conn.close()
except Exception as e:
    print(e)
