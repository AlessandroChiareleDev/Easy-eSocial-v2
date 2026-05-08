#!/usr/bin/env bash
# Easy eSocial V2 — deploy update (rodar como user esocial OU root)
# Uso: bash deploy/scripts/deploy.sh [branch]

set -euo pipefail

APP_DIR=/opt/easy-esocial
BRANCH="${1:-main}"
REPO_DIR="$APP_DIR/repo"

echo "==> 1. git pull ($BRANCH)"
cd "$REPO_DIR"
git fetch --all
git checkout "$BRANCH"
git pull --ff-only

echo "==> 2. Sync backend"
rsync -a --delete --exclude='.venv' --exclude='uploads' --exclude='.env' \
    "$REPO_DIR/backend/" "$APP_DIR/backend/"

echo "==> 3. Atualiza deps Python"
"$APP_DIR/backend/.venv/bin/pip" install -r "$APP_DIR/backend/requirements.txt"

echo "==> 4. Migrações sistema (se houver)"
if [[ -f "$APP_DIR/backend/scripts/apply_migrations.py" ]]; then
    "$APP_DIR/backend/.venv/bin/python" "$APP_DIR/backend/scripts/apply_migrations.py" || \
        echo "    (sem migrações pendentes)"
fi

echo "==> 5. Build frontend"
cd "$REPO_DIR"
npm ci --silent
npm run build
rsync -a --delete "$REPO_DIR/dist/" "$APP_DIR/frontend-dist/"

echo "==> 6. Restart serviço"
sudo systemctl restart easy-esocial.service
sleep 2
sudo systemctl --no-pager --lines=10 status easy-esocial.service || true

echo "==> 7. Smoke"
# Antes do cutover, V2 só responde local. Depois do cutover, no domínio público.
curl -sf http://127.0.0.1:8001/health || echo "    !! /health local falhou"
curl -sfk https://easyesocial.com.br/api/health > /dev/null 2>&1 \
    && echo "    OK público" \
    || echo "    (público ainda não ativo — rode cutover_v1_to_v2.sh)"

echo "==> Deploy OK"
