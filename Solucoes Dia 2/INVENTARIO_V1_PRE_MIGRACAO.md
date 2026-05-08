# INVENTÁRIO V1 — Pré-Migração

> Data da varredura: **08 de maio de 2026**
> Origem: PC1 (`C:\Users\xandao\Documents\GitHub\Easy-Social`)
> Objetivo: mapear **tudo** que existe no V1 antes de iniciar a migração descrita em [`MIGRACAO_V1_V2.md`](./MIGRACAO_V1_V2.md). Garantir que **nada importante seja perdido**, especialmente dados/histórico da **APPA**.

---

## 0. TL;DR — descobertas críticas

| 🔴 Achado | Impacto | Ação |
|---|---|---|
| **Dados de produção da APPA NÃO estão no PC1** | risco zero aqui, mas precisa garantir backup PC2 + VPS antes de migrar | confirmar (no PC2) onde está o DB APPA "vivo" hoje (PC2 local? VPS?) — fazer 2 dumps independentes antes de qualquer ação |
| **V1 já é multi-DB**, não tenant-por-linha como pensávamos | arquitetura V1 ↔ V2 mais próxima do que parecia | confere: `easy_social_db` (APPA) + `easy_social_db_emp2` (SOLUCOES), com `master_empresas` mestre — **a estratégia "1 DB por empresa" do V2 é evolução natural, não disruptura** |
| **Cert APPA fora da pasta padrão** | cert mora em `python-scripts/certificados/cert_05969071000110_45C7EBE84F3FE665.pfx`, não em `_certificados_locais/` | mover/centralizar para `_certificados_locais/` antes da migração |
| **ARQUIVOS_RETORNO só tem out-dez/2025** | XMLs de retorno fev-set/2025 da APPA **NÃO foram salvos** | confirma o que [`MIGRACAO_V1_V2.md` §3.2](./MIGRACAO_V1_V2.md) já documentou: APPA migra com metadados only, sem XML completo histórico |
| **`backend/uploads/` tem 1.1 GB** | XLSX de DIRF, cruzamento, ficha financeira — anexos importados via UI V1 | decidir: migrar pra Supabase Storage? Manter local? Descartar (> 6 meses)? |
| **`_backups_db/` 505 MB** | backups Postgres de meses passados — ouro pra reconciliação ETL | preservar como read-only durante toda a migração |
| **APPA cert vence quando?** | coluna `validade` não existe mais — coluna foi removida | verificar PFX direto com OpenSSL antes de migrar |

---

## 1. Estrutura física top-level (PC1)

```
C:\Users\xandao\Documents\GitHub\Easy-Social\
├── backend/                  1235 MB  13632 arquivos  ← V1 Node + node_modules + uploads
├── _backups_db/               505 MB     73 arquivos  ← snapshots Postgres
├── python-scripts/            405 MB  17067 arquivos  ← scripts ETL/eSocial + venv local
├── .venv/                     283 MB  15427 arquivos  ← venv principal (gitignored)
├── ARQUIVOS_RETORNO/          238 MB   3621 arquivos  ← XMLs de retorno do governo (parcial!)
├── frontend/                  221 MB  10756 arquivos  ← V1 Vue + node_modules
├── .git/                       38 MB   1956 arquivos
├── supabase/                   23 MB     67 arquivos  ← (investigar — talvez exploração antiga)
├── relatorio_ana/              14 MB      5 arquivos  ← HTMLs gerados
├── docs/                        3 MB     88 arquivos  ← documentação histórica + RELATÓRIOS
├── setup-inicial/             0.2 MB      8 arquivos
├── transcricoes-call/         0.2 MB     18 arquivos
├── comunicacao-ia-geral/      0.2 MB     38 arquivos
├── Problemas APPA/            0.1 MB     31 arquivos  ← CASOS DE BUG/ESTUDO
├── Solucoes Dia 1/             —          3 arquivos  ← agosto/CICLO50
├── Solucoes Dia 2/             —          3 arquivos  ← este documento + outros
├── missoes/                    —          5 arquivos
├── _certificados_locais/       —          1 arquivo   ← SÓ tem PFX da Soluções
└── .vscode/, root files (.md, .py, .json, .xml)
```

---

## 2. Bancos de dados Postgres (localhost:5432)

