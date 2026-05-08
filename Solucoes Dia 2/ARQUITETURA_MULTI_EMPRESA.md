# ARQUITETURA MULTI-EMPRESA — Soluções Dia 2

> Documento técnico complementar de [`MIGRACAO_V1_V2.md`](./MIGRACAO_V1_V2.md).
> Foco: **como o V2 vai isolar empresas em bancos Supabase distintos**, **como roteia requisições**, e **por que o V2 trata XML completo do governo de jeito diferente do V1**.

---

## 1. Princípio central: **um banco por empresa**

### 1.1. Por que não multi-tenant por linha (V1) ou por schema?

| Estratégia | Prós | Contras | Veredito |
|---|---|---|---|
| **Tenant por linha** (V1: coluna `empresa_id` em todas as tabelas) | simples, JOIN direto entre empresas | risco vazamento (esquecer 1 `WHERE empresa_id=X`); LGPD frágil; índices crescem com mistura; migration impacta todos | ❌ — V1 já provou que cresce ruim |
| **Tenant por schema** (1 schema Postgres por empresa, mesmo banco) | isolamento médio; sem `empresa_id` em queries | manutenção pesada; backup e restore travam todo o banco; migration tem que iterar schemas | ⚠️ |
| **Tenant por banco** (1 Supabase DB por empresa) | **isolamento total**; backup/restore independentes; quotas independentes; dump específico para auditoria; LGPD por design | precisa router de conexão; precisa migration runner que percorre N bancos | ✅ **escolhido** |

### 1.2. Implicações imediatas

- **Vazar Empresa A pra Empresa B é fisicamente impossível** sem trocar a connection string.
- A Rafa fechando APPA não enxerga **nada** da Soluções — nem mesmo SQL admin acidental.
- Se um schema migration der bug, ele afeta **só uma empresa**, e dá pra rodar empresa por empresa.
- Backup é por empresa: se a APPA pedir "manda o banco completo pra contabilidade", é 1 dump direto.

---

## 2. Topologia detalhada

```
┌────────────────────────────────────────────────────────────────────────┐
│                        FRONTEND V2 (Vue 3 + Vite)                       │
│                       (servido pela mesma VPS)                          │
│                                                                          │
│   após login: JWT contém { user_id, empresas: [cnpj1, cnpj2, ...] }     │
│   header em toda request: Authorization + X-Empresa-CNPJ                │
└────────────────────────────────┬───────────────────────────────────────┘
                                 │
┌────────────────────────────────▼───────────────────────────────────────┐
│                    BACKEND V2 (FastAPI / uvicorn)                       │
│                                                                          │
│   middleware auth → resolve user + verifica X-Empresa-CNPJ permitido    │
│   middleware tenant → router_db(cnpj) → conexão Supabase certo          │
│                                                                          │
│   request.state.db = psycopg2.connect(EMPRESA_DB_URL)                  │
└──────────┬─────────────────────────────────────────────────┬───────────┘
           │                                                  │
           │                                                  │
┌──────────▼──────────┐    ┌──────────────────────┐     ┌────▼─────────────┐
│   SUPABASE SISTEMA  │    │   SUPABASE APPA      │     │ SUPABASE SOLUCOES │
│   (banco "mestre")  │    │   (banco da APPA)    │     │  (banco Soluções) │
│                     │    │                      │     │                   │
│   - users           │    │   schema padrão      │     │  schema padrão    │
│   - empresas_       │    │   - explorador_eventos│     │  - explorador_eventos│
│     routing         │    │   - timeline_envio   │     │  - timeline_envio │
│   - schema_versions │    │   - timeline_envio_  │     │  - timeline_envio_│
│   - audit_log       │    │     item             │     │    item           │
│                     │    │   - timeline_mes     │     │  - timeline_mes   │
│                     │    │   - empresa_zips_    │     │  - empresa_zips_  │
│                     │    │     brutos           │     │    brutos         │
│                     │    │   - rubricas         │     │  - rubricas       │
│                     │    │   - s1010_*          │     │  - s1010_*        │
│                     │    │                      │     │                   │
│                     │    │   ⚠ XMLs antigos:    │     │  ✅ XMLs completos │
│                     │    │     metadados only   │     │    em lobject     │
└─────────────────────┘    └──────────────────────┘     └───────────────────┘
```

### 2.1. Banco "Sistema" (mestre)

**Não contém dados operacionais.** Só:

