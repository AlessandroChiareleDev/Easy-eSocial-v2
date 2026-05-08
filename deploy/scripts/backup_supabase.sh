#!/usr/bin/env bash
# Backup do schema sistema/ + dump dos schemas appa, solucoes, legado
# Roda via cron (diário) na VPS:
#   0 3 * * *  esocial  /opt/easy-esocial/repo/deploy/scripts/backup_supabase.sh
set -euo pipefail

BACKUP_DIR=/opt/easy-esocial/backups
RETENTION_DAYS=14

mkdir -p "$BACKUP_DIR"
TS=$(date +%Y-%m-%d_%H%M)
OUT="$BACKUP_DIR/easyesocial_$TS.sql.gz"

# DSN vem do .env do backend
set -a
. /opt/easy-esocial/backend/.env
set +a

echo "==> pg_dump → $OUT"
pg_dump "$SISTEMA_DB_URL" \
    --no-owner --no-privileges \
    --schema=sistema --schema=appa --schema=solucoes --schema=legado \
    | gzip > "$OUT"

# Rotação
find "$BACKUP_DIR" -name 'easyesocial_*.sql.gz' -mtime +$RETENTION_DAYS -delete

echo "==> Backup OK ($(du -h "$OUT" | cut -f1))"