| Banco | Tamanho | Conteúdo | Estado |
|---|---|---|---|
| **`easy_social_solucoes`** | **2829 MB** | V2 vivo (Soluções): 184k explorador_eventos, 16k timeline_envio_item, 162 envios | 🟢 produção atual |
| **`easy_social_db`** | 19 MB | V1 da APPA (estrutura) — só tem 1 row em master_empresas, certificados_a1, config_esocial; resto vazio | ⚠️ casca — dados reais não estão aqui |
| **`easy_social_master`** | 8 MB | usuarios + empresas + usuario_empresa + naturezas — todas com **0 linhas** | ⚠️ DDL antigo abandonado |
| coffee_candles | 8 MB | (irrelevante — outro projeto) | — |
| postgres | 8 MB | template — | — |

### 2.1. Tabela mestre `master_empresas` (no banco `easy_social_db`)

```
id | nome                                              | cnpj               | db_name             | host      | port | ativo
 1 | APPA SERVICOS TEMPORARIOS E EFETIVOS LTDA         | 05.969.071/0001-10 | easy_social_db      | localhost | 5432 | true
 2 | SOLUCOES SERVICOS TERCEIRIZADOS LTDA              | 09.445.502/0001-09 | easy_social_db_emp2 | localhost | 5432 | true
```

> ⚠️ `easy_social_db_emp2` **não existe** mais no PC1 (a Soluções migrou pra `easy_social_solucoes` no V2). E o `easy_social_db` aqui está vazio — os dados da APPA estão **em outro lugar** (PC2/VPS).

### 2.2. Tabelas no banco `easy_social_solucoes` (V2 vivo — top 10)

| Tabela | Linhas | Tamanho |
|---|---|---|
| explorador_eventos | 184.769 | 201 MB |
| timeline_envio_item | 16.103 | 4.4 MB |
| timeline_envio | 162 | 144 KB |
| explorador_atividade | 3 | 48 KB |
| explorador_importacoes | 3 | 32 KB |
| empresa_zips_brutos | 1 | 80 KB |
| master_empresas | 1 | 64 KB (só Soluções!) |
| timeline_mes | 1 | 56 KB |
| certificados_a1 | 0 | — |
| pipeline_cpf_results | 0 | — |

### 2.3. Tabelas V1 que existem na estrutura mas estão **vazias** em ambos DBs

`s1210_cpf_envios`, `s1210_cpf_scope`, `s1210_cpf_recibo`, `s1210_cpf_blocklist`, `s1210_lote1_codfunc_scope`, `s1210_xlsx`, `cruzamento_*` (8 tabelas), `analise_natureza*` (3 tabelas), `auditoria_naturezas`, `naturezas_esocial`, `tabela3_esocial_oficial`, `pipeline_*` (4 tabelas), `rubrica_corrections`, `correcoes_staging`, `esocial_envios`, `tabela_eb`, `eb_skills_base_legal`, `dinamica`, `senha_certificado_salva`.

> Conclusão: V1 tinha schema MUITO mais largo do que está em uso. Muitas tabelas eram protótipos abandonados. **A migração V2 só precisa cobrir as tabelas com dados reais** + as que o backend Node ainda lê em produção.

---

## 3. Certificados digitais

| Path | CNPJ | Empresa | Tamanho | Última mod |
|---|---|---|---|---|
| `_certificados_locais/SOLUCOES_SERVICOS_TERCEIRIZADOS_09445502000109.pfx` | 09445502000109 | Soluções | 3.7 KB | 04/05/2026 |
| `python-scripts/certificados/cert_05969071000110_45C7EBE84F3FE665.pfx` | **05969071000110** | **APPA** | 3.9 KB | 28/03/2026 |
| `python-scripts/certificados/cert_unknown_45C7EBE84F3FE665.pfx` | desconhecido | ? | 3.9 KB | 28/03/2026 |
| `python-scripts/tests/fixtures/certs/...` (2 arquivos) | fixtures | teste | — | — |

**Ação migração**:
1. Mover/copiar o cert APPA para `_certificados_locais/APPA_SERVICOS_TEMPORARIOS_05969071000110.pfx`.
2. Validar a senha (idem `Sol500424` para Soluções; APPA pode ter outra).
3. Verificar validade com OpenSSL: `openssl pkcs12 -in <pfx> -nodes -nokeys | openssl x509 -noout -dates`.
4. Identificar dono do `cert_unknown_*.pfx` ou descartá-lo.
5. **NUNCA** commitar PFX no git. Confirmar `.gitignore` blindado.

---

## 4. ARQUIVOS_RETORNO/ — XMLs do governo

