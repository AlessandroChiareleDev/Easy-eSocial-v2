#!/usr/bin/env bash
# Easy eSocial V2 - instalacao completa numa VPS Debian 13 (Hostinger).
# Banco local na VPS (easy_esocial): schema sistema (login) + appa + solucoes.
# Rodar como root, com o codigo ja clonado em /opt/easy-esocial/repo:
#   bash /root/setup_vps.sh
# Pede no terminal: senha do banco Supabase EasyEsocial e login/senha do novo acesso.
set -euo pipefail
APP=/opt/easy-esocial
DB=easy_esocial
SB_HOST=aws-1-us-east-2.pooler.supabase.com
SB_USER=postgres.zpizibafccwsjgvplcum
HOST_PUBLICO=${HOST_PUBLICO:-srv2006850.hstgr.cloud}
APPA_CNPJ=05969071000110
SOL_CNPJ=09445502000109
say(){ printf '\n==> %s\n' "$*"; }
psql_db(){ sudo -u postgres psql -X -q -v ON_ERROR_STOP=1 -d "$DB" "$@"; }
tem_schema(){ psql_db -tAc "SELECT 1 FROM pg_namespace WHERE nspname='$1'" | grep -q 1; }

[ -d "$APP/repo/.git" ] || { echo "Falta o codigo em $APP/repo (faca o git clone antes)"; exit 1; }
git config --global --add safe.directory "$APP/repo" || true

say "1/9 Pacotes"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq postgresql postgresql-contrib python3 python3-venv python3-dev build-essential \
  libpq-dev nginx git curl rsync nodejs npm openssl sudo >/dev/null
systemctl enable --now postgresql

say "2/9 Usuario, pastas e banco local"
id esocial >/dev/null 2>&1 || useradd -r -m -d "$APP" -s /bin/bash esocial
mkdir -p "$APP"/backend/uploads "$APP"/frontend-dist "$APP"/certs "$APP"/logs "$APP"/backups
[ -f /root/.easy_db_pass ] || openssl rand -hex 24 > /root/.easy_db_pass
chmod 600 /root/.easy_db_pass
DBPASS=$(cat /root/.easy_db_pass)
sudo -u postgres psql -X -q -v ON_ERROR_STOP=1 -v pw="$DBPASS" <<'SQL'
SELECT 'CREATE ROLE esocial LOGIN' WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='esocial') \gexec
ALTER ROLE esocial PASSWORD :'pw';
SELECT 'CREATE DATABASE easy_esocial OWNER esocial' WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname='easy_esocial') \gexec
SQL

if ! tem_schema appa; then
  say "3/9 Backup do Supabase EasyEsocial (dados da APPA)"
  DUMP="$APP/backups/easyesocial_public_$(date +%Y%m%d_%H%M).dump"
  read -rsp "Senha do banco Supabase EasyEsocial: " SBPW; echo
  PGPASSWORD="$SBPW" pg_dump -h "$SB_HOST" -p 5432 -U "$SB_USER" -d postgres -n public \
    --no-owner --no-privileges -Fc -f "$DUMP"
  unset SBPW
  ls -lh "$DUMP"

  say "4/9 Restaurando no schema appa"
  psql_db -c 'CREATE SCHEMA IF NOT EXISTS extensions; CREATE EXTENSION IF NOT EXISTS pgcrypto SCHEMA extensions; CREATE EXTENSION IF NOT EXISTS "uuid-ossp" SCHEMA extensions;'
  sudo -u postgres pg_restore -d "$DB" --no-owner --no-privileges --role=esocial "$DUMP" \
    2> "$APP/logs/restore_appa.err" || true
  echo "avisos do restore: $(wc -l < "$APP/logs/restore_appa.err") linhas ($APP/logs/restore_appa.err)"
  psql_db -c "ALTER SCHEMA public RENAME TO appa; CREATE SCHEMA public AUTHORIZATION esocial; ALTER SCHEMA appa OWNER TO esocial;"
else
  say "3-4/9 schema appa ja existe, pulando backup/restore"
fi

if ! tem_schema solucoes; then
  say "5/9 Schema solucoes (estrutura da APPA + dados da Solucoes que existirem)"
  sudo -u postgres pg_dump -d "$DB" -n appa --schema-only --no-owner --no-privileges \
    | sed -e 's/\bappa\./solucoes./g' -e 's/SCHEMA appa\b/SCHEMA solucoes/g' -e "s/'appa\./'solucoes./g" \
    > "$APP/backups/solucoes_schema.sql"
  sudo -u postgres psql -X -q -d "$DB" -c "SET ROLE esocial" -f "$APP/backups/solucoes_schema.sql" \
    > /dev/null 2> "$APP/logs/solucoes_schema.err" || true
  sudo -u postgres psql -X -v ON_ERROR_STOP=1 -d "$DB" -v cnpj="$SOL_CNPJ" <<'SQL'
