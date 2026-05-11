# Arquitetura Multi-Tenant — Easy-eSocial V2

> **Documento de referência.** Última atualização: 11/05/2026.
> Fonte: código real em produção (`backend/app/tenant.py`, `backend/app/sistema_db.py`, `backend/app/config.py`, `backend/migrations/`) + estado atual do banco (consulta SSH a `76.13.169.45`, schemas `sistema`/`appa`/`solucoes`).
>
> Este documento responde às perguntas:
>
> 1. Quantas empresas temos hoje?
> 2. Quantos bancos diferentes no Supabase usamos?
> 3. Como funciona o backend?
> 4. O sistema tem um banco por empresa?
> 5. O sistema tem um banco que recebe novas empresas?
> 6. Se chegarem 10 empresas novas, como elas são alocadas?
> 7. Existe padrão para importar empresas?
> 8. Como uma empresa nova entra no sistema (passo a passo)?

---

## TL;DR — resposta direta em 1 minuto

- **2 empresas** ativas hoje: APPA (CNPJ 05969071000110) e SOLUCOES (CNPJ 09445502000109).
- **2 projetos Supabase distintos** (= 2 bancos físicos diferentes na nuvem):
  - **Sistema DB** — `db.kjbgiwnlvqnrfdozjvhq.supabase.co` (database `postgres`, schema `sistema`). Guarda **auth + routing + auditoria**. Nada de dado operacional de empresa.
  - **Dados DB** — `aws-1-us-east-2.pooler.supabase.com` (database `postgres`, schemas `appa`, `solucoes`, `legado`, `public`). Guarda **todos os dados operacionais** das empresas, isolados por **schema PostgreSQL**.
- **NÃO temos 1 banco físico por empresa.** Temos **1 schema PostgreSQL por empresa** dentro do mesmo banco de dados. Isso é o que a Bíblia chama de "modelo F5 — schema-based multi-tenant".
- **Sim, existe banco que recebe novas empresas:** o **Sistema DB** (`empresas_routing`). Cadastrar uma empresa = adicionar uma linha lá + criar um schema novo no Dados DB + rodar a migration `empresa_v1.1.0.sql` apontando para o schema novo.
- **10 empresas novas?** Cabem tranquilo. O custo é 10 schemas + 10 execuções do runner de migration. **Não precisa criar 10 bancos Supabase.** Limite prático: ~50–100 empresas por banco antes de pensar em sharding.
- **Padrão de onboarding existe e está scriptado:** `python -m app.migrate apply --target empresa --version 1.1.0 --schema <slug> --dsn <DSN>`. Falta automação web (botão no admin) — hoje é manual via terminal.

---

## 1. Panorama geral

### 1.1. Modelo em vigor: **tenant por schema**

```
┌──────────────────────────────────────────────────────────────────────┐
│                          FRONTEND V2 (Vue 3)                          │
│                                                                       │
│  Login → JWT { user_id, empresas: [cnpj1, cnpj2, ...] }              │
│  Toda request: Authorization: Bearer <jwt>  +  X-Empresa-CNPJ: <cnpj>│
└────────────────────────────┬─────────────────────────────────────────┘
                             │
┌────────────────────────────▼─────────────────────────────────────────┐
│                       BACKEND V2 (FastAPI)                            │
│                                                                       │
│  1) Auth middleware decodifica JWT → user_id                          │
│  2) Resolve X-Empresa-CNPJ → schema_name via empresas_routing         │
│  3) Valida permissão em user_empresas                                 │
│  4) Conexão usa "SET search_path TO <schema>, public"                 │
└──────────┬────────────────────────────────┬──────────────────────────┘
           │                                │
           │ SISTEMA_DB_URL                 │ SUPABASE_DB_*  + search_path
           │                                │
┌──────────▼──────────────┐    ┌────────────▼─────────────────────────┐
│   SUPABASE "SISTEMA"    │    │   SUPABASE "DADOS"                    │
│   db.kjbgiwnlvqnrfdozj. │    │   aws-1-us-east-2.pooler.supabase.com │
│   supabase.co           │    │                                        │
│                         │    │                                        │
│   database: postgres    │    │   database: postgres                   │
│   schema:   sistema     │    │                                        │
│                         │    │   schema: appa       (APPA)            │
│   ─ users               │    │   schema: solucoes   (SOLUCOES)        │
│   ─ empresas_routing    │    │   schema: legado     (V1 raw dump)     │
│   ─ user_empresas       │    │   schema: public     (compartilhado:   │
│   ─ audit_log           │    │     s1299_fechamento_status,           │
│   ─ schema_meta         │    │     explorador_eventos legacy, etc.)   │
│                         │    │                                        │
│   ATIVOS:               │    │   Schemas têm AS MESMAS 36 tabelas:    │
│   ─ 2 users             │    │   ─ master_empresas                    │
│     (xandeadmin admin,  │    │   ─ s1210_cpf_envios                   │
│      Ana operador)      │    │   ─ s1210_cpf_scope                    │
│   ─ 2 empresas          │    │   ─ pipeline_cpf_results               │
│     (APPA, SOLUCOES)    │    │   ─ explorador_eventos (...) etc.      │
│   ─ 2 vínculos (Ana →   │    │                                        │
│     APPA + SOLUCOES)    │    │                                        │
└─────────────────────────┘    └────────────────────────────────────────┘
```

