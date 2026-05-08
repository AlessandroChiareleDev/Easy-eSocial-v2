# 01 — Plano do Explorador de Arquivos

> Pré-requisito: ler [`00_CONTEXTO_E_FONTES.md`](./00_CONTEXTO_E_FONTES.md) primeiro.
> Este MD é o **blueprint técnico**: o que vai ser construído, em que ordem, e por que.

---

## 1. VISÃO DO PRODUTO (em uma frase)

> **Pegar o zip cru do eSocial, guardar intacto e comprimido dentro do banco da empresa, e oferecer uma interface bonita e rápida no front para ver, entender e estudar todos os eventos do ano de uma empresa.**

Princípios de UX:

- **Visão por CPF/funcionário** (chain walk: S-2200 → S-1200 → S-1210 → S-5001/02/03 → S-2299).
- **XMLs baixáveis** em cada nó da timeline.
- **Visualização sofisticada** (timeline/grafo, não tabela). Detalhes do design o Alex explica depois.
- **Upload rápido com feedback visual**: barra de progresso, taxa de transferência, velocímetro, % de extração.

---

## 2. FLUXO DE DADOS — DO PORTAL ATÉ O FRONT

```
[1] Usuário no portal eSocial
    └─ escolhe período: dt_ini → dt_fim
    └─ clica "Baixar"
    └─ eSocial gera zip(s) com nrSequencial próprio
    └─ usuário salva localmente

[2] Upload no Explorador (drag-drop estilo wagner)
    └─ front envia arquivo + dt_ini + dt_fim + estado_id da empresa
    └─ backend recebe stream

[3] Backend processa
    ├─ a) calcula sha256 do zip cru (deduplicação)
    ├─ b) extrai sequencial do nome do arquivo
    ├─ c) salva o ZIP INTACTO (binário) no banco
    │     em uma tabela dedicada empresa_zips_brutos
    ├─ d) extrai XMLs em memória, processa em streaming
    ├─ e) por XML: identifica tipo de evento, perApur, cpf_trab, id_evento, nr_recibo
    └─ f) insere linhas em explorador_eventos com FK para o zip de origem

[4] Front consulta
    └─ pelos índices da tabela explorador_eventos
    └─ chain walk por CPF
    └─ download de XML individual: backend retira do zip armazenado e devolve
```

> **O zip permanece guardado para sempre** dentro do banco. Os XMLs nunca são gravados em disco fora dele.

---

## 3. DECISÕES DE ARQUITETURA

### 3.1 Onde fica o backend?

**Decisão:** criar `Easy-eSocial-v2/backend/` — FastAPI próprio, isolado do V1.

Motivo:

- O Alex foi explícito: "tudo novo para soluções", "não toca no projeto atual".
- O `bot_api` do V1 é grande, acoplado ao Supabase APPA. Reusar é arriscar contaminar APPA.
- Dependências mínimas: `fastapi`, `uvicorn`, `psycopg2-binary`, `python-multipart` (upload), `openpyxl` (se precisar XLSX no futuro), `lxml` (parse XML rápido).

### 3.2 Como guardar o zip dentro do banco?

**Decisão:** **Postgres Large Objects (`pg_largeobject`)** — guardar o zip como `OID` em coluna `conteudo_oid OID`.

Por quê:

- Limite por upload definido em **3 GB**. `BYTEA` só aceita até ~1 GB → desclassificado.
- Large Objects suportam até **4 TB por objeto**, leitura/escrita em streaming via `lo_open` / `lo_read` (não carrega tudo em RAM).
- Ideal pro caso "guardar o zip pra sempre, ler XML único sob demanda" — abrimos o LO, fazemos seek, lemos só o entry pedido.
- Backup: `pg_dump -b` inclui Large Objects.

**Re-comprimir o zip antes de guardar?** Não. O zip do eSocial já está comprimido — re-comprimir traz <10% e atrapalha o streaming.

### 3.3 Chave única do zip

**Decisão:** `(empresa_id, sha256_zip)` é a chave de **deduplicação**. O par `(empresa_id, dt_ini, dt_fim, sequencial_esocial)` é a chave **lógica** (o que o usuário vê).

Comportamento ao tentar subir o mesmo zip de novo:

