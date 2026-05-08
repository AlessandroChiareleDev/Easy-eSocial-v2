# BÍBLIA V2 — Norte de Execução

> **Este é o documento mestre.** Lê primeiro `INVENTARIO_V1_PRE_MIGRACAO.md`, `MIGRACAO_V1_V2.md`, `ARQUITETURA_MULTI_EMPRESA.md` e `UPLOAD_CERT_A1_REALPREV.md`. Este aqui consolida tudo num **plano operacional executável em ordem**, sem ambiguidade. Quando estiver perdido, volta aqui.
>
> **Data**: 08/05/2026
> **Estado V2 hoje**: backend FastAPI funcional pra envio S-1210 (Soluções 13.6k CPFs validados via CICLO100), frontend Vue 3 80% pronto, **multi-tenant inexistente, auth inexistente, upload cert inexistente, Supabase inexistente**.
> **Estado-alvo**: V2 em produção no VPS Hostinger, 2 bancos Supabase (APPA + Soluções) + 1 banco Sistema, login funcionando, upload cert A1 estilo Real Prev, Rafa operando exclusivamente no V2, V1 desligado.

---

## Sumário

1. [Visão de uma página](#1-visão-de-uma-página)
2. [Decisões já travadas (não rediscutir)](#2-decisões-já-travadas-não-rediscutir)
3. [Decisões pendentes (preciso responder antes de Phase 2)](#3-decisões-pendentes-preciso-responder-antes-de-phase-2)
4. [Diagrama final](#4-diagrama-final)
5. [Mapa de dependências entre fases](#5-mapa-de-dependências-entre-fases)
6. [Fase 0 — Salvamento (HOJE)](#fase-0--salvamento-hoje)
7. [Fase 1 — Limpeza V2](#fase-1--limpeza-v2)
8. [Fase 2 — Schema único + Sistema DB](#fase-2--schema-único--sistema-db)
9. [Fase 3 — Multi-tenant runtime](#fase-3--multi-tenant-runtime)
10. [Fase 4 — Auth + Upload Cert A1](#fase-4--auth--upload-cert-a1)
11. [Fase 5 — Provisionar Supabase APPA + Soluções](#fase-5--provisionar-supabase-appa--soluções)
12. [Fase 6 — ETL APPA V1→Supabase](#fase-6--etl-appa-v1supabase)
13. [Fase 7 — Migrar Soluções local→Supabase](#fase-7--migrar-soluções-localsupabase)
14. [Fase 8 — Funcionalidades faltantes (auth UI, upload XLSX, validação)](#fase-8--funcionalidades-faltantes-auth-ui-upload-xlsx-validação)
15. [Fase 9 — Frontend conectado](#fase-9--frontend-conectado)
16. [Fase 10 — Deploy VPS](#fase-10--deploy-vps)
17. [Fase 11 — Cutover + aposentadoria V1](#fase-11--cutover--aposentadoria-v1)
18. [Anexo A — Estrutura de pastas alvo do V2](#anexo-a--estrutura-de-pastas-alvo-do-v2)
19. [Anexo B — Variáveis de ambiente](#anexo-b--variáveis-de-ambiente)
20. [Anexo C — Comandos prontos](#anexo-c--comandos-prontos)
21. [Anexo D — Critérios de "pronto"](#anexo-d--critérios-de-pronto)
22. [Regras de ouro](#regras-de-ouro)

---

## 1. Visão de uma página

**O que vou construir, em uma frase**: um sistema web (Vue 3 + FastAPI) hospedado no VPS atual da Hostinger, onde cada empresa tem **seu próprio banco Supabase**, com upload de certificado A1 estilo Real Prev, login por usuário, multi-empresa por usuário, e capaz de tudo que o V1 fazia + envio S-1210/S-1298/S-1010 + chain walk + XML completo do governo armazenado.

**Como cheguei aqui**:
- O V1 funciona mas é Node antigo, multi-tenant frágil (por linha), sem XML completo, schema misturado.
- O V2 nasceu pra resolver tudo isso. Já tem o **núcleo de envio** validado (CICLO100 fechou Soluções).
- Falta **periferia**: auth, multi-tenant runtime, upload cert, frontend ligado, deploy.
- Real Prev (`Projeto/`) tem o pattern de cert correto — vou copiar dele, não do V1.

**Princípios não-negociáveis**:

1. **1 banco por empresa** no Supabase. Sistema DB separado pra routing/users.
2. **Schema idêntico em todos os bancos** de empresa. Migration runner aplica em todos.
3. **Cert A1 fica no servidor** (filesystem `/opt/easy-esocial/certs/`), **metadata + senha Fernet no banco**.
4. **JWT** carrega `user_id` + `empresas_permitidas[]`. Header `X-Empresa-CNPJ` define escopo por request.
5. **APPA migra como histórico** (sem XML completo retroativo). Soluções e empresas novas têm XML completo desde o dia 1.
6. **Nada destrutivo no V1** até cutover validado. V1 fica online em paralelo até Fase 11.

---

## 2. Decisões já travadas (não rediscutir)

| # | Decisão | Razão |
|---|---|---|
| D1 | Backend = FastAPI Python | já existe + envio paralelo + chain walk validado |
| D2 | Frontend = Vue 3 + TS strict + Tailwind v4 | já existe (Liquid Glass / Ghost Green) |
| D3 | DB = Supabase (managed) | backup + HA + Postgres puro |
| D4 | 1 DB por empresa | isolamento total LGPD/auditoria |
| D5 | DB Sistema separado (3º banco) | routing + users + audit_log |
| D6 | Pattern cert A1 = Real Prev (não V1) | mais maduro, multi-tenant nativo |
| D7 | XML completo via `lobject` Postgres + gzip | rastreabilidade |
| D8 | Cutover via subdomain `v2.easyesocial.com.br` por 7 dias | rollback safe |
| D9 | V1 fica read-only após cutover, archive 12 meses | LGPD + sanidade |
| D10 | Senha cert criptografada Fernet, **nunca** em plaintext | Real Prev pattern |
| D11 | URI vazio na assinatura XMLDSig | exigência eSocial (erro 142) |
| D12 | `signxml` lib (não custom) | maturo, BR-friendly |

---

## 3. Decisões pendentes (preciso responder antes de Phase 2)

| # | Pergunta | Opções | Recomendação |
|---|---|---|---|
| P1 | Supabase Cloud ou self-hosted no VPS? | a) Cloud b) self-hosted | **Cloud** — backup/HA out-of-the-box |
| P2 | Sistema DB no Supabase Cloud separado, ou junto com APPA? | a) separado b) junto APPA | **separado** — desacoplamento |
| P3 | Onde a chave Fernet vive em produção? | a) `.env` b) Supabase Vault c) Hashicorp Vault | **a + rotacionar pra `.env` enquanto não migra pra Vault**; manter compat com chave hardcoded Real Prev pra descriptografar senhas existentes |
| P4 | Storage de XML > 24m (frio) | a) S3-compat (Hostinger Object Storage) b) só comprimido no Postgres | **a** — quente 24m no DB, frio S3 |
| P5 | Auth: importar bcrypt do V1 ou recriar usuários? | a) importar b) recriar | **importar** — Rafa não troca senha |
| P6 | Tela de seleção empresa: dropdown ou cards? | a) dropdown b) cards visuais | **cards** — mais bonito, condiz com Liquid Glass |
| P7 | Logs estruturados | a) loguru b) stdlib logging c) structlog | **loguru** — DX melhor, JSON pronto |
| P8 | Pool de conexão | a) `psycopg2.pool` b) `asyncpg` c) SQLAlchemy session | **a** — leve, casa com FastAPI sync routes que já existem |

> **Bloqueio**: Phase 2 só começa quando P1, P2 e P5 estiverem respondidos.

---

## 4. Diagrama final

```
┌──────────────────────────────────────────────────────────────────────┐
│                  https://easyesocial.com.br                          │
│                       (VPS Hostinger única)                          │
│                                                                      │
│   Nginx (TLS Let's Encrypt) ────────────┐                            │
│     ├── /         → /opt/easy-esocial/frontend-dist/ (Vue 3 build)   │
│     └── /api/*    → 127.0.0.1:8001 (uvicorn)                         │
└──────────────────────────────────┬───────────────────────────────────┘
                                   │
┌──────────────────────────────────▼───────────────────────────────────┐
│                    Backend FastAPI (uvicorn :8001)                   │
│                                                                      │
│  middleware auth      → resolve user via JWT                         │
│  middleware tenant    → resolve cnpj via X-Empresa-CNPJ              │
│  request.state.db     → pool[cnpj].getconn()                         │
│                                                                      │
│  modules:                                                            │
│    auth.py            (login, JWT)                                   │
│    tenant.py          (router de DB + pool por empresa)              │
│    cert_routes.py     (upload/listar/ativo/delete cert A1)           │
│    certificate_*.py   (lift do Real Prev)                            │
│    xml_signer.py      (lift do Real Prev — signxml + URI vazio)      │
│    envio_paralelo_v2  (já existe — só trocar cert_path por DB query) │
│    explorador.py      (já existe)                                    │
│    upload_dominio.py  (NOVO — porta do V1 Node)                      │
│    validacao_*.py     (NOVO — porta do V1 Node)                      │
│    cruzamento.py      (NOVO — porta do V1 Node)                      │
└────────────┬─────────────────────────────────────────────┬───────────┘
             │                                              │
             │                                              │
┌────────────▼──────────┐  ┌────────────────────────┐  ┌────▼──────────────┐
│ SUPABASE  SISTEMA     │  │ SUPABASE  APPA         │  │ SUPABASE SOLUCOES │
│ (managed cloud)       │  │ (managed cloud)        │  │ (managed cloud)   │
│                       │  │                        │  │                   │
│ users                 │  │ schema_v1.0.0          │  │ schema_v1.0.0     │
│ empresas_routing      │  │  - explorador_eventos  │  │  - explorador_*   │
│ user_empresas         │  │  - timeline_envio      │  │  - timeline_*     │
│ schema_versions       │  │  - timeline_envio_item │  │  - certificados   │
│ audit_log             │  │  - certificados        │  │  - rubricas       │
│                       │  │  - rubricas            │  │  - s1010_*        │
│                       │  │  - s1010_*             │  │  - pipeline_*     │
│                       │  │  flags={tem_xml:false} │  │  flags={tem_xml:T}│
└───────────────────────┘  └────────────────────────┘  └───────────────────┘

      certs/                     <-- /opt/easy-esocial/certs/
        09445502000109_<serial>.pfx     (perms 600, owner esocial)
        05969071000110_<serial>.pfx
```

---

## 5. Mapa de dependências entre fases

```
F0 (commits)  ─────────────────────────────────────────────► (independente)

F1 (limpeza V2) ──► F2 (schema único)
                       │
                       ▼
                    F3 (multi-tenant runtime) ──► F4 (auth + cert)
                                                     │
                                                     ▼
                                                  F5 (Supabase provision)
                                                     │
                                                     ▼
                                       ┌─────────────┴─────────────┐
                                       ▼                           ▼
                                    F6 (ETL APPA)             F7 (mover Soluções)
                                       │                           │
                                       └─────────┬─────────────────┘
                                                 ▼
                                              F8 (port funcs faltantes)
                                                 │
                                                 ▼
                                              F9 (frontend conectado)
                                                 │
                                                 ▼
                                              F10 (deploy VPS subdomain)
                                                 │
                                                 ▼
                                              F11 (cutover + arquivar V1)
```

---

## Fase 0 — Salvamento (HOJE)

> **Bloqueador absoluto.** Se HD do PC1 morrer agora, perde-se `envio_paralelo_v2.py` + fix `_gerar_id` + Liquid Glass. **Não pode ficar pra amanhã.**

### Checklist

```
[ ] 0.1  Reforçar Easy-eSocial-v2/backend/.gitignore
         Bloquear: .env, *.pfx, *.p12, _*.py, _*.log, _*.txt, __pycache__/
[ ] 0.2  Easy-eSocial-v2: git add backend/app backend/migrations backend/requirements.txt
                        backend/README.md backend/.gitignore backend/.env.example
[ ] 0.3  Easy-eSocial-v2: git add src/ public/ index.html package.json tsconfig.json
                        vite.config.ts .env.example .gitignore SECURITY.md
                        "md norte solucoes/" docs/ scripts/
[ ] 0.4  Easy-eSocial-v2: git commit -m "feat(v2): salvamento pré-migração — backend + frontend completos"
[ ] 0.5  Easy-eSocial-v2: git push origin main (autorizado pelo dono)
[ ] 0.6  Easy-Social: git add "Solucoes Dia 2/" + arquivos .md tocados hoje
[ ] 0.7  Easy-Social: git commit -m "docs: inventário V1 + bíblia V2 + pattern cert Real Prev"
[ ] 0.8  Easy-Social: git push origin main (autorizado pelo dono)
```

> **Risco se não fizer**: 4-6 meses de trabalho fora do controle de versão. Crítico.

> **Tempo estimado**: 20 min se autorização vem rápido.

---

## Fase 1 — Limpeza V2

> Antes de adicionar coisa nova, tirar o lixo pra não levar ele junto pro Supabase/VPS.

### Tarefas

| # | Ação | Comando |
|---|---|---|
| 1.1 | Mover todos `_*.py` e `_*.log` da raiz `backend/` pra `backend/_archive/` | `mkdir _archive ; mv _*.py _*.log _*.txt _*.err _archive/` |
| 1.2 | Adicionar `_archive/` ao `.gitignore` | edit |
| 1.3 | Auditar `backend/app/` — qual file é vivo, qual é zombie? | leitura + lista |
| 1.4 | Apagar `envio_v1*.{log,err}` da raiz (são logs antigos, não código) | rm |
| 1.5 | Confirmar `migrations/001..004` aplicáveis ao Supabase puro (sem psql `\d` etc.) | review |
| 1.6 | Remover `backend/app/envio_teste_100.py` se obsoleto | review + rm |
| 1.7 | Frontend: rodar `npm run build` localmente — confirmar que builda sem erro | `npm run build` |
| 1.8 | Frontend: deletar pastas `dist/` antes de commit | rm |

### Critério de pronto
- `git status` mostra só código vivo + docs.
- Build front roda sem warning.

---

## Fase 2 — Schema único + Sistema DB

> Consolidar as 4 migrations em **um arquivo SQL versionado** + criar DDL do Sistema DB.

### Estrutura proposta

```
Easy-eSocial-v2/backend/migrations/
├── sistema/
│   └── sistema_v1.0.0.sql        (users, empresas_routing, user_empresas, audit)
├── empresa/
│   └── empresa_v1.0.0.sql        (consolida 001+002+003+004 + tabela certificados)
└── README.md                      (como rodar)
```

### Conteúdo `empresa_v1.0.0.sql` (resumo)

- `explorador_eventos` (com `xml_oid` lobject)
- `explorador_atividade`
- `explorador_importacoes`
- `empresa_zips_brutos`
- `timeline_mes`
- `timeline_envio`
- `timeline_envio_item`
- `pipeline_cpf_results`
- `s1010_*`
- `rubricas`, `naturezas`
- **NOVO** `certificados` (DDL do Real Prev — ver `UPLOAD_CERT_A1_REALPREV.md` §3)

### Conteúdo `sistema_v1.0.0.sql`

```sql
CREATE TABLE users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,           -- bcrypt compat V1
  nome TEXT,
  ativo BOOLEAN DEFAULT TRUE,
  super_admin BOOLEAN DEFAULT FALSE,
  criado_em TIMESTAMPTZ DEFAULT NOW(),
  ultimo_login TIMESTAMPTZ
);

CREATE TABLE empresas_routing (
  cnpj TEXT PRIMARY KEY CHECK (length(cnpj)=14),
  razao_social TEXT NOT NULL,
  db_url TEXT NOT NULL,                  -- conn string Supabase
  schema_version TEXT NOT NULL,
  flags JSONB DEFAULT '{}',
  ativo BOOLEAN DEFAULT TRUE,
  criado_em TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE user_empresas (
  user_id UUID REFERENCES users(id) ON DELETE CASCADE,
  cnpj TEXT REFERENCES empresas_routing(cnpj) ON DELETE CASCADE,
  papel TEXT NOT NULL CHECK (papel IN ('admin','operador','leitor')),
  PRIMARY KEY (user_id, cnpj)
);

CREATE TABLE audit_log (
  id BIGSERIAL PRIMARY KEY,
  ts TIMESTAMPTZ DEFAULT NOW(),
  user_id UUID,
  cnpj TEXT,
  acao TEXT,
  ip TEXT,
  detalhes JSONB
);

CREATE INDEX idx_audit_ts ON audit_log(ts DESC);
CREATE INDEX idx_audit_cnpj ON audit_log(cnpj, ts DESC);
```

### Migration runner — `app/migrate.py` (adaptar o que já existe)

```bash
python -m app.migrate apply --target sistema --version 1.0.0
python -m app.migrate apply --target empresa --version 1.0.0 --cnpj 09445502000109
python -m app.migrate apply --target empresa --version 1.0.0 --all   # todas
python -m app.migrate status
```

### Critério de pronto
- 2 SQLs versionados existem.
- Migration runner aplica em DB local de teste sem erro.
- `status` mostra versão correta em cada DB.

---

## Fase 3 — Multi-tenant runtime

### Arquivos a criar/atualizar em `backend/app/`

| Arquivo | Função |
|---|---|
| `sistema_db.py` | conexão pool **só** ao Sistema DB; queries de routing |
| `tenant.py` (já existe — auditar) | pool por empresa + `empresa_conn(cnpj)` context manager |
| `middlewares.py` | auth_middleware + tenant_middleware |
| `auth.py` | JWT encode/decode + `get_current_user` Depends |

### Esqueleto

```python
# backend/app/sistema_db.py
import os, psycopg2
from psycopg2.pool import ThreadedConnectionPool
from contextlib import contextmanager

_pool = ThreadedConnectionPool(1, 5, os.environ["SISTEMA_DB_URL"])

@contextmanager
def sistema_conn():
    c = _pool.getconn()
    try: yield c
    finally: _pool.putconn(c)

def fetch_routing(cnpj: str) -> dict | None:
    with sistema_conn() as c, c.cursor() as cur:
        cur.execute("SELECT cnpj,razao_social,db_url,schema_version,flags,ativo "
                    "FROM empresas_routing WHERE cnpj=%s", (cnpj,))
        row = cur.fetchone()
        if not row: return None
        cols = ['cnpj','razao_social','db_url','schema_version','flags','ativo']
        return dict(zip(cols, row))

def list_empresas() -> list[dict]:
    with sistema_conn() as c, c.cursor() as cur:
        cur.execute("SELECT cnpj FROM empresas_routing WHERE ativo=TRUE")
        return [{'cnpj': r[0]} for r in cur.fetchall()]
```

```python
# backend/app/tenant.py
import psycopg2
from psycopg2.pool import ThreadedConnectionPool
from contextlib import contextmanager
from .sistema_db import fetch_routing

_pools: dict[str, ThreadedConnectionPool] = {}

def get_pool(cnpj: str) -> ThreadedConnectionPool:
    if cnpj not in _pools:
        rota = fetch_routing(cnpj)
        if not rota or not rota['ativo']:
            raise PermissionError(f"empresa {cnpj} indisponível")
        _pools[cnpj] = ThreadedConnectionPool(1, 10, rota['db_url'])
    return _pools[cnpj]

@contextmanager
def empresa_conn(cnpj: str):
    pool = get_pool(cnpj)
    c = pool.getconn()
    try: yield c
    finally: pool.putconn(c)
```

```python
# backend/app/middlewares.py
from fastapi import Request, HTTPException
from .auth import decode_jwt

async def auth_middleware(request: Request, call_next):
    if request.url.path.startswith(("/api/auth/", "/api/healthz")):
        return await call_next(request)
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "missing token")
    try:
        payload = decode_jwt(auth.removeprefix("Bearer ").strip())
    except Exception:
        raise HTTPException(401, "invalid token")
    request.state.user = payload   # {id, email, empresas: [...], super_admin}
    return await call_next(request)

async def tenant_middleware(request: Request, call_next):
    cnpj = request.headers.get("X-Empresa-CNPJ")
    user = getattr(request.state, "user", None)
    if cnpj and user and not user.get("super_admin"):
        if cnpj not in user.get("empresas", []):
            raise HTTPException(403, "sem permissão nesta empresa")
    request.state.cnpj_ativo = cnpj
    return await call_next(request)
```

### Critério de pronto
- `curl -H "Authorization: Bearer <jwt>" -H "X-Empresa-CNPJ: 09445502000109" /api/explorador/eventos` funciona.
- Sem JWT → 401. JWT válido + CNPJ não permitido → 403.

---

## Fase 4 — Auth + Upload Cert A1

> Usa `UPLOAD_CERT_A1_REALPREV.md` integralmente. Aqui só lista a sequência.

### 4.A — Auth

| # | Tarefa |
|---|---|
| 4.A.1 | `pip install pyjwt[crypto] passlib[bcrypt] python-multipart` |
| 4.A.2 | `app/auth.py`: `hash_password`, `verify_password`, `encode_jwt`, `decode_jwt`, `get_current_user` |
| 4.A.3 | `app/auth_routes.py`: `POST /api/auth/login` → retorna `{token, empresas:[{cnpj,razao,papel}]}` |
| 4.A.4 | Seed: 1 super_admin + 1 user APPA + 1 user Soluções no Sistema DB |
| 4.A.5 | Teste: login retorna token, token decodifica, lista empresas correta |

### 4.B — Cert A1 (porta do Real Prev)

| # | Tarefa |
|---|---|
| 4.B.1 | `pip install cryptography signxml lxml` (signxml é o que falta) |
| 4.B.2 | Copiar `Projeto/python-backend/esocial/certificate_manager.py` → `app/certificate_manager.py` (sem mudança) |
| 4.B.3 | Copiar `certificate_extractor.py` → `app/certificate_extractor.py` |
| 4.B.4 | **Substituir** `app/xml_signer.py` atual pelo do Real Prev |
| 4.B.5 | Criar `app/cert_routes.py` com 6 endpoints (extrair de `Projeto/main.py` 9465-9831) |
| 4.B.6 | Adaptar pra usar `empresa_conn()` ao invés de session global |
| 4.B.7 | Mover chave Fernet pra `os.environ['FERNET_KEY']` (default = chave Real Prev pra compat) |
| 4.B.8 | Refatorar `envio_paralelo_v2.py`: substituir flag `--cert/--senha` por busca via DB:

```python
cert = select_active_certificate(empresa_db, current_user)
senha = CertificateManager.decrypt_password(cert.senha_encrypted)
cert_path = cert.arquivo_path
```

### Critério de pronto
- `POST /api/certificado/upload` aceita PFX + senha, valida, salva, registra em `certificados`.
- `GET /api/certificado/ativo` retorna o cert ativo do tenant ativo.
- `envio_paralelo_v2 --per-apur 2025-08 --limite 10` (sem `--cert`/`--senha`) funciona usando cert do DB.

---

## Fase 5 — Provisionar Supabase APPA + Soluções

> **Pré-requisito**: P1, P2 respondidos.

| # | Ação |
|---|---|
| 5.1 | Criar projeto Supabase `easy-esocial-sistema` (região São Paulo) |
| 5.2 | Criar projeto Supabase `easy-esocial-appa` |
| 5.3 | Criar projeto Supabase `easy-esocial-solucoes` |
| 5.4 | Anotar `db_url` (com pooler 6543) de cada um em `.env` local |
| 5.5 | Aplicar `sistema_v1.0.0.sql` no Sistema DB |
| 5.6 | Aplicar `empresa_v1.0.0.sql` no APPA DB |
| 5.7 | Aplicar `empresa_v1.0.0.sql` no Soluções DB |
| 5.8 | Inserir registros em `empresas_routing`:
```sql
INSERT INTO empresas_routing (cnpj, razao_social, db_url, schema_version, flags) VALUES
('05969071000110', 'APPA SERVICOS TEMPORARIOS LTDA',
 'postgresql://...', '1.0.0',
 '{"tem_xml_completo": false, "origem":"v1_legado"}'),
('09445502000109', 'SOLUCOES SERVICOS TERCEIRIZADOS LTDA',
 'postgresql://...', '1.0.0',
 '{"tem_xml_completo": true, "origem":"v2_nativo"}');
```
| 5.9 | Smoke test do migration runner: `python -m app.migrate status` mostra ambos como 1.0.0 |

---

## Fase 6 — ETL APPA V1→Supabase

> **Crítico**: APPA tem 110.651 CPFs históricos. Não pode perder linha.

### Estratégia

```
PC2: pg_dump easy_social_db (V1 APPA)
  → arquivo appa_v1_dump_2026-05-08.sql.gz (2 cópias)
  → sftp pra PC1 + cloud backup

PC1: psql restore em DB temporário appa_v1_replica
  → audit: COUNT(*) por tabela
  → audit: COUNT(DISTINCT cpf, per_apur) em s1210_cpf_envios

ETL: backend/scripts/etl_appa_v1_to_v2.py
  → lê appa_v1_replica
  → escreve Supabase APPA via psycopg2 batch 5000

Reconciliação:
  → COUNT por tabela origem vs destino
  → Histograma erro_codigo por per_apur
  → 5 CPFs random: snapshot side-by-side
```

### Mapping V1 → V2 (resumo, detalhe na Phase 6 da MIGRACAO)

| V1 | V2 | Transformação |
|---|---|---|
| `s1210_cpf_envios` (218k linhas) | `timeline_envio_item` (HEAD) + `historico_tentativas_cpf` (full) | DISTINCT ON (cpf, per_apur) ORDER BY enviado_em DESC |
| `s1210_cpf_scope` | `pipeline_cpf_results` | direto |
| `users` | Sistema DB `users` | manter `password_hash` bcrypt |
| `master_empresas` | Sistema DB `empresas_routing` | já fazendo |
| `rubricas`, `naturezas` | idem no APPA DB | direto |
| `s1010_*` | idem | direto |
| (não tem XML por evento) | `explorador_eventos` com `xml_oid=NULL` | popula só metadados |
| `ARQUIVOS_RETORNO/2025-1[0-2]/*.xml` | `explorador_eventos.xml_oid` (parsed) | parse + lobject |

### Critério de pronto
- Reconciliação 100% (ou divergências documentadas e aceitas).
- Rafa abre 5 CPFs de meses diferentes, batem com V1.

---

## Fase 7 — Migrar Soluções local→Supabase

> Hoje Soluções vive em `easy_social_solucoes` Postgres local PC1 (2.8 GB). Move pro Supabase.

| # | Ação |
|---|---|
| 7.1 | `pg_dump --format=custom -d easy_social_solucoes -f solucoes_local.dump` |
| 7.2 | `pg_restore -d <supabase-solucoes-url> solucoes_local.dump` |
| 7.3 | Validar contagens: 184.769 explorador_eventos, 16.103 timeline_envio_item, 162 timeline_envio |
| 7.4 | Apontar `.env` SOLUCOES_DB_URL pro Supabase |
| 7.5 | Smoke: rodar `envio_paralelo_v2 --limite 5` apontando pro Supabase Soluções |

---

## Fase 8 — Funcionalidades faltantes (auth UI, upload XLSX, validação)

Portar do V1 Node → V2 Python:

| # | Funcionalidade | V1 origem | V2 destino |
|---|---|---|---|
| 8.1 | Upload XLSX Domínio | `Easy-Social/backend/src/routes/uploadRoutes.ts` | `app/upload_dominio.py` (openpyxl) |
| 8.2 | Validação rubrica | `services/rubrica-validation-service.ts` | `app/validacao_rubrica.py` |
| 8.3 | Validação natureza | `services/natureza-validation-service.ts` | `app/validacao_natureza.py` |
| 8.4 | Cruzamento contábil | `cruzamentoRoutes.ts` | `app/cruzamento.py` |
| 8.5 | Tabelas mestras (S-1000/1005/1010) | `tableRoutes.ts` | auditar `app/explorador.py` |
| 8.6 | Auth UI seed | manual | `scripts/seed_users.py` |

> **Cada item = 1 PR isolado**. Não misturar.

---

## Fase 9 — Frontend conectado

| # | Tarefa |
|---|---|
| 9.1 | `src/services/api.ts`: axios instance com interceptor (Authorization + X-Empresa-CNPJ) |
| 9.2 | `src/stores/auth.ts`: Pinia, salva token + empresas em localStorage |
| 9.3 | `src/stores/empresa.ts`: empresa ativa |
| 9.4 | `src/views/LoginView.vue`: form, chama `/api/auth/login` |
| 9.5 | `src/views/EmpresaSelectView.vue`: cards (P6) com razão social + badge de status |
| 9.6 | Router guard: sem token → /login. Sem empresa selecionada → /empresas |
| 9.7 | `src/components/CertificadoUpload.vue` (ver `UPLOAD_CERT_A1_REALPREV.md` §6) |
| 9.8 | `src/views/ConfigCertificado.vue`: usa upload + lista atual + delete |
| 9.9 | Apontar todos os services pra `/api/*` (proxy via Vite dev) |
| 9.10 | Build prod: `npm run build` → `dist/` |

### Critério de pronto
- Login funciona em `localhost:5173`.
- Seleção empresa muda header automaticamente.
- Explorador carrega dados do Supabase certo.
- Upload cert funciona via UI.

---

## Fase 10 — Deploy VPS

> Subdomain `v2.easyesocial.com.br` paralelo. **V1 continua online em `easyesocial.com.br`.**

### Provisionamento

```
/opt/easy-esocial/
├── backend/
│   ├── .venv/
│   ├── app/                  ← git pull
│   ├── migrations/
│   └── .env                  ← prod, perms 600
├── frontend-dist/            ← scp ou git pull + build
├── certs/                    ← perms 600, owner esocial
└── logs/
```

### systemd `easy-esocial.service`

```ini
[Unit]
Description=Easy eSocial V2
After=network.target

[Service]
Type=simple
User=esocial
WorkingDirectory=/opt/easy-esocial/backend
EnvironmentFile=/opt/easy-esocial/backend/.env
ExecStart=/opt/easy-esocial/backend/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8001 --workers 2
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### Nginx `v2.easyesocial.com.br`

```nginx
server {
  listen 443 ssl http2;
  server_name v2.easyesocial.com.br;
  ssl_certificate /etc/letsencrypt/live/v2.easyesocial.com.br/fullchain.pem;
  ssl_certificate_key /etc/letsencrypt/live/v2.easyesocial.com.br/privkey.pem;

  client_max_body_size 50M;

  root /opt/easy-esocial/frontend-dist;
  index index.html;
  location / { try_files $uri $uri/ /index.html; }

  location /api/ {
    proxy_pass http://127.0.0.1:8001/api/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_read_timeout 300;
  }

  # rate limit upload cert
  location /api/certificado/upload {
    limit_req zone=cert_upload burst=3 nodelay;
    proxy_pass http://127.0.0.1:8001/api/certificado/upload;
  }
}
```

### Critério de pronto
- `https://v2.easyesocial.com.br` carrega login.
- Rafa loga, vê APPA, abre Explorador, vê 110k CPFs.
- Soluções loga, faz envio S-1210 de teste (limite 5) em homologação.

---

## Fase 11 — Cutover + aposentadoria V1

> **Janela mínima de 7 dias** com V2 em `v2.` paralelo antes de derrubar V1.

| Dia | Ação |
|---|---|
| D0 | Anúncio Rafa+Ana: usar V2 em paralelo, reportar bugs |
| D+3 | Review bugs reportados — fix |
| D+5 | Smoke test final |
| D+7 | Apontar DNS `easyesocial.com.br` → mesma VPS, mesmo Nginx, agora servindo V2 |
| D+7 | V1 systemd `stop` + `disable` |
| D+8 | V1 repo GitHub → archived |
| D+30 | Backup final V1 DB → S3 frio |
| D+30 | Drop DB V1 do Postgres do VPS |

### Critério de pronto
- DNS aponta pra V2.
- V1 process não responde.
- Rafa fechou pelo menos 1 mês inteiro pelo V2.

---

## Anexo A — Estrutura de pastas alvo do V2

```
Easy-eSocial-v2/
├── backend/
│   ├── .env.example
│   ├── .gitignore                     (blindar PFX, .env, _archive)
│   ├── README.md
│   ├── requirements.txt
│   ├── pyproject.toml                 (eventual)
│   ├── _archive/                      (gitignored — scripts one-shot)
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                    (FastAPI app + middleware register)
│   │   ├── config.py
│   │   ├── sistema_db.py              NOVO
│   │   ├── tenant.py                  REFATORADO
│   │   ├── middlewares.py             NOVO
│   │   ├── auth.py                    NOVO
│   │   ├── auth_routes.py             NOVO
│   │   ├── certificate_manager.py     NOVO (lift Real Prev)
│   │   ├── certificate_extractor.py   NOVO (lift Real Prev)
│   │   ├── xml_signer.py              SUBSTITUÍDO (Real Prev)
│   │   ├── cert_routes.py             NOVO
│   │   ├── upload_dominio.py          NOVO (porta V1)
│   │   ├── validacao_rubrica.py       NOVO (porta V1)
│   │   ├── validacao_natureza.py      NOVO (porta V1)
│   │   ├── cruzamento.py              NOVO (porta V1)
│   │   ├── envio_paralelo_v2.py       REFATORADO (cert via DB)
│   │   ├── envio_s1298.py
│   │   ├── esocial_client.py
│   │   ├── esocial_parser.py
│   │   ├── explorador.py
│   │   ├── timeline.py
│   │   ├── storage.py
│   │   ├── backfill_chain.py
│   │   ├── backfill_xml.py
│   │   ├── reprocessar_envio.py
│   │   ├── xml_extractor.py
│   │   ├── xml_s1210.py
│   │   ├── xml_s1298.py
│   │   ├── xml_diff.py
│   │   ├── db.py
│   │   └── migrate.py
│   ├── migrations/
│   │   ├── README.md
│   │   ├── sistema/
│   │   │   └── sistema_v1.0.0.sql
│   │   └── empresa/
│   │       └── empresa_v1.0.0.sql
│   └── scripts/
│       ├── seed_users.py
│       └── etl_appa_v1_to_v2.py
├── src/                               (Vue 3 — mesmo de hoje + novos componentes)
│   ├── App.vue
│   ├── main.ts
│   ├── router/
│   ├── stores/
│   │   ├── auth.ts                    NOVO
│   │   └── empresa.ts                 NOVO
│   ├── services/
│   │   └── api.ts                     REFATORADO (interceptor)
│   ├── views/
│   │   ├── LoginView.vue              NOVO
│   │   ├── EmpresaSelectView.vue      EXISTE — terminar
│   │   ├── ConfigCertificado.vue      NOVO
│   │   ├── ExploradorView.vue
│   │   ├── S1210AnualView.vue
│   │   └── S1210MesView.vue
│   ├── components/
│   │   └── CertificadoUpload.vue      NOVO
│   └── ...
├── public/
├── package.json, vite.config.ts, tsconfig.json
├── README.md, SECURITY.md, .env.example, .gitignore
└── docs/
```

---

## Anexo B — Variáveis de ambiente

```ini
# Easy-eSocial-v2/backend/.env  (perms 600 em produção)

# Sistema
SISTEMA_DB_URL=postgresql://user:pass@db.supabase.co:6543/postgres

# JWT
JWT_SECRET=<32 bytes random>
JWT_TTL_HOURS=12

# Cert encryption
FERNET_KEY=VeO-WGEJAv51ZXFdGO0MV06Bl2lI1XkYMiqV_WOpy_g=   # default Real Prev (compat)
                                                          # rotacionar depois de Phase 11

# eSocial
ESOCIAL_AMBIENTE=producao
ESOCIAL_URL_ENVIAR=https://webservices.efdreinf.esocial.gov.br/...
ESOCIAL_URL_CONSULTAR=https://webservices.efdreinf.esocial.gov.br/...

# Storage
CERT_BASE_DIR=/opt/easy-esocial/certs
XML_FRIO_S3_BUCKET=easy-esocial-xml-frio
XML_FRIO_S3_KEY=...
XML_FRIO_S3_SECRET=...

# Logs
LOG_LEVEL=INFO
LOG_JSON=true
```

---

## Anexo C — Comandos prontos

### Aplicar schema em todos os bancos

```bash
cd Easy-eSocial-v2/backend
python -m app.migrate apply --target sistema --version 1.0.0
python -m app.migrate apply --target empresa --version 1.0.0 --all
python -m app.migrate status
```

### Seed de usuários

```bash
python scripts/seed_users.py \
  --email rafa@appa.com.br --senha-bcrypt-v1 '<hash>' \
  --empresas 05969071000110 \
  --papel operador
```

### Subir backend local

```bash
cd Easy-eSocial-v2/backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --port 8001
```

### Subir frontend local

```bash
cd Easy-eSocial-v2
npm run dev
# http://localhost:5173 → proxied /api → :8001
```

### Backup APPA antes de migração

```powershell
# no PC2, com Postgres APPA vivo
pg_dump -h localhost -p 5432 -U postgres -d easy_social_db `
        --format=custom --no-owner --no-acl `
        -f appa_v1_pre_migracao_2026-05-08.dump
# copiar pra pendrive + cloud
```

---

## Anexo D — Critérios de "pronto"

### Pronto pra Phase 5 (provisionar Supabase)
- [ ] Phase 0 ✅
- [ ] Phase 1 ✅ (V2 limpo)
- [ ] Phase 2 ✅ (schemas SQL versionados)
- [ ] Phase 3 ✅ (multi-tenant runtime testado em DB local)
- [ ] Phase 4 ✅ (auth + cert testados em DB local)
- [ ] P1, P2, P5 respondidos

### Pronto pra Phase 10 (deploy)
- [ ] Phase 5 ✅ (3 Supabase ativos)
- [ ] Phase 6 ✅ (APPA reconciliada)
- [ ] Phase 7 ✅ (Soluções migrada)
- [ ] Phase 8 ✅ (funcs portadas)
- [ ] Phase 9 ✅ (frontend funcionando)
- [ ] Smoke test local end-to-end

### Pronto pra Phase 11 (cutover)
- [ ] Phase 10 ✅
- [ ] 7 dias paralelo sem bugs P1
- [ ] Rafa autorizou
- [ ] Backup V1 final feito

---

## Regras de ouro

1. **Não toca git sem autorização.** Phase 0 só executa quando o dono falar "vai".
2. **Não consulta eSocial sem permissão explícita.** Cota 10/dia compartilhada entre todas as APIs de download.
3. **Não usa `explorador_eventos` como fonte de recibo.** Usa ZIP baixado ou `pipeline_cpf_results`.
4. **Não inventa nome de pessoa.** Só "Ana", "Sandro", "operador", "dono", "Rafa" se confirmado em memória.
5. **Não comita `.pfx`, `.env`, ou senha em qualquer file.** `.gitignore` blindado antes de qualquer add.
6. **PFX em `_certificados_locais/` (PC1) ou `/opt/easy-esocial/certs/` (VPS), nunca em git.**
7. **Senha cert em DB sempre Fernet-criptografada, nunca plaintext, nunca SHA256.**
8. **URI vazio na assinatura XMLDSig**, sempre. Erro 142 SERPRO se esquecer.
9. **`Id` maiúsculo no atributo do evento eSocial**, sempre.
10. **Schema migration roda em todos os bancos da empresa, ou aborta.** Nada de "metade aplicado".
11. **V1 fica online até cutover validado**. Reversível até D+30.
12. **Cada Phase tem critério de pronto.** Se não atende, não passa.

---

## Quando começar?

```
[ ]  AGORA: Phase 0 (commit) — autorizo? ⌛
[ ]  HOJE/AMANHÃ: Phase 1 (limpeza V2)
[ ]  SEMANA: Phase 2 + 3 + 4 (em paralelo onde possível)
[ ]  Decisão P1+P2+P5 → Phase 5 (provisionar Supabase)
[ ]  Phase 6 + 7 em paralelo
[ ]  Phase 8 (porta V1) — pode começar antes do Supabase
[ ]  Phase 9 (frontend) — pode começar com mocks
[ ]  Phase 10 (deploy subdomain v2.)
[ ]  Phase 11 (cutover)
```

> **Próximo passo concreto neste momento**: aguardar autorização do dono pra **Phase 0** (commits). Sem isso, nada anda.

---

## Documentos relacionados nesta pasta

| Doc | Função |
|---|---|
| [`INVENTARIO_V1_PRE_MIGRACAO.md`](./INVENTARIO_V1_PRE_MIGRACAO.md) | o que existe no PC1 hoje |
| [`MIGRACAO_V1_V2.md`](./MIGRACAO_V1_V2.md) | missão de migrar V1→V2 (visão narrativa) |
| [`ARQUITETURA_MULTI_EMPRESA.md`](./ARQUITETURA_MULTI_EMPRESA.md) | detalhe técnico multi-DB |
| [`UPLOAD_CERT_A1_REALPREV.md`](./UPLOAD_CERT_A1_REALPREV.md) | pattern cert A1 do Real Prev |
| [`ciclo100.md`](./ciclo100.md) | técnica de envio massivo já validada |
| **`BIBLIA_V2_NORTE.md`** (este) | **plano operacional executável — começa por aqui** |