### 1.2. Por que dois Supabase diferentes?

A Bíblia define como hipótese ideal "1 banco por empresa". Na prática:

- A **APPA** já existia em produção desde o V1 em um Supabase específico (`aws-1-us-east-2.pooler.supabase.com`, database `postgres`). Migrar 376k linhas de `explorador_eventos` + ZIPs do eSocial para outro projeto era caro e arriscado.
- Quando criamos o **V2**, optamos por:
  - Reaproveitar o banco da APPA como **"Dados DB"** e mover os dados do V1 para o schema `appa`.
  - Importar SOLUCOES (que estava em PostgreSQL local) para o **mesmo banco**, em um schema `solucoes` novo.
  - Criar um **segundo projeto Supabase** só para auth/routing (`db.kjbgiwnlvqnrfdozjvhq.supabase.co`). Esse banco é minúsculo (5 tabelas, ~10 KB) — vive de graça no plano free do Supabase.

Resultado prático: **2 projetos Supabase**, mas funcionalmente **3 "papéis"** de DB:

| Papel       | Onde mora                            | Conteúdo                  |
| ----------- | ------------------------------------ | ------------------------- |
| Sistema     | Supabase "sistema"                   | auth, routing, audit      |
| Tenant APPA | Supabase "dados" → schema `appa`     | dados eSocial da APPA     |
| Tenant SOLU | Supabase "dados" → schema `solucoes` | dados eSocial da SOLUCOES |

---

## 2. Resposta direta às perguntas do usuário

### 2.1. "Quantas empresas temos hoje?"

**2 empresas ativas.**

Consulta real no Sistema DB (executada em 11/05/2026):

```
SELECT cnpj, razao_social, schema_name, schema_version, ativo
  FROM sistema.empresas_routing
 ORDER BY razao_social;

('05969071000110', 'APPA SERVICOS TEMPORARIOS LTDA',   'appa',     '1.1.0', True)
('09445502000109', 'SOLUCOES SERVICOS TERCEIRIZADOS LTDA', 'solucoes', '1.1.0', True)
```

### 2.2. "Quantos bancos no Supabase nós conectamos?"

**2 projetos Supabase distintos** (= 2 hostnames, 2 conexões fundamentalmente diferentes). Configurados em `backend/.env`:

```ini
# Supabase "Dados" (APPA + SOLUCOES por schema)
SUPABASE_DB_HOST=aws-1-us-east-2.pooler.supabase.com
SUPABASE_DB_PORT=5432
SUPABASE_DB_NAME=postgres
SUPABASE_DB_USER=postgres.zpizibafccwsjgvplcum
SUPABASE_DB_PASSWORD=********
SUPABASE_DB_SSL=true

# Supabase "Sistema" (auth + routing) — DSN completo
SISTEMA_DB_URL=postgresql://postgres:********@db.kjbgiwnlvqnrfdozjvhq.supabase.co:5432/postgres?sslmode=require
```

### 2.3. "Como funciona nosso backend?"

Backend é **FastAPI 0.115** + **uvicorn**, rodando como serviço systemd na VPS Hostinger (`/opt/easy-esocial/backend/`, port 8001, atrás do nginx).

Fluxo de uma request típica (`GET /api/s1210-repo/anual/overview?ano=2025&empresa_id=1`):

1. **Nginx** (porta 443, TLS) recebe a request e faz proxy para `127.0.0.1:8001`.
2. **FastAPI middleware** decodifica `Authorization: Bearer <JWT>`. Se inválido → 401.
3. O endpoint chama `tenant.get_db_config_for_empresa(empresa_id=1)`:

   ```python
   # backend/app/tenant.py
   _EMPRESA_SCHEMA = {1: "appa", 2: "solucoes"}

   def get_db_config_for_empresa(empresa_id):
       schema = _EMPRESA_SCHEMA.get(empresa_id, "public")
       cfg = dict(config.SUPABASE_DB_CONFIG)
       cfg["options"] = f"-csearch_path={schema},public"
       return cfg
   ```

   Isto retorna uma cópia do dict de conexão Supabase com `options=-csearch_path=appa,public` injetado. Toda query rodada nessa conexão resolve tabelas sem qualificador no schema da empresa.

