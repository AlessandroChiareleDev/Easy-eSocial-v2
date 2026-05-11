import psycopg2
import os

db_url = 'postgresql://postgres:EsoV2_CoxRHWQ1z6iucG7ZyvdqFIbN@db.kjbgiwnlvqnrfdozjvhq.supabase.co:5432/postgres?sslmode=require'
try:
    conn = psycopg2.connect(db_url)
    cur = conn.cursor()
    cur.execute(\"SELECT id, empresa_id, nome_arquivo_original, conteudo_oid, sha256, tamanho_bytes, extracao_status, extracao_erro, extraido_em FROM empresa_zips_brutos WHERE nome_arquivo_original LIKE '%SOLUCOES_2025-08%' ORDER BY id DESC LIMIT 5;\")
    rows = cur.fetchall()
    colnames = [desc[0] for desc in cur.description]
    print(colnames)
    for row in rows:
        print(row)
    cur.close()
    conn.close()
except Exception as e:
    print(e)
