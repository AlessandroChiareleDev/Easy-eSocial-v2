# Deploy V2 — Hostinger VPS

Sub-domínio: **v2.easyesocial.com.br** (paralelo ao V1, não toca em produção atual).

## Estrutura na VPS

```
/opt/easy-esocial/
├── repo/                  # clone do GitHub (origem do código)
├── backend/               # cópia working — onde uvicorn roda
│   ├── app/
│   ├── .venv/
│   ├── uploads/
│   └── .env               # secrets (chmod 600, owner esocial)
├── frontend-dist/         # build estático do Vue (servido pelo nginx)
├── certs/                 # .pfx aceitos via UI (chmod 700)
├── logs/
└── backups/
```

## 1) Provisionamento (1 vez)

```bash
ssh root@VPS_IP
cd /tmp
git clone https://github.com/SEU_USUARIO/Easy-eSocial-v2.git
cd Easy-eSocial-v2
bash deploy/scripts/provision.sh
```

O script:
1. Instala Python 3.12, Node 20, nginx, certbot, libpq.
2. Cria user `esocial`, estrutura de diretórios.
3. Clona repo em `/opt/easy-esocial/repo`.
4. Cria `.venv`, instala `requirements.txt`.
5. Copia `easy-esocial.service` → systemd, enable.
6. Copia `nginx/v2.easyesocial.com.br.conf` → sites-enabled.

## 2) Configurar `.env`

```bash
sudo -u esocial nano /opt/easy-esocial/backend/.env
```

Preencher (modelo em `deploy/.env.production.example`):
- `SISTEMA_DB_URL` (DSN Supabase)
- `JWT_SECRET` → `openssl rand -hex 64`
- `CERT_ENCRYPTION_KEY` → `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`

## 3) DNS + SSL

1. Apontar `v2.easyesocial.com.br` (A record) para o IP da VPS.
2. Aguardar propagação (`dig v2.easyesocial.com.br`).
3. Emitir certificado:
   ```bash
   certbot --nginx -d v2.easyesocial.com.br
   ```

## 4) Subir o serviço

```bash
systemctl start easy-esocial
systemctl status easy-esocial
curl -s https://v2.easyesocial.com.br/api/health
```

## 5) Deploy de updates

```bash
sudo -u esocial bash /opt/easy-esocial/repo/deploy/scripts/deploy.sh main
```

Faz: `git pull` → rsync backend → pip install → npm build → restart systemd → smoke `/api/health`.

## 6) Backups (cron)

```cron
0 3 * * * esocial /opt/easy-esocial/repo/deploy/scripts/backup_supabase.sh >> /opt/easy-esocial/logs/backup.log 2>&1
```

Mantém 14 dias em `/opt/easy-esocial/backups/`.

## 7) Logs

```
/opt/easy-esocial/logs/uvicorn.log
/opt/easy-esocial/logs/uvicorn.err.log
/var/log/nginx/v2.easyesocial.{access,error}.log
journalctl -u easy-esocial -f
```

## Rollback

```bash
sudo -u esocial bash /opt/easy-esocial/repo/deploy/scripts/deploy.sh <commit-anterior>
```

## NÃO afeta o V1

V1 usa porta 3000/3333 e domínio `easyesocial.com.br`.
V2 usa porta 8001 e `v2.easyesocial.com.br`. Configs nginx independentes.