4. Para rotas novas (F5, multi-tenant por CNPJ), o caminho preferido é:

   ```python
   # backend/app/tenant.py
   @contextmanager
   def empresa_conn(cnpj: str):
       schema = get_schema_for_cnpj(cnpj)   # consulta sistema.empresas_routing
       pool = sistema_db._ensure_pool()
       conn = pool.getconn()
       try:
           with conn.cursor() as cur:
               cur.execute(f'SET search_path TO "{schema}", public')
           yield conn
       finally:
           with conn.cursor() as cur:
               cur.execute("RESET search_path")
           pool.putconn(conn)
   ```

   Diferenças da API legada (`empresa_id`) para a nova (`cnpj`):

   | Item            | API legada                                  | API nova (F5)                                     |
   | --------------- | ------------------------------------------- | ------------------------------------------------- |
   | Identificador   | `empresa_id` (1=APPA, 2=SOLU)               | CNPJ (14 dígitos)                                 |
   | Resolução       | hard-coded em `_EMPRESA_SCHEMA`             | dinâmica via `empresas_routing`                   |
   | Pool de conexão | conexão nova por request (psycopg2.connect) | pool compartilhado (ThreadedConnectionPool 2..20) |
   | Header HTTP     | query param `empresa_id`                    | header `X-Empresa-CNPJ`                           |
   | Permissão       | implícita (vem do JWT)                      | checada em `user_empresas`                        |

5. O endpoint executa as queries no DB e devolve JSON.

### 2.4. "O sistema tem um banco para cada empresa?"

**Não.** Tem **1 schema PostgreSQL por empresa**, todos dentro do **mesmo banco de dados** ("Dados DB").

Por que escolhemos schema em vez de "1 banco por empresa"?

| Critério                 | 1 banco / empresa             | 1 schema / empresa (escolhido)   |
| ------------------------ | ----------------------------- | -------------------------------- |
| Isolamento físico        | Máximo                        | Forte (search_path + permissões) |
| Backup independente      | Trivial (pg_dump por DB)      | Trabalhoso (filtro por schema)   |
| Conexões / pools         | N pools (1 por empresa)       | 1 pool compartilhado             |
| Custo Supabase           | N projetos (cada um $25+/mês) | 1 projeto                        |
| Migração de schema (DDL) | Aplicar em N bancos           | Aplicar em N schemas (1 conexão) |
| Limite prático           | Centenas                      | Dezenas a centena                |
| LGPD                     | Excelente                     | Bom (RLS + search_path)          |

A escolha é **schema-based** porque:

- O custo do Supabase explode rapidamente com 1 projeto por empresa.
- A volumetria do eSocial é alta (centenas de milhares de XMLs por ano por empresa), mas cabe em 1 Postgres bem dimensionado por muito tempo.
- Migrações de schema (adicionar coluna, tabela, índice) podem ser rodadas via runner único em loop por schema, sem múltiplas conexões.

### 2.5. "Tem um banco que recebe novas empresas?"

**Sim — o Sistema DB.** Especificamente a tabela `sistema.empresas_routing`:

