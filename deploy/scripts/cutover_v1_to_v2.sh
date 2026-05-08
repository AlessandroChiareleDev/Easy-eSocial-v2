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
NGINX_SITE_V2=/etc/nginx/sites-available/$DOMAIN
NGINX_LINK_V2=/etc/nginx/sites-enabled/$DOMAIN
# Nome do site V1 atual (descoberto: /etc/nginx/sites-enabled/easy-social)
NGINX_SITE_V1=/etc/nginx/sites-enabled/easy-social
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

echo "==> 1. Backup do nginx config V1 (qualquer arquivo com easyesocial.com.br)"
mkdir -p "$BACKUP_DIR"
for f in /etc/nginx/sites-available/*; do
    [[ -f "$f" ]] || continue
    if grep -q "easyesocial.com.br" "$f" 2>/dev/null; then
        cp -a "$f" "$BACKUP_DIR/$(basename "$f").$TS.bak"
        echo "   backup: $f -> $BACKUP_DIR/"
    fi
done

echo "==> 2. Para V1 (pm2 stop + save)"
if command -v pm2 >/dev/null 2>&1; then
    pm2 stop easy-backend 2>/dev/null || true
    pm2 stop easy-python 2>/dev/null || true
    pm2 save 2>/dev/null || true
    pm2 list
    echo "   pm2: V1 parado"
fi

echo "==> 3. Instala nginx config V2"
install -m 644 "$REPO_DIR/deploy/nginx/$DOMAIN.conf" "$NGINX_SITE_V2"

# Remove TODOS os enabled antigos que apontam pra easy-social/easyesocial
for link in /etc/nginx/sites-enabled/*; do
    [[ -L "$link" || -f "$link" ]] || continue
    if [[ "$(basename "$link")" != "$DOMAIN" ]] && grep -q "easyesocial.com.br" "$link" 2>/dev/null; then
        rm -f "$link"
        echo "   removido enabled antigo: $link"
    fi
done
rm -f /etc/nginx/sites-enabled/default 2>/dev/null || true
ln -sf "$NGINX_SITE_V2" "$NGINX_LINK_V2"

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

V1 não foi DELETADO — só parado via pm2. Backup do nginx:
   $BACKUP_DIR/

EOF
