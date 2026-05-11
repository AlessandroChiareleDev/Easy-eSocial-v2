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
if [[ $EUID -eq 0 ]]; then
    SUDO=""
else
    SUDO="sudo -n"
fi
$SUDO systemctl restart easy-esocial.service
sleep 2
$SUDO systemctl --no-pager --lines=10 status easy-esocial.service || true

echo "==> 6.5 Sync nginx config (se mudou)"
NGINX_SRC="$REPO_DIR/deploy/nginx/easyesocial.com.br.conf"
NGINX_DST="/etc/nginx/sites-available/easyesocial.com.br.conf"
NGINX_NEEDS_RELOAD=0

# Remove confs antigos que conflitam com server_name easyesocial.com.br
# (instalações manuais legadas: easy-social, easy-esocial, easyesocial.com.br SEM .conf, .v2.conf, etc.)
for old in \
    /etc/nginx/sites-enabled/easy-social \
    /etc/nginx/sites-enabled/easy-esocial \
    /etc/nginx/sites-available/easy-social \
    /etc/nginx/sites-available/easy-esocial \
    /etc/nginx/sites-enabled/easyesocial.com.br \
    /etc/nginx/sites-available/easyesocial.com.br \
    /etc/nginx/sites-enabled/easyesocial.com.br.v2.conf \
    /etc/nginx/sites-available/easyesocial.com.br.v2.conf; do
    if [[ -e "$old" || -L "$old" ]]; then
        echo "    removendo conf antigo: $old"
        $SUDO rm -f "$old"
        NGINX_NEEDS_RELOAD=1
    fi
done

if [[ -f "$NGINX_SRC" ]] && ! cmp -s "$NGINX_SRC" "$NGINX_DST" 2>/dev/null; then
    echo "    nginx config mudou — atualizando"
    $SUDO cp "$NGINX_SRC" "$NGINX_DST"
    $SUDO ln -sf "$NGINX_DST" /etc/nginx/sites-enabled/easyesocial.com.br.conf
    NGINX_NEEDS_RELOAD=1
fi

# Sync conf.d/ (limites globais — vence qualquer server block legado)
CONFD_SRC_DIR="$REPO_DIR/deploy/nginx/conf.d"
if [[ -d "$CONFD_SRC_DIR" ]]; then
    for src in "$CONFD_SRC_DIR"/*.conf; do
        [[ -f "$src" ]] || continue
        name=$(basename "$src")
        dst="/etc/nginx/conf.d/$name"
        if ! cmp -s "$src" "$dst" 2>/dev/null; then
            echo "    conf.d/$name mudou — atualizando"
            $SUDO cp "$src" "$dst"
            NGINX_NEEDS_RELOAD=1
        fi
    done
fi

if [[ $NGINX_NEEDS_RELOAD -eq 1 ]]; then
    if $SUDO nginx -t; then
        $SUDO systemctl reload nginx
        echo "    nginx reload OK"
    else
        echo "    !! nginx -t falhou — config NAO aplicada"
    fi
else
    echo "    nginx config inalterada"
fi

# DEBUG: print all active confs + grep client_max_body_size
echo "    --- DEBUG nginx sites-enabled ---"
$SUDO ls -la /etc/nginx/sites-enabled/ 2>&1 || true
echo "    --- DEBUG conf.d ---"
$SUDO ls -la /etc/nginx/conf.d/ 2>&1 || true
echo "    --- DEBUG quem tem easyesocial server_name ---"
$SUDO grep -rl "easyesocial" /etc/nginx/ 2>/dev/null || true
echo "    --- DEBUG client_max_body_size em nginx -T ---"
$SUDO nginx -T 2>/dev/null | grep -i "client_max_body_size\|server_name" | head -30 || true

echo "==> 7. Smoke"
# Antes do cutover, V2 só responde local. Depois do cutover, no domínio público.
curl -sf http://127.0.0.1:8001/health || echo "    !! /health local falhou"
curl -sfk https://easyesocial.com.br/api/health > /dev/null 2>&1 \
    && echo "    OK público" \
    || echo "    (público ainda não ativo — rode cutover_v1_to_v2.sh)"

echo "==> Deploy OK"