```sql
CREATE TABLE IF NOT EXISTS empresas_routing (
    cnpj            TEXT PRIMARY KEY CHECK (length(cnpj) = 14),
    razao_social    TEXT NOT NULL,
    schema_name     VARCHAR(63) NOT NULL UNIQUE
                    CHECK (schema_name ~ '^[a-z][a-z0-9_]{0,62}$'),
    schema_version  TEXT NOT NULL,
    flags           JSONB NOT NULL DEFAULT '{}'::jsonb,
    ativo           BOOLEAN NOT NULL DEFAULT TRUE,
    criado_em       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    atualizado_em   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

É a **fonte da verdade**: backend lê dali pra saber em que schema procurar os dados de cada CNPJ.

Quando o backend recebe uma request com `X-Empresa-CNPJ: 12345678000199`, a função `tenant.get_schema_for_cnpj(cnpj)` faz:

```python
SELECT schema_name FROM sistema.empresas_routing WHERE cnpj = '12345678000199'
```

Se devolver `'cliente_x'`, o backend faz `SET search_path TO cliente_x, public` na conexão e segue como se nada tivesse mudado.

### 2.6. "Se chegassem 10 empresas, o sistema alocaria automaticamente?"

**Hoje: NÃO 100% automático.** O fluxo é semi-manual:

1. Operador (super_admin) executa um comando para criar o schema da empresa no Dados DB.
2. Operador roda o migration runner para criar as 36 tabelas no schema novo.
3. Operador insere a linha em `empresas_routing` + vincula usuários em `user_empresas`.

**Custo por empresa nova:** ~30 segundos de comandos. Os scripts existem; falta UI no admin para fazer isso por botão.

**Capacidade:** 10 empresas novas cabem sem ajuste de infra. Cada schema ocupa ~50 MB inicialmente (vazio). O Supabase Pro suporta facilmente 50+ empresas no mesmo banco se cada uma tiver volume APPA-like (375k eventos no `explorador_eventos`).

### 2.7. "Existe padrão para importação de empresas?"

**Sim.** Documentado em [`backend/migrations/README.md`](../backend/migrations/README.md). Veja seção 3 deste documento para o passo a passo completo.

### 2.8. "Como empresas novas entram?"

Veja seção **3 — Onboarding de empresa nova** abaixo.

---

## 3. Onboarding de empresa nova — passo a passo

### 3.1. Pré-requisitos

- Acesso SSH na VPS (`root@76.13.169.45`).
- Variáveis `.env` no backend contêm `SUPABASE_DB_*` (admin do Dados DB) e `SISTEMA_DB_URL`.
- O `schema_name` escolhido deve casar com a regex `^[a-z][a-z0-9_]{0,62}$`. Por convenção, usar a **razão social abreviada em minúsculo, sem espaços** (ex.: `appa`, `solucoes`, `acme_corp`).

### 3.2. Passo 1 — Criar o schema vazio no Dados DB

```sql
-- Conectar como admin do Dados DB:
-- psql "host=aws-1-us-east-2.pooler.supabase.com user=postgres.zpizibafccwsjgvplcum dbname=postgres sslmode=require"

CREATE SCHEMA IF NOT EXISTS acme_corp;
GRANT USAGE ON SCHEMA acme_corp TO postgres;
```

### 3.3. Passo 2 — Aplicar a migration `empresa_vX.Y.Z.sql` no schema novo

```powershell
# Na VPS, dentro do venv do backend:
cd /opt/easy-esocial/backend
.venv/bin/python -m app.migrate apply \
    --target empresa \
    --version 1.1.0 \
    --schema acme_corp \
    --dsn "postgresql://postgres.zpizibafccwsjgvplcum:****@aws-1-us-east-2.pooler.supabase.com:5432/postgres?sslmode=require"
```

O runner faz:

1. Lê o arquivo [`backend/migrations/empresa/empresa_v1.1.0.sql`](../backend/migrations/empresa/empresa_v1.1.0.sql).
2. Faz `string replace` de `public.` para `acme_corp.` em todo o SQL (mecânica do schema-based runner).
3. Executa o SQL transformado dentro da conexão com `SET search_path TO acme_corp`.
4. Cria 36 tabelas, índices, sequences, FKs.
5. Insere `INSERT INTO acme_corp.schema_meta (target, version) VALUES ('empresa','1.1.0')`.

**Tempo:** ~5 segundos.

### 3.4. Passo 3 — Cadastrar a empresa em `sistema.empresas_routing`

```sql
-- Conectar no Sistema DB:
-- psql "host=db.kjbgiwnlvqnrfdozjvhq.supabase.co user=postgres dbname=postgres sslmode=require"

INSERT INTO sistema.empresas_routing
    (cnpj, razao_social, schema_name, schema_version, flags, ativo)
VALUES
    ('12345678000199', 'ACME CORPORATION LTDA', 'acme_corp', '1.1.0', '{}'::jsonb, TRUE);
```

### 3.5. Passo 4 — Vincular usuários à empresa

```sql
-- Encontrar o user_id (UUID) do usuário que vai operar a empresa:
SELECT id, email, nome FROM sistema.users WHERE email = 'operador@acme.com';

-- Vincular como operador (papel: admin | operador | leitor):
INSERT INTO sistema.user_empresas (user_id, cnpj, papel)
VALUES ('<UUID do user>', '12345678000199', 'operador');
```

### 3.6. Passo 5 — Validar

Do navegador, logar com o usuário vinculado. A empresa deve aparecer no seletor (dropdown que vem do auth store `empresas: AuthEmpresa[]`).

Toda request a partir daí terá `X-Empresa-CNPJ: 12345678000199` e o backend roteia para `acme_corp` automaticamente.

### 3.7. Resumo dos comandos (one-liner)

```bash
# Tudo de uma vez, na VPS:
NEW_CNPJ="12345678000199"
NEW_SLUG="acme_corp"
NEW_RAZAO="ACME CORPORATION LTDA"
SUPER_USER_UUID="04ffee94-1d36-4649-9947-66f4f144d7a1"

