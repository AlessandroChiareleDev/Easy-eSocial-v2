#!/usr/bin/env bash
# Easy eSocial V2 — provisionamento inicial da VPS Hostinger
# Uso (como root): bash deploy/scripts/provision.sh
# Roda 1 vez. Depois de pronto, use deploy.sh pra updates.

set -euo pipefail

APP_DIR=/opt/easy-esocial
APP_USER=esocial
DOMAIN=v2.easyesocial.com.br
REPO_URL="${REPO_URL:-https://github.com/SEU_USUARIO/Easy-eSocial-v2.git}"

echo "==> 1. Pacotes do sistema"
apt-get update
apt-get install -y python3.12 python3.12-venv python3-pip nginx certbot python3-certbot-nginx \
    build-essential libpq-dev git curl

echo "==> 2. Node 20 (build do Vue)"
if ! command -v node >/dev/null || [[ "$(node -v)" != v20.* ]]; then
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
    apt-get install -y nodejs
fi

echo "==> 3. Usuário de aplicação"
id -u "$APP_USER" >/dev/null 2>&1 || useradd -r -m -d "$APP_DIR" -s /bin/bash "$APP_USER"

echo "==> 4. Estrutura de diretórios"
mkdir -p "$APP_DIR"/{logs,certs,backend/uploads,frontend-dist}
chown -R "$APP_USER:$APP_USER" "$APP_DIR"
chmod 700 "$APP_DIR/certs"

echo "==> 5. Clone do repo (como esocial)"
if [[ ! -d "$APP_DIR/backend/app" ]]; then
    sudo -u "$APP_USER" git clone "$REPO_URL" "$APP_DIR/repo"
    sudo -u "$APP_USER" cp -r "$APP_DIR/repo/backend"/* "$APP_DIR/backend/"
fi

echo "==> 6. venv + deps Python"
sudo -u "$APP_USER" python3.12 -m venv "$APP_DIR/backend/.venv"
sudo -u "$APP_USER" "$APP_DIR/backend/.venv/bin/pip" install --upgrade pip
sudo -u "$APP_USER" "$APP_DIR/backend/.venv/bin/pip" install -r "$APP_DIR/backend/requirements.txt"

echo "==> 7. .env (esqueleto se não existir)"
if [[ ! -f "$APP_DIR/backend/.env" ]]; then
    cp "$APP_DIR/repo/deploy/.env.production.example" "$APP_DIR/backend/.env"
    chown "$APP_USER:$APP_USER" "$APP_DIR/backend/.env"
    chmod 600 "$APP_DIR/backend/.env"
    echo "    !! EDITE $APP_DIR/backend/.env antes de iniciar o serviço !!"
fi

echo "==> 8. systemd unit"
install -m 644 "$APP_DIR/repo/deploy/easy-esocial.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable easy-esocial.service

echo "==> 9. nginx site"
install -m 644 "$APP_DIR/repo/deploy/nginx/$DOMAIN.conf" "/etc/nginx/sites-available/$DOMAIN"
ln -sf "/etc/nginx/sites-available/$DOMAIN" "/etc/nginx/sites-enabled/$DOMAIN"

echo "==> 10. SSL (Certbot)"
echo "    Rode manualmente depois que o DNS apontar para esta VPS:"
echo "    certbot --nginx -d $DOMAIN"

echo
echo "==> Próximos passos"
echo "  1) Edite .env: $APP_DIR/backend/.env"
echo "  2) certbot --nginx -d $DOMAIN"
echo "  3) bash deploy/scripts/deploy.sh   (faz pull + build + restart)"
echo "  4) systemctl status easy-esocial"
echo "  5) curl https://$DOMAIN/api/health"
