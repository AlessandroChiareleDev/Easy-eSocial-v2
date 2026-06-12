import json
import os
import sys

# Define base project path
project_root = r"C:\Users\xandao\Documents\GitHub\Easy-eSocial-v2\backend"
if project_root not in sys.path:
    sys.path.append(project_root)

from app.db import connect
from app.tenant import SOLUCOES_ID, internal_empresa_id

def run_audit():
    empresa_id = SOLUCOES_ID
    per_apur = '2025-12'
    int_id = internal_empresa_id(empresa_id)
    
    conn = connect(empresa_id)
    conn.autocommit = True
    
    result = {}

    with conn.cursor() as cur:
        # (1) source distinct S-1210 CPFs
        # Note: using internal id 1 as per app/tenant.py for SOLUCOES
        try:
            cur.execute("""
                SELECT COUNT(DISTINCT worker_cpf) as total_cpfs
                FROM explorador_eventos 
                WHERE event_type = 'S-1210' AND per_apur = %s AND empresa_id = %s
            """, (per_apur, int_id))
            row = cur.fetchone()
            result['source_s1210_cpfs'] = row[0] if row else 0
        except Exception as e:
            result['source_s1210_cpfs_error'] = str(e)

        # (2) timeline item counts by status and erro_codigo
        try:
            cur.execute("""
                SELECT status, erro_codigo, COUNT(*) as count
                FROM timeline
                WHERE per_apur = %s
                GROUP BY status, erro_codigo
            """, (per_apur,))
            rows = cur.fetchall()
            result['timeline_counts'] = [{'status': r[0], 'erro_codigo': r[1], 'count': r[2]} for r in rows]
        except Exception as e:
            result['timeline_counts_error'] = str(e)

        # (3) final-per-CPF classification
        try:
            cur.execute("""
                WITH LatestStatus AS (
                    SELECT employee_cpf, status, 
                           CASE 
                               WHEN status = 'sucesso' THEN 5
                               WHEN status = 'erro_esocial' THEN 4
                               WHEN status = 'pendente_consulta' THEN 3
                               WHEN status = 'pendente' THEN 2
                               WHEN status = 'falha_rede' THEN 1
                               ELSE 0
                           END as priority
                    FROM timeline
                    WHERE per_apur = %s
                ),
                MaxPriority AS (
                    SELECT employee_cpf, MAX(priority) as max_p
                    FROM LatestStatus
                    GROUP BY employee_cpf
                )
                SELECT 
                    CASE 
                        WHEN max_p = 5 THEN 'sucesso'
                        WHEN max_p = 4 THEN 'erro_esocial'
                        WHEN max_p = 3 THEN 'pendente_consulta'
                        WHEN max_p = 2 THEN 'pendente'
                        WHEN max_p = 1 THEN 'falha_rede'
                        ELSE 'desconhecido'
                    END as final_status,
                    COUNT(*) as count
                FROM MaxPriority
                GROUP BY final_status
            """, (per_apur,))
            rows = cur.fetchall()
            result['final_classification'] = {r[0]: r[1] for r in rows}
        except Exception as e:
            result['final_classification_error'] = str(e)

        # (4) CPFs whose latest attempt is pendente or pendente_consulta
        try:
            cur.execute("""
                WITH RankedTimeline AS (
                    SELECT employee_cpf, status, envio_id, erro_codigo,
                           ROW_NUMBER() OVER(PARTITION BY employee_cpf ORDER BY criado_em DESC, id DESC) as rn
                    FROM timeline
                    WHERE per_apur = %s
                )
                SELECT employee_cpf, status, envio_id, erro_codigo
                FROM RankedTimeline
                WHERE rn = 1 AND status IN ('pendente', 'pendente_consulta')
            """, (per_apur,))
            rows = cur.fetchall()
            pending_list = [{'cpf': r[0], 'status': r[1], 'envio_id': r[2], 'erro_codigo': r[3]} for r in rows]
            
            grouped_pending = {}
            for item in pending_list:
                key = f"envio:{item['envio_id']}|err:{item['erro_codigo']}"
                if key not in grouped_pending:
                    grouped_pending[key] = 0
                grouped_pending[key] += 1
                
            result['pending_cpfs'] = {
                'count': len(pending_list),
                'grouped': grouped_pending,
                'list': pending_list
            }
        except Exception as e:
            result['pending_cpfs_error'] = str(e)

        # (5) selectable remaining
        try:
            cur.execute("""
                SELECT DISTINCT worker_cpf 
                FROM explorador_eventos e
                WHERE e.event_type = 'S-1210' AND e.per_apur = %s AND e.empresa_id = %s
                AND NOT EXISTS (
                    SELECT 1 FROM timeline t 
                    WHERE t.employee_cpf = e.worker_cpf 
                    AND t.per_apur = %s 
                    AND t.status IN ('sucesso', 'pendente', 'pendente_consulta')
                )
                ORDER BY worker_cpf
                LIMIT 200
            """, (per_apur, int_id, per_apur))
            rows = cur.fetchall()
            selectable_cpfs = [r[0] for r in rows]
            
            cur.execute("""
                SELECT COUNT(DISTINCT worker_cpf)
                FROM explorador_eventos e
                WHERE e.event_type = 'S-1210' AND e.per_apur = %s AND e.empresa_id = %s
                AND NOT EXISTS (
                    SELECT 1 FROM timeline t 
                    WHERE t.employee_cpf = e.worker_cpf 
                    AND t.per_apur = %s 
                    AND t.status IN ('sucesso', 'pendente', 'pendente_consulta')
                )
            """, (per_apur, int_id, per_apur))
            row = cur.fetchone()
            
            result['selectable'] = {
                'count': row[0] if row else 0,
                'first_5': selectable_cpfs[:5],
                'last_5': selectable_cpfs[-5:] if len(selectable_cpfs) > 5 else selectable_cpfs
            }
        except Exception as e:
            result['selectable_error'] = str(e)

    conn.close()
    print(json.dumps(result, indent=2))

if __name__ == '__main__':
    run_audit()