# 1) Criar schema no Dados DB
psql "$DADOS_DSN" -c "CREATE SCHEMA IF NOT EXISTS $NEW_SLUG;"

# 2) Migration
cd /opt/easy-esocial/backend
.venv/bin/python -m app.migrate apply --target empresa --version 1.1.0 --schema $NEW_SLUG --dsn "$DADOS_DSN"

# 3) Routing
psql "$SISTEMA_DSN" -c "INSERT INTO sistema.empresas_routing (cnpj, razao_social, schema_name, schema_version, ativo)
                        VALUES ('$NEW_CNPJ', '$NEW_RAZAO', '$NEW_SLUG', '1.1.0', TRUE);"

# 4) Vincular admin
psql "$SISTEMA_DSN" -c "INSERT INTO sistema.user_empresas (user_id, cnpj, papel)
                        VALUES ('$SUPER_USER_UUID', '$NEW_CNPJ', 'admin');"
```

---

## 4. Anatomia do Sistema DB

### 4.1. Tabelas (schema `sistema`)

| Tabela             | Função                                                                  |
| ------------------ | ----------------------------------------------------------------------- |
| `users`            | Credenciais (bcrypt) + flags `ativo`/`super_admin`.                     |
| `empresas_routing` | Diretório CNPJ → schema (a fonte da verdade do tenant).                 |
| `user_empresas`    | N:N usuário ↔ empresa, com papel (admin/operador/leitor).               |
| `audit_log`        | Log append-only de ações sensíveis (login, upload cert, envio eSocial). |
| `schema_meta`      | Versão atual do schema do próprio Sistema DB.                           |

### 4.2. Estado atual (snapshot 11/05/2026)

```
users:
  04ffee94-...d7a1  xandeadmin   "Xande (admin)"  super_admin=True   ativo=True
  63ababeb-...d4ba  Ana          "Ana"            super_admin=False  ativo=True

empresas_routing:
  05969071000110  APPA SERVICOS TEMPORARIOS LTDA          appa      v1.1.0  ativo
  09445502000109  SOLUCOES SERVICOS TERCEIRIZADOS LTDA   solucoes  v1.1.0  ativo

user_empresas:
  Ana → APPA      (operador)
  Ana → SOLUCOES  (operador)

  (xandeadmin é super_admin: vê tudo via override no auth, sem precisar de linha em user_empresas)