SELECT set_config('easy.cnpj', :'cnpj', false);
SET session_replication_role = replica;
DO $$
DECLARE sol int; t record; n bigint;
BEGIN
  SELECT id INTO sol FROM appa.master_empresas
   WHERE regexp_replace(coalesce(cnpj,''),'\D','','g') = current_setting('easy.cnpj') OR nome ILIKE '%solu%'
   ORDER BY id LIMIT 1;
  IF sol IS NULL THEN RAISE NOTICE 'Solucoes nao encontrada em appa.master_empresas'; RETURN; END IF;
  RAISE NOTICE 'Solucoes = empresa_id % no banco da APPA', sol;
  INSERT INTO solucoes.master_empresas SELECT * FROM appa.master_empresas WHERE id = sol;
  UPDATE solucoes.master_empresas SET id = 1;
  FOR t IN SELECT c.table_name FROM information_schema.columns c
             JOIN information_schema.tables tb ON tb.table_schema = c.table_schema
              AND tb.table_name = c.table_name AND tb.table_type = 'BASE TABLE'
            WHERE c.table_schema = 'appa' AND c.column_name = 'empresa_id' AND c.table_name <> 'master_empresas'
  LOOP
    BEGIN
      EXECUTE format('INSERT INTO solucoes.%I SELECT * FROM appa.%I WHERE empresa_id = $1', t.table_name, t.table_name) USING sol;
      GET DIAGNOSTICS n = ROW_COUNT;
      IF n > 0 THEN
        EXECUTE format('UPDATE solucoes.%I SET empresa_id = 1', t.table_name);
        RAISE NOTICE 'solucoes.%: % linhas', t.table_name, n;
      END IF;
    EXCEPTION WHEN others THEN RAISE NOTICE 'pulando %: %', t.table_name, SQLERRM;
    END;
  END LOOP;
END $$;
DO $$
DECLARE r record;
BEGIN
  FOR r IN SELECT s.relname AS seq, t.relname AS tbl, a.attname AS col
             FROM pg_class s
             JOIN pg_depend d ON d.objid = s.oid AND d.deptype IN ('a','i')
             JOIN pg_class t ON t.oid = d.refobjid
             JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = d.refobjsubid
             JOIN pg_namespace ns ON ns.oid = s.relnamespace
            WHERE s.relkind = 'S' AND ns.nspname = 'solucoes'
  LOOP
    EXECUTE format('SELECT setval(%L, GREATEST(coalesce((SELECT max(%I) FROM solucoes.%I), 0), 1))',
                   'solucoes.' || r.seq, r.col, r.tbl);
  END LOOP;
END $$;
SQL
else
  say "5/9 schema solucoes ja existe, pulando"
fi

say "6/9 Schema sistema (login, empresas, permissoes)"
psql_db -c "CREATE SCHEMA IF NOT EXISTS sistema AUTHORIZATION esocial"
sed '/CREATE EXTENSION/d' "$APP/repo/backend/migrations/sistema/sistema_v1.0.0.sql" \
  | sudo -u postgres psql -X -q -v ON_ERROR_STOP=1 -d "$DB" -c "SET ROLE esocial; SET search_path TO sistema, public" -f -
psql_db -v a="$APPA_CNPJ" -v s="$SOL_CNPJ" <<'SQL'
INSERT INTO sistema.empresas_routing (cnpj, razao_social, schema_name, schema_version) VALUES
  (:'a', 'APPA', 'appa', '1.0.0'), (:'s', 'SOLUCOES', 'solucoes', '1.0.0')
ON CONFLICT (cnpj) DO NOTHING;
SQL

say "7/9 Backend (FastAPI)"
rsync -a --delete --exclude .venv --exclude uploads --exclude .env --exclude '_tmp*' \
  --exclude 'Solucoes Dia*' --exclude '__pycache__' --exclude '_certificados' \
  "$APP/repo/backend/" "$APP/backend/"
[ -x "$APP/backend/.venv/bin/python" ] || python3 -m venv "$APP/backend/.venv"
"$APP/backend/.venv/bin/pip" install -q --upgrade pip
"$APP/backend/.venv/bin/pip" install -q -r "$APP/backend/requirements.txt"
if [ ! -f "$APP/backend/.env" ]; then
  FK=$("$APP/backend/.venv/bin/python" -c 'from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())')
  cat > "$APP/backend/.env" <<EOF
SISTEMA_DB_URL=postgresql://esocial:${DBPASS}@127.0.0.1:5432/${DB}
JWT_SECRET=$(openssl rand -hex 48)
JWT_ALGORITHM=HS256
JWT_EXPIRES_MINUTES=480
LOCAL_DEV_LOGIN=false
FERNET_KEY=${FK}
API_HOST=127.0.0.1
API_PORT=8001
CORS_ORIGINS=https://${HOST_PUBLICO},http://${HOST_PUBLICO}
MAX_UPLOAD_BYTES=3221225472
EOF
fi
chmod 600 "$APP/backend/.env"

