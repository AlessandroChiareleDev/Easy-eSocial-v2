#!/usr/bin/env bash
# Easy eSocial — CUTOVER V1 → V2 no MESMO domínio (easyesocial.com.br)
#
# IDEMPOTENTE: pode rodar de novo se algo der errado.
# Pré-requisitos:
#   1. Já rodou provision.sh (estrutura /opt/easy-esocial existe)
#   2. /opt/easy-esocial/backend/.env tá preenchido
#   3. /opt/easy-esocial/frontend-dist/ tem build atualizado
#   4. Serviço easy-esocial.service tá rodando e respondendo /api/health
#
# Uso (root):  bash deploy/scripts/cutover_v1_to_v2.sh
# Rollback:    bash deploy/scripts/rollback_to_v1.sh

set -euo pipefail

DOMAIN=easyesocial.com.br
NGINX_SITE=/etc/nginx/sites-available/$DOMAIN
NGINX_LINK=/etc/nginx/sites-enabled/$DOMAIN
BACKUP_DIR=/opt/easy-esocial/backups/v1-cutover
TS=$(date +%Y-%m-%d_%H%M)
REPO_DIR=/opt/easy-esocial/repo

if [[ $EUID -ne 0 ]]; then
    echo "!! Rode como root (sudo bash $0)"
    exit 1
fi

echo "==> 0. Sanity: V2 backend está respondendo?"
if ! curl -sf http://127.0.0.1:8001/health > /dev/null; then
    echo "!! V2 backend não responde em 127.0.0.1:8001/health"
    echo "   Verifique: systemctl status easy-esocial"
    echo "   Logs:     journalctl -u easy-esocial -n 50"
    exit 1
fi
echo "   OK — V2 backend up"

if [[ ! -f /opt/easy-esocial/frontend-dist/index.html ]]; then
    echo "!! Build do Vue não encontrado em /opt/easy-esocial/frontend-dist/index.html"
    echo "   Rode antes:  bash $REPO_DIR/deploy/scripts/deploy.sh"
    exit 1
fi
echo "   OK — frontend dist presente"

echo "==> 1. Backup do nginx config V1"
mkdir -p "$BACKUP_DIR"
if [[ -f "$NGINX_SITE" ]]; then
    cp -a "$NGINX_SITE" "$BACKUP_DIR/easyesocial.com.br.v1.$TS.bak"
    echo "   backup: $BACKUP_DIR/easyesocial.com.br.v1.$TS.bak"
else
    echo "   (sem config V1 prévio em $NGINX_SITE — primeira vez)"
fi

# Procura outros nomes possíveis do site V1
for alt in /etc/nginx/sites-available/easyesocial /etc/nginx/sites-available/default; do
    if [[ -f "$alt" ]] && grep -q "easyesocial.com.br" "$alt" 2>/dev/null; then
        cp -a "$alt" "$BACKUP_DIR/$(basename "$alt").v1.$TS.bak"
        echo "   backup adicional: $alt -> $BACKUP_DIR/"
    fi
done

echo "==> 2. Para serviço V1 (se houver pm2/systemd)"
# Tenta os 3 cenários comuns; ignora erro se não existir
if command -v pm2 >/dev/null 2>&1; then
    sudo -u "${V1_USER:-root}" pm2 stop all 2>/dev/null || true
    sudo -u "${V1_USER:-root}" pm2 save 2>/dev/null || true
    echo "   pm2: parado"
fi
for svc in easy-social easysocial easyesocial easy-esocial-v1; do
    if systemctl list-unit-files | grep -q "^$svc"; then
        systemctl stop "$svc" 2>/dev/null || true
        systemctl disable "$svc" 2>/dev/null || true
        echo "   systemd: $svc parado"
    fi
done

echo "==> 3. Instala nginx config V2"
install -m 644 "$REPO_DIR/deploy/nginx/$DOMAIN.conf" "$NGINX_SITE"

# Remove qualquer enabled antigo conflitante e cria symlink limpo
find /etc/nginx/sites-enabled -maxdepth 1 -lname "*easyesocial*" -delete 2>/dev/null || true
rm -f /etc/nginx/sites-enabled/default 2>/dev/null || true
ln -sf "$NGINX_SITE" "$NGINX_LINK"

echo "==> 4. Testa nginx config"
nginx -t

echo "==> 5. Reload nginx"
systemctl reload nginx

echo "==> 6. Smoke V2 público"
sleep 2
if curl -sfk "https://$DOMAIN/api/health" > /dev/null; then
    echo "   OK — https://$DOMAIN/api/health respondeu"
else
    echo "   !! /api/health falhou — verificar logs:"
    echo "      tail -f /var/log/nginx/easyesocial.error.log"
    echo "      journalctl -u easy-esocial -f"
fi

cat <<EOF

==> CUTOVER COMPLETO

Frontend:  https://$DOMAIN
API:       https://$DOMAIN/api/health
Logs:      /var/log/nginx/easyesocial.{access,error}.log
           journalctl -u easy-esocial -f

ROLLBACK: bash $REPO_DIR/deploy/scripts/rollback_to_v1.sh

V1 não foi DELETADO — só desativado. Backup do nginx:
   $BACKUP_DIR/

EOF