```

---

## 5. Anatomia do Dados DB

### 5.1. Schemas atuais

```
appa       — dados da APPA (V2)
solucoes   — dados da SOLUCOES (V2)
legado     — dump cru do V1 da APPA (read-only, histórico)
public     — tabelas compartilhadas entre empresas
sistema    — não deveria existir aqui (resíduo histórico, não usado)
```

### 5.2. Tabelas por schema (idênticas em `appa` e `solucoes`)

Cada schema tem as **36 tabelas** geradas pela migration `empresa_v1.1.0.sql`:

**Master / cadastros**

- `master_empresas` — metadados da própria empresa (1 linha).
- `master_atividades`, `master_perfis`, `master_usuario_empresa`, `master_naturezas_esocial`.

**Explorador (ZIPs do eSocial)**

- `explorador_importacoes` — 1 linha por ZIP importado.
- `explorador_eventos` — 1 linha por XML dentro de um ZIP (event-level).
- `explorador_atividade`, `explorador_rubricas`.
- `empresa_zips_brutos` — bytea com o ZIP original (Large Object pointer).

**Pipeline S-1210 (envio mensal)**

- `s1210_cpf_scope` — universo do mês (1 row por CPF que deveria receber S-1210).
- `s1210_cpf_envios` — 1 row por tentativa de envio.
- `s1210_cpf_recibo` — recibos do eSocial.
- `s1210_cpf_blocklist`, `s1210_lote1_codfunc_scope`, `s1210_operadoras`, `s1210_xlsx`.
- `pipeline_runs`, `pipeline_cpf_results`, `pipeline_snapshots`, `pipeline_audit`, `pipeline_correcao`.

**Timeline (cadeia de eventos eSocial)**

- `timeline_mes`, `timeline_envio`, `timeline_envio_item`.

**eSocial / naturezas**

- `esocial_envios`, `esocial_depara`, `esocial_tabela3_natureza`, `tabela3_esocial_oficial`, `tabela_marcos`, `naturezas_esocial`.

**Certificados**

- `certificados_a1`, `senha_certificado_salva`, `config_esocial`.

**Correções / auditoria**

- `rubrica_corrections`, `correcoes_staging`, `auditoria_naturezas`.

### 5.3. Volumes reais (APPA, 11/05/2026)

```
explorador_eventos     375.985 linhas
s1210_cpf_envios       223.837 linhas
pipeline_cpf_results   113.025 linhas
s1210_cpf_scope        110.651 linhas
```

### 5.4. Schema `public` (compartilhado)

Algumas tabelas vivem em `public` (não migradas para schema da empresa, por motivos históricos):

- `s1299_fechamento_status` — cache de fechamento mensal por (empresa_id, per_apur).
- Tabelas legacy V1 que ainda não foram movidas.

Como `search_path = '<schema>,public'`, o backend resolve essas tabelas transparentemente.

---

## 6. Detalhes do backend

### 6.1. Stack

- **Python 3.12** + venv em `/opt/easy-esocial/backend/.venv/`
- **FastAPI 0.115.6** + **uvicorn**
- **psycopg2-binary** (com `ThreadedConnectionPool` para o Sistema DB)
- Rodando como `systemd service` (`easy-esocial.service`), port 8001
- Atrás do **nginx** (port 443 TLS Let's Encrypt)

### 6.2. Arquivos-chave

| Arquivo                       | Responsabilidade                                                                              |
| ----------------------------- | --------------------------------------------------------------------------------------------- |
| `backend/app/config.py`       | Carrega `.env`, expõe `DB_CONFIG`, `SUPABASE_DB_CONFIG`, `SISTEMA_DB_URL`, `JWT_SECRET`, etc. |
| `backend/app/tenant.py`       | Routing multi-tenant (`get_db_config_for_empresa`, `empresa_conn`).                           |
| `backend/app/sistema_db.py`   | Pool do Sistema DB, `fetch_routing`, `fetch_user_by_email`, `write_audit`.                    |
| `backend/app/auth.py`         | JWT encode/decode, hash bcrypt, dependências FastAPI.                                         |
| `backend/app/auth_routes.py`  | Rotas `POST /api/auth/login`, `GET /api/auth/me`.                                             |
| `backend/app/migrate.py`      | Runner CLI (`python -m app.migrate apply/status`).                                            |
| `backend/migrations/sistema/` | Migrations do Sistema DB.                                                                     |
| `backend/migrations/empresa/` | Migrations de tenant (rodadas N vezes — uma por schema).                                      |

### 6.3. Pool de conexões

- **Sistema DB:** `ThreadedConnectionPool(2, 20, dsn=SISTEMA_DB_URL, options="-c search_path=sistema,public")`. Esse pool serve **tanto auth quanto queries multi-tenant** (o `empresa_conn` pega do mesmo pool e troca o search_path por conexão).
- **Dados DB legado:** queries antigas (com `empresa_id`) abrem conexão nova por request (`psycopg2.connect(**cfg)`). Conforme a migração F5 avança, essas conexões migram para o pool.

### 6.4. JWT

- Algoritmo: **HS256**
- Secret: variável de ambiente `JWT_SECRET` (>= 32 chars)
- Expira em **8 horas** (`JWT_EXPIRES_MINUTES=480`)
- Payload: `{ sub: <user_id>, email, super_admin, empresas: [<cnpj>, ...] }`

---

## 7. Frontend

### 7.1. Stack

- **Vue 3** (`<script setup>`) + **Vite** + **Pinia** + **vue-router**
- Build estático em `/opt/easy-esocial/frontend-dist/` servido pelo nginx
- Rotas eSocial: `/esocial/s1210-anual`, `/esocial/s1210-anual/:per_apur/:lote_num`, etc.

### 7.2. Stores Pinia

- **`auth`** — JWT + lista de empresas do usuário, persistido em `localStorage`.
- **`empresa`** — qual empresa está ATIVA (CNPJ), persistido em `localStorage`.

### 7.3. Headers automáticos

Todo cliente HTTP injeta:

```ts
function authHeaders() {
  const h = { Accept: "application/json" };
  const token = useAuthStore().token;
  if (token) h["Authorization"] = `Bearer ${token}`;
  const cnpj = useEmpresaStore().currentCnpj;
  if (cnpj) h["X-Empresa-CNPJ"] = cnpj;
  return h;
}
```

Se o usuário trocar de empresa no dropdown, o `currentCnpj` muda no localStorage e **todas as próximas requests** já saem com o novo `X-Empresa-CNPJ`.

---

## 8. Auditoria e segurança

### 8.1. `audit_log`

Toda ação sensível grava em `sistema.audit_log`:

```python
sistema_db.write_audit(
    user_id="04ffee94-...",
    cnpj="05969071000110",
    acao="esocial.envio_lote",
    ip="200.x.x.x",
    detalhes={"per_apur": "2025-09", "qtd": 1200},
)
```

Best-effort: nunca levanta exceção. Se cair, log fica em stderr.

### 8.2. Isolamento entre empresas

- **search_path** é re-setado a cada conexão devolvida ao pool (`RESET search_path` no `finally`).
- **GRANT** no schema (em produção, falta restringir `postgres` admin para usar role específica por tenant).
- **Validação dupla** no backend: o middleware checa que `X-Empresa-CNPJ` está em `user_empresas` do usuário do JWT antes de qualquer query.
- **Migrations** nunca tocam dois schemas ao mesmo tempo. Cada execução do runner mira `--schema X`.

### 8.3. Pontos fracos atuais

- Não temos **RLS (Row Level Security)** habilitado nas tabelas. Confiamos no search_path. Um bug que esqueça de setá-lo pode vazar dados — daí a importância do `RESET` no finally do `empresa_conn`.
- **Senhas de certificado A1** são encriptadas com **Fernet** (chave em `.env` `FERNET_KEY`). Bug histórico: se a chave vazar, todas as senhas vazam.
- **Audit_log não tem retenção** automática. Roda forever. Em 10 anos vai ser GB.

---

## 9. Migrations — como funciona o runner

### 9.1. Estrutura

```
backend/migrations/
├── sistema/
│   └── sistema_v1.0.0.sql       # roda 1× no Sistema DB
├── empresa/
│   ├── empresa_v1.0.0.sql       # 36 tabelas base
│   └── empresa_v1.1.0.sql       # incrementos (v1.1.0 = versão atual)
└── _legacy/                     # migrations antigas, NÃO RODA
```

### 9.2. Idempotência

O runner consulta `<schema>.schema_meta(target, version)` **antes** de aplicar e **pula** se a versão já existe:

```python
def _has_applied(cur, target: str, version: str) -> bool:
    cur.execute(
        "SELECT 1 FROM schema_meta WHERE target=%s AND version=%s",
        (target, version),
    )
    return cur.fetchone() is not None