```sql
CREATE TABLE users (
  id UUID PRIMARY KEY,
  email TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,           -- bcrypt (compatível com V1)
  nome TEXT,
  criado_em TIMESTAMPTZ DEFAULT NOW(),
  ultimo_login TIMESTAMPTZ
);

CREATE TABLE empresas_routing (
  cnpj TEXT PRIMARY KEY,                 -- 14 dígitos
  razao_social TEXT NOT NULL,
  db_url TEXT NOT NULL,                  -- postgres://user:pass@host:port/db
  db_anon_key TEXT,                      -- pra Supabase REST se usar
  schema_version TEXT NOT NULL,          -- ex.: '1.2.0'
  flags JSONB DEFAULT '{}',              -- { tem_xml_completo: bool, plano: 'gold' }
  ativo BOOLEAN DEFAULT TRUE,
  criado_em TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE user_empresas (
  user_id UUID REFERENCES users(id) ON DELETE CASCADE,
  cnpj TEXT REFERENCES empresas_routing(cnpj) ON DELETE CASCADE,
  papel TEXT NOT NULL,                   -- 'admin' | 'operador' | 'leitor'
  PRIMARY KEY (user_id, cnpj)
);

CREATE TABLE schema_versions (
  cnpj TEXT REFERENCES empresas_routing(cnpj),
  version TEXT NOT NULL,
  aplicado_em TIMESTAMPTZ DEFAULT NOW(),
  PRIMARY KEY (cnpj, version)
);

CREATE TABLE audit_log (
  id BIGSERIAL PRIMARY KEY,
  ts TIMESTAMPTZ DEFAULT NOW(),
  user_id UUID,
  cnpj TEXT,
  acao TEXT,                             -- 'login', 'envio_lote', 'export_xml', etc
  detalhes JSONB
);
```

### 2.2. Banco por empresa (schema padrão)

**Idêntico em todas as empresas.** Versionado por arquivo `schema_v{X.Y.Z}.sql`. As tabelas vivas hoje no V2 (já validadas pela Soluções):

| Tabela | Função | Dados V1 importáveis? |
|---|---|---|
| `empresa_zips_brutos` | ZIPs do governo brutos por importação | parcial (V1 não guardou ZIPs todos) |
| `explorador_eventos` | 1 linha por evento extraído (S-1200/1210/2200/2299/5001/5002/5003/3000) | ✅ metadados; ❌ `xml_oid` (V1 não tem XML completo) |
| `timeline_mes` | agregador `(per_apur)` | ✅ |
| `timeline_envio` | 1 linha por execução de envio (CICLO100 = 1 envio = 100 CPFs) | ✅ |
| `timeline_envio_item` | 1 linha por CPF dentro do envio (status, recibo, erro) | ✅ |
| `rubricas`, `naturezas` | tabelas mestras | ✅ |
| `s1010_envios`, `s1010_eventos` | controle S-1010 | ✅ |
| `pipeline_cpf_results` | resultado consolidado HEAD por CPF | ✅ |

### 2.3. O que muda entre APPA e Soluções no mesmo schema?

**Nada estrutural.** Mas:

- **APPA** vai ter `flags = { "tem_xml_completo": false, "origem_dados": "v1_legado" }`. Frontend mostra badge "histórico V1" e desabilita botão "baixar XML" pra eventos `criado_em < 2026-05-08`.
- **Soluções** vai ter `flags = { "tem_xml_completo": true }`. Botão "baixar XML" funciona pra qualquer evento.
- Eventos importados pós-V2 em qualquer empresa têm XML completo automaticamente.

---

## 3. Diferença CRÍTICA: XML do governo

### 3.1. Como era no V1

```
1. Sistema V1 envia S-1210 → recebe protocolo
2. V1 consulta protocolo → recebe XML retorno (cd=201, recibo, mensagem)
3. V1 PARSEIA o XML → salva CAMPOS NO BANCO:
     - protocolo
     - nr_recibo
     - codigo_resposta
     - descricao_resposta
4. V1 DESCARTA o XML bruto.
```

**Resultado**: pra qualquer CPF do APPA, **só temos os campos parseados**. Se o governo mudar a interpretação de algum erro, ou alguém pedir o XML original, **acabou — não existe mais**.

### 3.2. Como é no V2

```
1. Sistema V2 envia S-1210 → recebe protocolo
2. V2 consulta protocolo → recebe XML retorno COMPLETO
3. V2 SALVA O XML BRUTO em postgres lobject (com compressão gzip)
   → coluna xml_oid em explorador_eventos / timeline_envio_item
4. V2 também parseia campos pra query rápida (igual V1 fazia)
5. UI Explorador permite BAIXAR o XML original de qualquer evento
```