if [ "$(psql_db -tAc 'SELECT count(*) FROM sistema.users')" = "0" ]; then
  say "Criando o seu login"
  read -rp "Login (e-mail ou nome de usuario): " LOGIN
  while :; do
    read -rsp "Senha (minimo 10 caracteres): " P1; echo
    read -rsp "Repita a senha: " P2; echo
    [ "$P1" = "$P2" ] && [ ${#P1} -ge 10 ] && break
    echo "Senhas diferentes ou curtas. Tenta de novo."
  done
  HASH=$(P="$P1" "$APP/backend/.venv/bin/python" -c 'import os,bcrypt;print(bcrypt.hashpw(os.environ["P"].encode()[:72],bcrypt.gensalt()).decode())')
  unset P1 P2
  psql_db -v login="$LOGIN" -v hash="$HASH" <<'SQL'
INSERT INTO sistema.users (email, password_hash, nome, super_admin) VALUES (:'login', :'hash', :'login', true)
ON CONFLICT (email) DO UPDATE SET password_hash = EXCLUDED.password_hash, ativo = true, super_admin = true;
INSERT INTO sistema.user_empresas (user_id, cnpj, papel)
SELECT u.id, e.cnpj, 'admin' FROM sistema.users u CROSS JOIN sistema.empresas_routing e WHERE u.email = :'login'
ON CONFLICT DO NOTHING;
SQL
fi

chown -R esocial:esocial "$APP"
chmod 755 "$APP" "$APP/frontend-dist"
cp "$APP/repo/deploy/easy-esocial.service" /etc/systemd/system/easy-esocial.service
systemctl daemon-reload
systemctl enable easy-esocial >/dev/null 2>&1
systemctl restart easy-esocial

say "8/9 Frontend (Vue)"
cd "$APP/repo"
npm ci --no-audit --no-fund
npm run build || npx vite build
rsync -a --delete dist/ "$APP/frontend-dist/"
chown -R esocial:esocial "$APP/frontend-dist"

say "9/9 Nginx (usa o certificado HTTPS que ja existe na VPS)"
# O Game Panel (AMP) usava este dominio; guardamos a config dele e o Easy eSocial assume.
[ -f "/etc/nginx/conf.d/${HOST_PUBLICO}.conf" ] && mv "/etc/nginx/conf.d/${HOST_PUBLICO}.conf" /root/gamepanel-nginx.conf.bak
# Certificado unico (certbot --webroot, cert-name easy-esocial) cobre os 3 nomes
CERT=/etc/letsencrypt/live/easy-esocial
[ -d "$CERT" ] || CERT=/etc/letsencrypt/live/${HOST_PUBLICO}
cat > /etc/nginx/conf.d/easy-esocial.conf <<EOF
server {
    listen 80;
    listen [::]:80;
    server_name ${HOST_PUBLICO} easyesocial.com.br www.easyesocial.com.br;
    location /.well-known/acme-challenge/ { root /var/www/html; }
    location / { return 301 https://\$host\$request_uri; }
}
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name ${HOST_PUBLICO} easyesocial.com.br www.easyesocial.com.br;
    ssl_certificate ${CERT}/fullchain.pem;
    ssl_certificate_key ${CERT}/privkey.pem;
    client_max_body_size 2G;
    client_body_timeout 1800s;
    proxy_read_timeout 1800s;
    proxy_send_timeout 1800s;
    proxy_request_buffering off;
    add_header Strict-Transport-Security "max-age=31536000" always;
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
    root ${APP}/frontend-dist;
    index index.html;
    location = /index.html { add_header Cache-Control "no-store" always; try_files /index.html =404; }
    location /api/ {
        # Compat: telas S-1010/Problemas chamam rotas antigas do V1
        rewrite ^/api/rubricas/com-problemas\$ /api/natureza/rubricas-com-problemas break;
        rewrite ^/api/rubricas/progresso\$ /api/natureza/progresso break;
        rewrite ^/api/validacao/(resumo|divergencias)\$ /api/rubrica/\$1 break;
        proxy_pass http://127.0.0.1:8001;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_buffering off;
    }
    location / { try_files \$uri \$uri/ /index.html; }
}
EOF
nginx -t
systemctl reload nginx

sleep 3
say "Checagem"
curl -s http://127.0.0.1:8001/health; echo
curl -s http://127.0.0.1:8001/health/sistema; echo
psql_db -tAc "SELECT 'appa: '||(SELECT count(*) FROM appa.explorador_rubricas)||' rubricas | solucoes: '||(SELECT count(*) FROM solucoes.master_empresas)||' empresa | usuarios: '||(SELECT count(*) FROM sistema.users)"
echo
echo "PRONTO: abra https://${HOST_PUBLICO}"
