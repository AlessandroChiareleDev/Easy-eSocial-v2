#!/usr/bin/env bash
# Easy eSocial — ROLLBACK V2 → V1
# Restaura o nginx config do V1 do backup mais recente e reinicia o V1.

set -euo pipefail

DOMAIN=easyesocial.com.br
NGINX_SITE=/etc/nginx/sites-available/$DOMAIN
NGINX_LINK=/etc/nginx/sites-enabled/$DOMAIN
BACKUP_DIR=/opt/easy-esocial/backups/v1-cutover

if [[ $EUID -ne 0 ]]; then
    echo "!! Rode como root"
    exit 1
fi

echo "==> 1. Procura backup V1 mais recente"
LAST_BAK=$(ls -1t "$BACKUP_DIR"/easy-social.*.bak "$BACKUP_DIR"/easyesocial*.bak 2>/dev/null | head -1 || true)
if [[ -z "$LAST_BAK" ]]; then
    echo "!! Nenhum backup encontrado em $BACKUP_DIR"
    echo "   Verifique também: /etc/nginx/sites-enabled/easy-social.bak_*"
    exit 1
fi
echo "   $LAST_BAK"

echo "==> 2. Para V2"
systemctl stop easy-esocial 2>/dev/null || true

echo "==> 3. Restaura nginx config V1"
# Remove o site V2 ativo
rm -f /etc/nginx/sites-enabled/easyesocial.com.br 2>/dev/null || true
# Restaura como /etc/nginx/sites-available/easy-social e symlinka
install -m 644 "$LAST_BAK" /etc/nginx/sites-available/easy-social
ln -sf /etc/nginx/sites-available/easy-social /etc/nginx/sites-enabled/easy-social

echo "==> 4. Testa nginx"
nginx -t

echo "==> 5. Reload nginx"
systemctl reload nginx

echo "==> 6. Sobe V1 (pm2)"
if command -v pm2 >/dev/null 2>&1; then
    pm2 start easy-backend 2>/dev/null || pm2 resurrect 2>/dev/null || \
        echo "   !! Suba manualmente: pm2 start easy-backend && pm2 start easy-python"
    pm2 start easy-python 2>/dev/null || true
    pm2 save 2>/dev/null || true
    pm2 list
fi

echo "==> 7. Smoke V1"
sleep 2
curl -sfk "https://$DOMAIN/" > /dev/null && echo "   OK — V1 respondendo" || echo "   !! V1 não respondeu — verifique manualmente"

cat <<EOF

==> ROLLBACK COMPLETO

V2 está parado. V1 voltou ao ar em https://$DOMAIN

Logs:
   /var/log/nginx/easyesocial.error.log (ou easy-social.error.log)
   pm2 logs

EOF