**Resultado**: rastreabilidade completa. Auditoria fiscal pode pedir XML do governo de qualquer envio e a gente entrega.

### 3.3. Storage de XML — política

| Item | Política |
|---|---|
| Local | `lobject` Postgres (suporta nativo, transação igual a row) |
| Compressão | gzip aplicado antes de gravar (eSocial XML = ~70% redução) |
| Backup | mesma frequência que o resto do DB Supabase (diário automático) |
| Retenção quente | 24 meses no DB principal |
| Retenção fria | 24+ meses → exportar pra `archive_xml/{cnpj}/{YYYY}/{tipo_evento}.tar.zst` em storage S3-compat |
| Acesso UI | endpoint autenticado `GET /api/eventos/{id}/xml` → baixa stream |

---

## 4. DB Router — implementação proposta

### 4.1. Esqueleto FastAPI

```python
# backend/app/tenant.py
from contextlib import contextmanager
import psycopg2
from . import sistema_db

@contextmanager
def empresa_conn(cnpj: str):
    """Abre conexão no banco da empresa do CNPJ. Levanta 403 se não autorizado."""
    rota = sistema_db.fetch_routing(cnpj)
    if not rota or not rota['ativo']:
        raise PermissionError(f"empresa {cnpj} inativa ou inexistente")
    conn = psycopg2.connect(rota['db_url'])
    try:
        yield conn
    finally:
        conn.close()
```

```python
# backend/app/main.py (middleware)
from fastapi import Request, HTTPException

@app.middleware("http")
async def tenant_router(request: Request, call_next):
    cnpj = request.headers.get("X-Empresa-CNPJ")
    user = request.state.user            # populado pelo middleware auth anterior
    if cnpj and cnpj not in user.empresas_permitidas:
        raise HTTPException(403, "sem permissão nesta empresa")
    request.state.cnpj_ativo = cnpj
    return await call_next(request)
```

```python
# qualquer endpoint
@app.get("/api/timeline-envios")
def listar(request: Request):
    cnpj = request.state.cnpj_ativo
    with empresa_conn(cnpj) as conn:
        with conn.cursor() as c:
            c.execute("SELECT * FROM timeline_envio ORDER BY id DESC LIMIT 50")
            return c.fetchall()
```

### 4.2. Pool de conexões (importante em produção)

Usar `psycopg2.pool.ThreadedConnectionPool` **por empresa**, mantido em cache:

```python
_pools: dict[str, ThreadedConnectionPool] = {}

def get_pool(cnpj: str) -> ThreadedConnectionPool:
    if cnpj not in _pools:
        rota = sistema_db.fetch_routing(cnpj)
        _pools[cnpj] = ThreadedConnectionPool(1, 10, rota['db_url'])
    return _pools[cnpj]
```

Limite: 10 conexões por empresa. Se passar — fila ou erro 503.

---

## 5. Migration runner

```bash
# CLI proposto (backend/app/migrate.py)
python -m app.migrate apply --version 1.2.0
python -m app.migrate apply --version 1.2.0 --cnpj 09445502000109   # 1 empresa só
python -m app.migrate status                                          # mostra o estado de cada DB
```

```python
def apply(version: str, cnpj: str | None = None):
    rotas = sistema_db.list_empresas() if cnpj is None else [sistema_db.fetch_routing(cnpj)]
    sql = open(f"migrations/schema_v{version}.sql").read()
    for r in rotas:
        if sistema_db.has_version(r['cnpj'], version):
            continue
        with psycopg2.connect(r['db_url']) as conn:
            with conn.cursor() as c:
                c.execute(sql)             # transação implícita
                sistema_db.mark_applied(r['cnpj'], version)
        print(f"OK {r['cnpj']} → {version}")
```

**Regras:**
1. SQL é idempotente sempre que possível (`CREATE TABLE IF NOT EXISTS`, `ALTER TABLE ... IF EXISTS`).
2. Cada migration é uma transação por empresa (rollback automático se falhar).
3. O `schema_versions` no DB sistema garante que ninguém aplica versão errada.
4. Em produção, primeiro aplicar em staging (1 empresa de teste).

---

## 6. Plano ETL APPA (V1 → Supabase APPA)

> Detalhamento mínimo. Plano completo escrito durante a Fase 3 da missão.

### 6.1. Inventário de tabelas V1 envolvidas