| Mês | XMLs | MB |
|---|---|---|
| 2025-02 | 0 | 5.78 (só relatórios soltos) |
| 2025-10 | 360 | 16.7 |
| 2025-11 | 1.333 | 75.7 |
| 2025-12 | 1.871 | 100.4 |
| relatorios_lote1 | 0 | 1.0 |
| relatorios_por_lote | 0 | 22.9 |
| **TOTAL** | **3.564** | ~222 |

### Implicações

- **Out-dez/2025** estão preservados. Podem ser parseados e injetados em `explorador_eventos.xml_oid` da APPA pós-migração.
- **Fev-set/2025** ❌ não há XMLs salvos. APPA terá só metadados nesse período (V1 não guardou).
- **2026 (jan-abr)**: depende de onde foi rodado (PC2 ou VPS). Verificar se há `ARQUIVOS_RETORNO/` em outros PCs.

---

## 5. Backups de banco (`_backups_db/`)

- 505 MB / 73 arquivos
- README presente
- Subpastas:
  - `extract_v2/` — provável dumps recentes
  - `_pg17_tools/` — utilitários
  - Arquivo solto: `backfill_jan2025_pre_fix_2026-05-05_0119.json`

**Política durante migração**: pasta inteira fica **read-only** até pós-cutover. É a fonte de verdade para reconciliação ETL.

---

## 6. `python-scripts/` — scripts críticos (405 MB total)

### 6.1. Distribuição

- `venv/`: 376 MB (descartável — recriar com `requirements.txt`)
- `esocial/`: 1.2 MB / 60 arquivos — **núcleo da lógica eSocial V1**
- `tests/`: 1.1 MB / 42 arquivos
- `saida_lote*/` (10+ pastas): saídas históricas de envios em lote (jun-dez 2025)
- `_chat_export_summary/`: 7.7 MB
- `referencias/`: 0.7 MB

### 6.2. Scripts top-level (amostra — há centenas)

`bot_api.py`, `bot_esocial.py` (22.9 KB — provável **maior peça da automação**), `audit_tprubr_completo.py`, `batch_s1010_producao.py`, `batch_retry_15.py`, dezenas de `check_*.py`/`check_*.sql`, `analise_final_natrubr.py`, etc.

**Risco de migração**: muitos scripts foram one-shot (rodaram 1 vez). Outros são produção. Precisa **inventário fino** depois — definir quais portar pro V2 vs descartar vs documentar como histórico.

---

## 7. `backend/` (V1 Node + frontend builds + uploads)

| Subpasta | MB | Observação |
|---|---|---|
| `uploads/` | **1109 MB** | XLSX importados pela UI V1 (DIRF, cruzamento) — investigar política |
| `node_modules/` | 126 | descartável (recria com `npm install`) |
| `src/` | 0.26 | **CÓDIGO REAL — 23 arquivos** |
| `dist/` | 0.24 | build TS — descartável |

### 7.1. Rotas V1 (`backend/src/routes/`)

| Rota | KB | Função |
|---|---|---|
| `adminRoutes.ts` | 13.7 | painel admin |
| `cruzamentoRoutes.ts` | 15.3 | cruzamento natureza/rubrica |
| `tableRoutes.ts` | 10.5 | leitura/escrita das tabelas mestras |
| `naturezaRoutes.ts` | 6.8 | naturezas eSocial |
| `validationRoutes.ts` | 4.9 | validações |
| `authRoutes.ts` | 4.7 | login + JWT (bcrypt) |
| `upload.routes.ts` + `uploadRoutes.ts` | 3.2 | upload XLSX (multer) |

### 7.2. `backend/uploads/` — 22 arquivos grandes

- 6× XLSX de **DIRF 2025** (~127 MB cada = ~764 MB) — duplicados
- 3× XLSX de **40 MB** (provável Domínio crus)
- 11× XLSX `cruzamento-...An__lise_Natureza_Certa...` (~58 KB cada)

**Decisão pendente**: deduplicar (manter 1 cópia de cada DIRF), arquivar em S3-compat ou descartar?

---

## 8. `frontend/` (V1 Vue)

- 221 MB / 10756 arquivos — predominantemente `node_modules/`
- Código fonte está aqui (a investigar `frontend/src/` em pass posterior)
- **Política**: V1 frontend será desligado quando o V2 frontend for promovido. Manter como referência só.

---

## 9. Documentação histórica (`docs/` + raiz)

### 9.1. `docs/` — 88 arquivos / 69 MDs