```

### 9.3. Schema injection

Para empresa, o runner faz **string replace** de `public.` por `<schema>.` no SQL antes de executar:

```python
sql = file.read_text(encoding="utf-8")
if schema and target == "empresa":
    sql = sql.replace("public.", f'"{schema}".')
```

Por isso o SQL fonte usa `public.master_empresas` (não-qualificado também funcionaria, mas explicit > implicit).

### 9.4. Comandos úteis

```bash
# Aplicar uma migration
python -m app.migrate apply --target empresa --version 1.1.0 --schema acme --dsn "$DSN"

# Ver versão aplicada num schema
python -m app.migrate status --schema appa --dsn "$DSN"

# Ver versão do Sistema DB
python -m app.migrate status --target sistema --dsn "$SISTEMA_DSN"
```

---

## 10. Cenário hipotético: 10 empresas novas chegam amanhã

### 10.1. Plano

1. **Para cada empresa**, gerar o `schema_name` (slug) e validar regex.
2. **Loop em bash** que cria schema + roda migration + insere routing + vincula usuário admin.
3. Tempo total: ~5 minutos para as 10.

### 10.2. Script de exemplo

```bash
#!/bin/bash
set -euo pipefail

DADOS_DSN="postgresql://postgres.zpizibafccwsjgvplcum:****@aws-1-us-east-2.pooler.supabase.com:5432/postgres?sslmode=require"
SISTEMA_DSN="postgresql://postgres:****@db.kjbgiwnlvqnrfdozjvhq.supabase.co:5432/postgres?sslmode=require"
ADMIN_UUID="04ffee94-1d36-4649-9947-66f4f144d7a1"

while IFS=, read -r cnpj razao slug; do
    echo "=== Provisionando $razao ($cnpj) → schema $slug ==="

    # 1. Schema
    psql "$DADOS_DSN" -c "CREATE SCHEMA IF NOT EXISTS \"$slug\";"

    # 2. Migration
    cd /opt/easy-esocial/backend
    .venv/bin/python -m app.migrate apply \
        --target empresa --version 1.1.0 \
        --schema "$slug" --dsn "$DADOS_DSN"

    # 3. Routing
    psql "$SISTEMA_DSN" <<SQL
        INSERT INTO sistema.empresas_routing (cnpj, razao_social, schema_name, schema_version, ativo)
        VALUES ('$cnpj', '$razao', '$slug', '1.1.0', TRUE)
        ON CONFLICT (cnpj) DO NOTHING;