- Se sha256 já existe → não duplica binário, só registra um novo "upload event" e aponta pro mesmo zip.
- Se sha256 novo mas mesmo `(dt_ini, dt_fim, sequencial)` → versionar (talvez houve nova solicitação no portal).

### 3.4 Schema multi-estado

Tabela `master_empresas` ganha coluna `tipo_estado VARCHAR(16) NOT NULL` com CHECK em `('estado_1','estado_2')`. SOLUCOES é cadastrada como `estado_1` desde já. O comportamento futuro do parser por estado é ponto de extensão.

### 3.5 Cadeia (chain walk) — como amarrar eventos

Cada evento eSocial tem `id_evento` (atributo `Id` no XML, formato `ID1...`). Eventos relacionados se referenciam por:

- `nrRecArqBase` (ex: S-1210 referencia S-1200)
- `nrRecibo` em S-3000 (apontando o evento excluído)
- `cpf_trab` + `perApur` (amarração lógica de timeline)

A tabela `explorador_eventos` (já existe no schema) já guarda `id_evento`, `nr_recibo`, `cpf_trab`, `per_apur`, `tipo_evento`. Adicionar:

- `referenciado_recibo VARCHAR(40)` — recibo do evento-pai (extraído do XML)
- `zip_id BIGINT REFERENCES empresa_zips_brutos(id)` — origem do XML
- `xml_offset_no_zip INT` ou nome do entry — para extrair sob demanda

---

## 4. MODELO DE DADOS — TABELAS NOVAS

### 4.1 `empresa_zips_brutos`

```sql
CREATE TABLE empresa_zips_brutos (
    id BIGSERIAL PRIMARY KEY,
    empresa_id BIGINT NOT NULL REFERENCES master_empresas(id),
    -- período pedido pelo usuário no portal
    dt_ini DATE NOT NULL,
    dt_fim DATE NOT NULL,
    -- sequencial gerado pelo eSocial (extraído do nome do arquivo)
    sequencial_esocial VARCHAR(40),
    -- arquivo cru
    nome_arquivo_original TEXT NOT NULL,
    sha256 CHAR(64) NOT NULL,
    tamanho_bytes BIGINT NOT NULL,
    conteudo_oid OID NOT NULL,  -- Large Object (pg_largeobject), até 4 TB, streaming
    -- contagens (preenchidas após extração)
    total_xmls INT,
    perapur_dominante VARCHAR(7),
    -- auditoria
    enviado_em TIMESTAMP NOT NULL DEFAULT now(),
    extraido_em TIMESTAMP,
    extracao_status VARCHAR(16) NOT NULL DEFAULT 'pendente',  -- pendente|extraindo|ok|erro
    extracao_erro TEXT,
    UNIQUE (empresa_id, sha256)
);
CREATE INDEX ix_zips_periodo ON empresa_zips_brutos (empresa_id, dt_ini, dt_fim);
CREATE INDEX ix_zips_status ON empresa_zips_brutos (extracao_status);
```

### 4.2 Estender `explorador_eventos` (já existe)

Adicionar colunas:

```sql
ALTER TABLE explorador_eventos
  ADD COLUMN zip_id BIGINT REFERENCES empresa_zips_brutos(id) ON DELETE CASCADE,
  ADD COLUMN xml_entry_name TEXT,             -- nome do arquivo dentro do zip
  ADD COLUMN referenciado_recibo VARCHAR(40); -- recibo do evento-pai (chain walk)
CREATE INDEX ix_evt_zip ON explorador_eventos (zip_id);
CREATE INDEX ix_evt_cpf_per ON explorador_eventos (cpf_trab, per_apur);
CREATE INDEX ix_evt_recibo ON explorador_eventos (nr_recibo);
CREATE INDEX ix_evt_ref ON explorador_eventos (referenciado_recibo);
```

### 4.3 `master_empresas` — coluna `tipo_estado`

```sql
ALTER TABLE master_empresas
  ADD COLUMN tipo_estado VARCHAR(16) NOT NULL DEFAULT 'estado_1'
    CHECK (tipo_estado IN ('estado_1','estado_2'));
```

---

## 5. API (FastAPI dentro de `Easy-eSocial-v2/backend/`)

