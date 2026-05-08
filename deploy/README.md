# Deploy V2 — substituir V1 no MESMO domínio

**Estratégia:** V2 toma o lugar do V1 em `easyesocial.com.br`.
Mesma VPS, mesmo IP, mesmo domínio, mesmo certificado SSL. Sem custos novos.

V1 fica desativado mas **não deletado** (pra rollback rápido).

## Como funciona

```
ANTES:  easyesocial.com.br  →  nginx  →  V1 (Node :3333)
DEPOIS: easyesocial.com.br  →  nginx  →  V2 (FastAPI :8001 + Vue dist)
```

A troca acontece em **1 reload do nginx** (~1 segundo de downtime).

## Estrutura na VPS

```
/opt/easy-esocial/
├── repo/                  # clone do GitHub (Easy-eSocial-v2)
├── backend/               # working copy + uvicorn
│   ├── app/
│   ├── .venv/
│   ├── uploads/
│   └── .env               # secrets (chmod 600, owner esocial)
├── frontend-dist/         # build estático do Vue (servido pelo nginx)
├── certs/                 # .pfx aceitos via UI (chmod 700)
├── logs/
└── backups/
    └── v1-cutover/        # backup do nginx config V1 (rollback)
```

V1 continua onde estava (não mexer). Só fica parado.

---

## Roteiro completo (3 fases)

### Fase 1 — Provisionamento (1 vez só)

```bash
ssh root@SEU_IP_VPS
cd /tmp
git clone https://github.com/SEU_USUARIO/Easy-eSocial-v2.git
cd Easy-eSocial-v2
bash deploy/scripts/provision.sh
```

O script:

1. Instala Python 3.12, Node 20, libs.
2. Cria user `esocial` e estrutura `/opt/easy-esocial/`.
3. Clona o repo, monta `.venv`, instala deps.
4. Registra `easy-esocial.service` no systemd (NÃO inicia ainda).
5. Coloca config nginx V2 em `/etc/nginx/sites-available/easyesocial.com.br.v2.conf` (ainda inativo).

**Não toca no V1. V1 segue rodando normal.**

### Fase 2 — Configurar e subir V2 em paralelo

```bash
sudo -u esocial nano /opt/easy-esocial/backend/.env
```

Preencher:

- `SISTEMA_DB_URL` — DSN Supabase (V2 usa Supabase, não o DB do V1)
- `JWT_SECRET` — `openssl rand -hex 64`
- `FERNET_KEY` — `python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`

Build + start V2:

```bash
sudo -u esocial bash /opt/easy-esocial/repo/deploy/scripts/deploy.sh
systemctl status easy-esocial
curl http://127.0.0.1:8001/health
```

V2 está rodando na **porta 8001** (interna). V1 continua respondendo no domínio público — usuários nem notaram.

Você pode testar o V2 fazendo um túnel SSH:

```bash
# no seu pc local:
ssh -L 8001:127.0.0.1:8001 root@SEU_IP_VPS
# depois abra http://127.0.0.1:8001/api/health no browser
```

### Fase 3 — CUTOVER (troca o nginx)

Quando estiver confiante:

```bash
bash /opt/easy-esocial/repo/deploy/scripts/cutover_v1_to_v2.sh
```

O script:

1. Verifica que V2 tá saudável (`/health` interno).
2. Faz **backup** do nginx config V1 em `/opt/easy-esocial/backups/v1-cutover/`.
3. Para V1 (pm2 ou systemd, ambos cobertos).
4. Substitui `/etc/nginx/sites-enabled/easyesocial.com.br` pela config V2.
5. `nginx -t && systemctl reload nginx`.
6. Testa `https://easyesocial.com.br/api/health` público.

A partir daqui, **V2 está ao vivo** no domínio. Downtime ~1 segundo.

---

## Rollback (se der ruim)

```bash
bash /opt/easy-esocial/repo/deploy/scripts/rollback_to_v1.sh
```

Restaura nginx V1 e reinicia V1. Volta ao ar em segundos.

---

## Updates futuros (depois do cutover)

```bash
sudo -u esocial bash /opt/easy-esocial/repo/deploy/scripts/deploy.sh
```

Faz `git pull` → rsync backend → pip install → npm build → restart systemd → smoke. **Não mexe no nginx.**

---

## Backups Supabase (cron)

Adicionar em `/etc/cron.d/easy-esocial-backup`:

```cron
0 3 * * * esocial /opt/easy-esocial/repo/deploy/scripts/backup_supabase.sh >> /opt/easy-esocial/logs/backup.log 2>&1
```

Mantém 14 dias em `/opt/easy-esocial/backups/`.

---

## Logs

```
/opt/easy-esocial/logs/uvicorn.log
/opt/easy-esocial/logs/uvicorn.err.log
/var/log/nginx/easyesocial.access.log
/var/log/nginx/easyesocial.error.log
journalctl -u easy-esocial -f
```

---

## SSL

V2 reusa o cert existente do V1 em `/etc/letsencrypt/live/easyesocial.com.br/`.
A renovação automática do certbot continua funcionando porque a config V2 mantém o `location /.well-known/acme-challenge/` no server :80.

---

## Checklist antes do cutover

- [ ] `.env` preenchido com secrets reais
- [ ] `systemctl status easy-esocial` → `active (running)`
- [ ] `curl http://127.0.0.1:8001/health` → 200
- [ ] `/opt/easy-esocial/frontend-dist/index.html` existe
- [ ] DNS de `easyesocial.com.br` continua apontando pro IP da VPS
- [ ] Cert SSL ainda válido: `certbot certificates`
- [ ] Avisar usuários do downtime planejado (~1 min de margem)