SQL

    # 4. Vínculo admin
    psql "$SISTEMA_DSN" <<SQL
        INSERT INTO sistema.user_empresas (user_id, cnpj, papel)
        VALUES ('$ADMIN_UUID', '$cnpj', 'admin')
        ON CONFLICT DO NOTHING;
SQL
done < empresas_novas.csv
```

CSV de entrada:

```csv
12345678000101,Empresa Alfa LTDA,alfa
12345678000102,Empresa Beta LTDA,beta
...
```

### 10.3. Capacidade

- Cada schema vazio: ~50 MB.
- 10 schemas: ~500 MB adicionais (negligível).
- Pool do Sistema DB (2..20 conexões) atende facilmente 10 empresas adicionais. Sob carga real, talvez ajustar para 5..40.

### 10.4. Quando partir para "1 banco por empresa"?

Critérios para fragmentar:

- Quando alguma empresa passar de **5 GB** de dados (afeta backup/restore).
- Quando precisarmos isolar **completamente** por contrato (cliente exige dump independente).
- Quando o número de empresas passar de **~50** e queries cross-schema começarem a degradar.

Migração futura é **factível** porque o roteamento já é dinâmico: bastaria mudar `empresas_routing` para guardar `db_url` em vez de só `schema_name`, e atualizar `empresa_conn` para abrir conexão diferente por empresa.

---

## 11. Lacunas e próximos passos

### 11.1. Falta automação

- ❌ Não há endpoint `POST /api/admin/empresas` para criar empresa via UI.
- ❌ Cadastro de usuário só por SQL direto (não tem `POST /api/admin/users`).
- ❌ Vincular usuário a empresa só por SQL.

### 11.2. Falta robustez

- ❌ Sem RLS no Dados DB.
- ❌ `audit_log` sem retenção/rotação.
- ❌ Pool do Sistema DB sem health check periódico (conexões zumbis se Supabase reciclar).

### 11.3. Falta observabilidade

- ❌ Sem dashboard de "quantas requests por empresa".
- ❌ Sem alertas se uma empresa começar a consumir 100% das conexões.

---

## 12. Glossário

| Termo           | Definição                                                                          |
| --------------- | ---------------------------------------------------------------------------------- |
| **Sistema DB**  | Supabase de auth/routing/audit. 1 só.                                              |
| **Dados DB**    | Supabase onde vivem os schemas das empresas. 1 só hoje, escalável.                 |
| **Tenant**      | Empresa no contexto multi-tenant.                                                  |
| **Schema**      | Namespace PostgreSQL. Cada empresa ocupa 1 schema no Dados DB.                     |
| **search_path** | Ordem em que o PG procura tabelas não-qualificadas. Setado por conexão.            |
| **empresa_id**  | ID inteiro legado (1=APPA, 2=SOLU). Em uso em rotas antigas.                       |
| **CNPJ**        | Identificador novo (F5). Chave em `empresas_routing`.                              |
| **F3 / F5**     | Fases do plano da Bíblia para evolução multi-tenant.                               |
| **Routing**     | Tradução CNPJ → schema_name. Faz em `sistema.empresas_routing`.                    |
| **schema_meta** | Tabela de controle de versão do schema (uma em cada DB/schema).                    |
| **super_admin** | Flag em `users` que dá acesso a todas as empresas sem precisar de `user_empresas`. |

---

## 13. Onde checar este documento sob suspeita

Toda a informação acima pode ser confirmada com queries SQL:

```sql
-- Empresas ativas
SELECT * FROM sistema.empresas_routing WHERE ativo;

-- Usuários
SELECT id, email, nome, super_admin, ativo FROM sistema.users;

-- Vínculos
SELECT u.email, er.razao_social, ue.papel
  FROM sistema.user_empresas ue
  JOIN sistema.users u ON u.id = ue.user_id
  JOIN sistema.empresas_routing er ON er.cnpj = ue.cnpj;

-- Schemas existentes no Dados DB
SELECT nspname FROM pg_namespace WHERE nspname NOT LIKE 'pg_%' AND nspname != 'information_schema';

-- Versão do schema de cada empresa
SELECT 'appa' AS schema, * FROM appa.schema_meta
UNION ALL SELECT 'solucoes', * FROM solucoes.schema_meta;
```

Os comandos acima estão registrados em `_tmp_query.py` (transitório, removido após uso) e a saída foi colada na seção **4.2**.

---

**FIM.**