#### Subpastas
- `backup_preenvio_lote1/` (9 arquivos)
- `como enviar s1210 em lotes 1 2 3 4/` (3)
- `missao-08-04-2026/` (3)
- `MISSOES_APPA_FEVEREIRO_MARCO_ABRIL/` (11)
- `prontuario_sandro/` (2)
- `RELATORIOS_L1_2025/` (1)
- `RELATORIOS_L2_2025/` (13)

#### Top-level recentes (mais relevantes)
- `GUIA_MONTAGEM_S1210.md` (19.3 KB) — guia técnico vivo
- `explicacao envio s1210 por cpf.md` (10.7 KB)
- `explicacao todos eventos que vem mes a mes do esocial.md` (16.9 KB)
- `RELATORIO_LOTE1_DEZEMBRO_2025.md` (7.5 KB)
- `S1210_ANUAL_PERFEITO_ARQUITETURA.md` (10 KB)
- `MEGA_AUDITORIA_TABELAS.md` (11.9 KB)
- `INCIDENTE_PC2_24-04-2026_SCOPE_DELETADO.md` — fundamental (incidente)
- `RELATORIO_BUG_PLANSAUDE.md/.html` — caso aberto
- `DEPLOY_VPS_STATUS.md`, `DEPLOY_84dcf14.md` — referência VPS

### 9.2. `Problemas APPA/` — 31 MDs

Casos clínicos de bugs/exceções específicas da APPA. Todos relevantes para validação pós-migração:

- `426CPFS_PLANSAUDE_DOBRADO.md`
- `67CPFS_SINTACLUNS_PLANSAUDE_FANTASMA.md`
- `BUG_PLANSAUDE_VALORES_INFLADOS.md`
- `CASO_RANIERI_DEMISSAO_MATERNIDADE.md`
- `DEDUCAO_DEPENDENTES_SETEMBRO.md`
- `DUPLICIDADE_S1210_JANEIRO_100CPFS.md`
- `ERRO_PRECEDENCIA_PENSAO_ACORDO.md`
- `RUBRICA_522_INCIDENCIA_IR_ERRADA.md` / `RUBRICA_566_INSS_INCIDENCIA_IR.md`
- `S1010_RUBRICAS_PENDENTES.md`
- `VERBAS_INDENIZATORIAS_RESCISAO_ZERADAS.md`
- `OPERADORA_MUDANCA_SETEMBRO_2025.md`
- `PROBLEMA_APPA.md` (root case)
- + 19 outros

> Estes MDs descrevem **regras de negócio** da APPA. Devem virar **checklist de validação** pós-ETL. Cada MD = 1 cenário de teste a reproduzir no V2.

### 9.3. `missoes/`
5 arquivos: `MISSAO.md`, `MISSAO_14_04.md`, `MISSAO_15_04.md`, `MISSAO_16_04.md`, `MISSAO_774_607.md`.

---

## 10. Outras pastas relevantes

| Pasta | Conteúdo | Migração? |
|---|---|---|
| `relatorio_ana/` | HTMLs gerados (relatórios de fechamento) | manter como artefatos históricos |
| `transcricoes-call/` | transcrições de calls (Ana e outros) | manter — contexto de regras |
| `comunicacao-ia-geral/` | trocas com IA (Enviada/Recebida) | descartável após migração |
| `setup-inicial/` | scripts de setup ambiente | atualizar/portar |
| `supabase/` | **investigar** — pode ser exploração inicial Supabase já feita | revisar antes de Phase 2 |
| `_certificados_locais/` | só Soluções — APPA precisa entrar | mover cert APPA pra cá |
| `Solucoes Dia 1/` | Guard rail 543/202 + relatórios agosto | já documentação V2 |
| `Solucoes Dia 2/` | esta missão (3 MDs) | atual |

---

## 11. O que está **fora do PC1** (precisa confirmar quando estiver no PC2)

| Item | Onde provavelmente está | Como confirmar |
|---|---|---|
| **DB APPA produção real** | PC2 ou VPS Hostinger | rodar `\l` no Postgres do PC2 + `\dt` em `easy_social_db` lá |
| **Certificados APPA atualizados** | PC2 ou VPS | comparar SHA dos PFX |
| **XMLs de retorno fev-set/2025** | provável que **não foram salvos** em parte alguma | aceitar perda — V2 só com metadados |
| **XMLs de retorno jan-abr/2026** | PC2 (`ARQUIVOS_RETORNO/`) | sincronizar antes da migração |
| **Logs de envio históricos** | PC2 | sincronizar |
| **Configurações VPS atual** | servidor Hostinger | dump de `/opt/easy-social` (V1 hoje rodando) + Nginx config + systemd |