| Método | Rota                                      | Descrição                                          |
| ------ | ----------------------------------------- | -------------------------------------------------- |
| POST   | `/api/explorador/zips/upload`             | Upload de 1 zip (multipart). Retorna `zip_id`.     |
| POST   | `/api/explorador/zips/{zip_id}/extrair`   | Dispara extração assíncrona. Retorna job_id.       |
| GET    | `/api/explorador/zips/{zip_id}/status`    | Progresso da extração (% + velocímetro).           |
| GET    | `/api/explorador/zips`                    | Lista zips da empresa (paginação, filtro período). |
| GET    | `/api/explorador/zips/{zip_id}/download`  | Devolve o zip original (auditoria).                |
| GET    | `/api/explorador/eventos`                 | Filtros: cpf, per_apur, tipo, zip_id.              |
| GET    | `/api/explorador/eventos/{evento_id}/xml` | Devolve o XML único extraído sob demanda do zip.   |
| GET    | `/api/explorador/cpfs/{cpf}/timeline`     | Chain walk montado para um CPF.                    |

### Streaming e progresso

- Upload: `StreamingResponse` no front com `XHR.upload.onprogress` ou `fetch + ReadableStream`.
- Extração: backend processa em streaming (não carrega XMLs todos em memória), publica progresso em tabela `explorador_extracao_progresso(zip_id, lidos, total, bytes_lidos, started_at, last_tick_at)`. Front faz polling a cada 500ms para velocímetro.

---

## 6. FRONTEND (Vue 3 + Vite + TS + Tailwind v4)

### Nova rota

- `/explorador` (única view nesta fase)

### Componentes a criar (em `src/views/Explorador/` e `src/components/explorador/`)

- `ExploradorView.vue` — layout master.
- `ZipUploader.vue` — drag-and-drop, mostra fila, % de upload por arquivo, taxa MB/s, velocímetro.
- `ZipsList.vue` — lista de zips já carregados, agrupado por mês/período.
- `EventosViewer.vue` — explorador de eventos por CPF/período (timeline visual).
- `XmlPreview.vue` — modal para ver/baixar XML de um nó.

### Estilo

Manter tokens já definidos: `liquid-glass`, `gg-glow`, `blush-aura` (ver `src/styles/main.css`). Velocímetro usa Ghost Green como cor da agulha.

---

## 7. FASES DE EXECUÇÃO

### Fase A — Fundação (sem UI)

- A.1 Criar `backend/` no V2 com FastAPI mínimo, conexão ao `easy_social_solucoes` local.
- A.2 Migrations idempotentes: `empresa_zips_brutos`, ALTER em `explorador_eventos` e `master_empresas`.
- A.3 Cadastrar SOLUCOES em `master_empresas` como `estado_1`.
- A.4 Endpoint `POST /zips/upload` com armazenamento em **Large Object (OID)** via `psycopg2 lobject` em streaming.
- A.5 Endpoint `POST /zips/{id}/extrair` síncrono (sem job ainda) — popula `explorador_eventos`.
- A.6 Importar os 3 zips existentes (06, 08, 12 de 2025) por curl/script para validar.

### Fase B — Extração robusta

- B.1 Tornar a extração assíncrona (background task ou job runner simples).
- B.2 Tabela de progresso + endpoint de status.
- B.3 Parsers especializados por tipo de evento (extrair `cpf_trab`, `per_apur`, `id_evento`, `nr_recibo`, `referenciado_recibo`).
- B.4 Chain walk: índices e endpoint `/cpfs/{cpf}/timeline`.

### Fase C — Frontend

- C.1 `ZipUploader.vue` com progresso real (XHR).
- C.2 `ZipsList.vue`.
- C.3 `EventosViewer.vue` com filtros.
- C.4 Velocímetro/Lover indicator.
- C.5 Visualização timeline (escolher lib: vis-timeline, vue-flow, ou custom SVG).

### Fase D — Polish

- D.1 Empty states, skeletons, error boundaries.
- D.2 Cache de timeline por CPF.
- D.3 Lazy decompress (extrair XML único sob demanda do zip armazenado).

---

## 8. DECISÕES AINDA EM ABERTO (esperando Alex)