| Tabela V1 (Postgres legacy) | Tabela V2 destino |
|---|---|
| `s1210_cpf_envios` | `timeline_envio_item` (1:N → 1:1 com agrupamento por envio) |
| `s1210_cpf_scope` | `pipeline_cpf_results` |
| `users` | `users` (Sistema DB) |
| `empresas` | `empresas_routing` (Sistema DB) |
| `rubricas`, `naturezas` | `rubricas`, `naturezas` (no Supabase APPA) |
| `s1010_*` | `s1010_*` (no Supabase APPA) |
| (não tem) `explorador_eventos` | popular **só metadados** com `xml_oid=NULL` |

### 6.2. Estratégia de execução

1. **Snapshot V1** — `pg_dump` filtrado por `empresa_id=APPA` em arquivo `appa_v1_dump.sql` (read-only).
2. **Carga em DB temporário** `appa_v1_replica` — pra rodar SELECTs sem onerar produção.
3. **ETL Python** lê de `appa_v1_replica`, normaliza, escreve no Supabase APPA. Cada tabela em batch de 5000 linhas.
4. **Reconciliação**:
   - `COUNT(*)` por tabela: replica vs Supabase APPA.
   - `COUNT(DISTINCT cpf)` em `pipeline_cpf_results` por per_apur: replica vs Supabase APPA.
   - Histograma `erro_codigo` por per_apur: replica vs Supabase APPA.
5. **Sign-off Rafa**: ela abre 5 CPFs aleatórios na UI V2 e confere com a UI V1 lado a lado.

### 6.3. Risco de divergência V1 vs V2

V1 tem **218.953 linhas em `s1210_cpf_envios`** (1 linha por POST = retentativas, chain walk, retificações). V2 tem `timeline_envio_item` que é **1 linha por (envio, cpf)**.

A regra de **HEAD** já implementada no V2 (`DISTINCT ON (cpf) ORDER BY enviado_em DESC`) resolve. Mas o histórico das 218k linhas vai pra coluna `tentativas` ou tabela auxiliar `historico_tentativas_cpf` (a definir).

---

## 7. Frontend — implicações

### 7.1. Login → Seleção de empresa

```
1. POST /api/auth/login { email, senha }
   ← { token, empresas: [{cnpj, razao}] }
2. Se 1 empresa: salva no Pinia store e segue.
   Se >1: tela EmpresaSelectView.vue → escolhe.
3. Token salvo em localStorage. Empresa ativa salva em localStorage também.
4. Axios interceptor:
     headers.Authorization = `Bearer ${token}`
     headers['X-Empresa-CNPJ'] = empresaAtiva.cnpj
```

### 7.2. Badges de estado

| Empresa | Badge no painel |
|---|---|
| APPA | "📦 histórico V1 — XMLs antigos sem download" |
| Soluções | "🔓 V2 nativo — XML completo disponível" |
| Outras | conforme `flags` |

### 7.3. Componentes existentes na V2 que já encaixam

- `EmpresaSelectView.vue` ✅
- `BrainStage.vue`, `AppBackground.vue` (Liquid Glass) ✅
- `ExploradorView.vue` + `timeline/` ✅ (chain walk)
- `S1210AnualView.vue`, `S1210MesView.vue` ✅
- Falta: `LoginView.vue` conectar no auth real (hoje é stub).

---

## 8. VPS — configuração proposta

### 8.1. Estrutura de diretórios

```
/opt/easy-esocial/
├── backend/                  # checkout do repo V2 (subdir backend/)
│   ├── .venv/                # venv Python isolado
│   └── app/
├── frontend-dist/            # output de `npm run build`
├── certs/                    # PFX A1 montado por volume seguro
│   ├── 09445502000109.pfx
│   └── ... (outros CNPJs)
└── logs/                     # uvicorn + nginx
```

### 8.2. Nginx (proposta)

```nginx
server {
  listen 443 ssl http2;
  server_name easyesocial.com.br;
  ssl_certificate /etc/letsencrypt/live/easyesocial.com.br/fullchain.pem;
  ssl_certificate_key /etc/letsencrypt/live/easyesocial.com.br/privkey.pem;

  # Frontend
  root /opt/easy-esocial/frontend-dist;
  index index.html;

  location / {
    try_files $uri $uri/ /index.html;     # SPA
  }

  # Backend
  location /api/ {
    proxy_pass http://127.0.0.1:8001/api/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_read_timeout 300;               # eSocial polling pode passar 60s
  }

  client_max_body_size 50M;               # uploads XLSX Domínio
}
```