---

## 12. Inventário completo do estado atual da APPA (a preencher com PC2)

> ⚠️ **Esta seção precisa ser preenchida ANTES de começar Phase 1 da migração.**

```
[ ] CNPJ confirmado:               05.969.071/0001-10
[ ] Cert PFX e senha confirmadas:  ___________________
[ ] Validade do cert:              ___ / ___ / ____
[ ] DB host atual (PC2 ou VPS):    ___________________
[ ] DB nome:                       easy_social_db (provável)
[ ] Total de CPFs em escopo:       ___________________
[ ] Total de eventos enviados:     ___________________
[ ] Período coberto:               ___ / 2025 → ___ / 2026
[ ] Último envio S-1210 com sucesso: data ___ / mês ___
[ ] Último envio S-1010:           data ___
[ ] Pendências em aberto:          ver "Problemas APPA/" — qtd: 31 casos
[ ] Backup mais recente do DB:     data ___ / tamanho ___ MB
```

---

## 13. Pré-requisitos antes de iniciar Phase 0 da migração

1. ✅ Inventário V1 completo (este documento).
2. 🟡 **Sincronizar ARQUIVOS_RETORNO/ do PC2** para o PC1 ou VPS (out-dez/2025 + 2026).
3. 🟡 **Pg_dump da APPA** (no PC2/VPS onde estiver vivo) → 2 cópias independentes:
   - `_backups_db/appa_v1_pre_migracao_2026-05-08.sql.gz` (PC1)
   - cópia segunda em pendrive/cloud
4. 🟡 **Mover cert APPA** de `python-scripts/certificados/` para `_certificados_locais/APPA_*.pfx`.
5. 🟡 **Verificar `.gitignore`**: PFX, .env, _backups_db/, ARQUIVOS_RETORNO/ todos blindados.
6. 🟡 **Fase 0 da MIGRACAO_V1_V2.md** (commits emergenciais V2 backend) — separado mas concorrente.
7. 🟡 **Confirmar pendências APPA**: lista de pendências em aberto (Problemas APPA/) que NÃO podem ficar sem solução pós-migração.

---

## 14. Riscos identificados

| Risco | Probabilidade | Impacto | Mitigação |
|---|---|---|---|
| Dump APPA corrompido/incompleto | baixa | catastrófico | 2 dumps independentes + validar com `pg_restore --list` |
| Cert APPA vencido durante migração | média | alto (não consegue enviar) | renovar antes de iniciar; ter cert reserva |
| 31 casos de "Problemas APPA" não cobertos no V2 | alta | médio (validações falham na UI) | virar suite de testes de aceitação |
| ETL perder linhas por encoding/charset | média | alto | comparar `COUNT(*)` por tabela origem vs destino |
| XLSX `backend/uploads/` perdidos | baixa (são duplicados) | baixo | deduplicar e arquivar |
| Timeline V1 (218k tentativas) explodir tabela V2 | média | médio | criar `historico_tentativas_cpf` separado, manter HEAD em `timeline_envio_item` |

---

## 15. Próximos passos imediatos (ordem sugerida)

1. **Hoje** — preencher §11 e §12 (precisa estar no PC2).
2. **Hoje** — Fase 0 emergencial: commits V2 backend (autorização do usuário).
3. **D+1** — pg_dump APPA do PC2/VPS + sincronizar ARQUIVOS_RETORNO.
4. **D+2** — começar Phase 1 da [`MIGRACAO_V1_V2.md`](./MIGRACAO_V1_V2.md): inventário fino do código V1 (rotas Node + scripts Python que ainda rodam em produção).
5. **D+3** — Phase 2: setup Supabase + schema padrão + DB Sistema.

---

## 16. Checklist final "podemos começar?"

```
[ ] §11 preenchido (no PC2)
[ ] §12 preenchido (no PC2)
[ ] §13.2 sincronização XMLs feita
[ ] §13.3 dump APPA em 2 cópias
[ ] §13.4 cert APPA centralizado
[ ] §13.5 .gitignore auditado
[ ] §13.6 Phase 0 V2 commitado
[ ] §13.7 autorização explícita do dono
```

> Quando todas as caixas estiverem marcadas, pode-se iniciar Phase 1 com tranquilidade.