| #   | Decisão                                            | Default proposto                 |
| --- | -------------------------------------------------- | -------------------------------- |
| D.1 | Lib de timeline no front                           | `vis-timeline` (provado, leve)   |
| D.2 | Job runner para extração                           | FastAPI BackgroundTasks (MVP)    |
| D.3 | Re-comprimir zip ao guardar?                       | Não (zip já comprime XMLs)       |
| D.4 | Compactação extra de XML individual no banco?      | Não (extrair sob demanda do zip) |
| D.5 | Identidade do upload (login/sessão)                | Sem auth no MVP local            |
| D.6 | Limite de tamanho por upload                       | 3 GB                             |
| D.7 | Como popular `referenciado_recibo` para chain walk | Parser por tipo (mapa de XPaths) |

---

## 9. RISCOS E MITIGAÇÕES

| Risco                                      | Mitigação                                                                                |
| ------------------------------------------ | ---------------------------------------------------------------------------------------- |
| Zip de 800 MB carrega tudo em RAM ao subir | Upload multipart em stream → grava no Large Object em chunks de 4 MB.                    |
| Ler 800 MB do Postgres a cada XML pedido   | `lo_open` + `lo_read` por offset; abrir zip via `zipfile` sobre file-like wrapper do LO. |
| Extrair 200k XMLs estoura memória          | Iterar com `zipfile.ZipFile.open()` por entry, parse incremental.                        |
| Re-upload do mesmo zip                     | sha256 é UNIQUE — não duplica.                                                           |
| Banco SOLUCOES já tem schema "do APPA"     | Não dropar nada. ALTER apenas para adicionar; tabelas novas são novas.                   |
| Front travar com lista de 200k eventos     | Paginar + filtrar no backend; nunca trazer tudo.                                         |

---

## 10. CHECKLIST INICIAL (a fazer agora, em ordem)

1. ✅ Criar pasta `docs/EXPLORADOR/` no V2 e estes 2 MDs (este passo está sendo feito).
2. ⬜ Criar `Easy-eSocial-v2/backend/` com `pyproject.toml`/`requirements.txt`, `.env.example`, FastAPI hello-world.
3. ⬜ Criar `backend/db.py` apontando para `easy_social_solucoes` LOCAL.
4. ⬜ Criar `backend/migrations/` com SQL idempotente das 3 alterações da seção 4.
5. ⬜ Cadastrar SOLUCOES em `master_empresas` (estado_1).
6. ⬜ Endpoint `POST /zips/upload` salvando em Large Object (OID, streaming).
7. ⬜ Endpoint `POST /zips/{id}/extrair` (síncrono no MVP).
8. ⬜ Importar `SOLUCOES_2025-06.zip` (menor, 340 MB) como teste.
9. ⬜ Importar 08 e 12.
10. ⬜ Iniciar frontend: rota `/explorador` + `ZipsList` mínimo.

---

## 11. REFERÊNCIAS CRUZADAS

| Conteúdo                                                  | Onde ler                                                                                                                                                       |
| --------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Por que 1 zip tem múltiplos perApur                       | [`md norte solucoes/explicacao todos eventos...md`](../../md%20norte%20solucoes/explicacao%20todos%20eventos%20que%20vem%20mes%20a%20mes%20do%20esocial.md) §4 |
| Tabela de tipos de evento (S-22xx, S-1210, S-5xxx, etc.)  | mesmo MD §3.2 e §3.3                                                                                                                                           |
| Cadastrais sem perApur                                    | mesmo MD §3.3                                                                                                                                                  |
| 1 CPF com vários S-1210 no mesmo mês                      | [`md norte solucoes/explicacao envio s1210 por cpf.md`](../../md%20norte%20solucoes/explicacao%20envio%20s1210%20por%20cpf.md) §2-§3                           |
| Roadmap original do Explorador                            | [`README.md`](../../README.md) §"Roadmap — Explorador de Arquivos"                                                                                             |
| Tokens visuais (Liquid Glass / Ghost Green / Blush Frost) | [`README.md`](../../README.md) §"Princípios visuais"                                                                                                           |
| Histórico narrativo da decisão                            | `C:\Users\xandao\Downloads\chat.json` (~1844 menções a Easy-eSocial-v2)                                                                                        |

---

> **Próximo passo concreto:** com este plano aprovado, executar item 2 do checklist (§10): scaffold do `backend/` no V2.