### 8.3. systemd service (uvicorn)

```ini
# /etc/systemd/system/easy-esocial.service
[Unit]
Description=Easy eSocial V2 backend
After=network.target

[Service]
User=esocial
WorkingDirectory=/opt/easy-esocial/backend
Environment="CERT_BASE_PATH=/opt/easy-esocial/certs"
EnvironmentFile=/opt/easy-esocial/.env.production
ExecStart=/opt/easy-esocial/backend/.venv/bin/uvicorn app.main:app \
  --host 127.0.0.1 --port 8001 --workers 4
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

---

## 9. Segurança — hardening obrigatório

| Item | Detalhe |
|---|---|
| **Certificados .pfx** | nunca no git (já blindado em `.gitignore`). Em produção, `chmod 600` + `chown esocial:esocial`. Path absoluto via env `CERT_BASE_PATH`. |
| **Connection strings Supabase** | env apenas. Nunca em código. |
| **JWT secret** | mínimo 64 chars random. Rotacionar a cada 90 dias. |
| **bcrypt cost** | 12 (padrão V1 mantém compat). |
| **Rate limit** | nginx `limit_req_zone` para `/api/auth/login` (5/min/IP) e `/api/envio/*` (60/min/user). |
| **CORS** | só `easyesocial.com.br` em produção. |
| **Audit log** | toda ação sensível (login, envio_lote, export_xml, mudança_empresa) grava em `audit_log` no Sistema DB. |
| **Backup Supabase** | snapshot diário automático + dump manual mensal pra storage offsite. |
| **HTTPS only** | nginx redireciona `:80 → :443`. HSTS habilitado. |
| **LGPD** | banco por empresa = isolamento por design. Direito ao esquecimento → DROP DATABASE da empresa. |

---

## 10. Roadmap de testes antes do go-live

| Tipo | Cobertura mínima |
|---|---|
| **Smoke** | login → seleção empresa → painel S-1210 anual carrega → 1 envio teste |
| **Schema** | migration runner aplica `schema_v1.0.0` num DB vazio sem erro |
| **ETL APPA** | 100% dos CPFs APPA do V1 batem na contagem do Supabase APPA |
| **Multi-tenant isolation** | usuário com permissão em APPA tenta acessar Soluções → 403 |
| **Envio paralelo (CICLO100)** | rodar 1 leva de 100 CPFs no Supabase Soluções e validar `timeline_envio` |
| **Upload Domínio** | upload do mesmo XLSX que a Rafa usou na última semana → resultado idêntico |
| **XML completo** | enviar 1 S-1210, confirmar `xml_oid` populado, baixar XML pela UI |
| **Backup/Restore** | restaurar dump APPA num DB novo do zero e validar |

---

## 11. Glossário

| Termo | Significado |
|---|---|
| **Banco Sistema** | DB Supabase central com `users`, `empresas_routing`, `audit_log`. Não tem dados operacionais. |
| **Banco da Empresa** | DB Supabase exclusivo de 1 empresa. Contém todos os eventos, envios, rubricas. |
| **lobject** | Large Object do Postgres — usado pra guardar XML completo de evento (não é coluna BYTEA, é um stream com OID). |
| **CICLO100** | técnica documentada em `ciclo100.md` — envio em levas de 100 CPFs. |
| **HEAD** | última versão de um evento por (cpf, per_apur), filtrada por `retificado_por_id IS NULL`. |
| **Chain walk** | navegação entre eventos relacionados de um CPF (S-2200 → S-1200 → S-1210 → S-2299). |
| **Schema padrão** | DDL idêntico aplicado em todos os DBs de empresa, versionado. |

---

## 12. Resumo executivo

1. **1 banco Supabase por empresa**, schema idêntico.
2. **Banco "Sistema" separado** com auth e routing.
3. **DB router no FastAPI** resolve empresa via JWT + header.
4. **Migration runner** versiona schema e aplica em todos os DBs.
5. **APPA migra com metadados** (sem XML completo — V1 não tinha).
6. **Soluções e novas empresas** já entram com XML completo do governo guardado em `lobject`.
7. **VPS Hostinger** muda do build V1 para V2; mesmo domínio, mesma URL.
8. **V1 vira read-only** após cutover.

> Decisões pendentes em [`MIGRACAO_V1_V2.md` § 6](./MIGRACAO_V1_V2.md#6-decisões-pendentes-perguntas-que-a-missão-precisa-responder).
