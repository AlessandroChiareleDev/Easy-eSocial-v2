# MISSÃO MIGRAÇÃO V1 → V2 — Soluções Dia 2

> **Data de início**: 08/05/2026
> **Status**: planejamento (não executado)
> **Marco anterior**: APPA fechada (110.651 CPFs S-1210 + S-1299, fev/2025–abr/2026), 100% conciliada
> **Objetivo**: aposentar V1 como sistema operacional e elevar V2 ao posto de **sistema único**, incluindo VPS, banco e frontend

---

## 1. Contexto — onde estamos hoje

### 1.1. Dois repositórios, dois mundos

| | **V1 — `Easy-Social`** | **V2 — `Easy-eSocial-v2`** |
|---|---|---|
| **Backend** | Node.js + TypeScript + Express | **Python + FastAPI** (NOVO) |
| **Frontend** | Vue legado | Vue 3 + TS strict + Tailwind v4 (Liquid Glass / Ghost Green) |
| **Banco** | Postgres (1 banco compartilhado por todas as empresas, multi-tenant por linha) | Postgres (mesma DB hoje, mas vai virar **1 DB por empresa no Supabase**) |
| **Storage de XML retorno** | Salva só protocolo + recibo no banco. **Não tem XML completo do governo por pessoa.** | Salva XML completo por evento em `lobject`/storage. Permite reconstrução total. |
| **Deploy** | VPS Hostinger — `easyesocial.com.br` (vivo) | Sem deploy. Roda só local. |
| **Tested at scale** | APPA fechou 110k CPFs com ele | CICLO100 validou Soluções (13.646 CPFs / 2,79% erro) |
| **Auth** | JWT + bcrypt funcionando | Não existe |
| **Upload Domínio** | Funciona (XLSX/cruzamento) | Não existe |
| **Validação rubrica/natureza** | Funciona | Não existe |

### 1.2. A frase que define a missão

> *"o V2 não pode ter aspectos a menos que o V1 — ele tem que ter tudo do V1, mais coisa, e aposentar o V1."*

Em particular **3 capacidades novas exclusivas do V2** que o V1 nunca terá:

1. **XML completo do governo por CPF** (V1 só tem protocolo). O V2 baixa, descompacta, indexa por `tipo_evento` × `cpf` × `per_apur` e disponibiliza pra UI Explorador.
2. **Chain walk de eventos** — linha do tempo amarrada (`S-2200 → S-1200/S-1210 → S-2299`).
3. **Multi-tenant por banco separado** (1 Supabase DB por empresa). V1 mistura tudo num banco só.

### 1.3. O que está rodando agora em produção

- VPS Hostinger serve `easyesocial.com.br` rodando **V1** (Node + Vue legado).
- A Rafa (operadora APPA) usa o V1 todos os dias para fechar S-1210, validar rubricas, gerar relatórios.
- Banco do V1 contém **todo o histórico APPA** (110k CPFs, recibos, status, missões).
- Soluções foi enviada via **scripts locais** (CICLO100 + `envio_paralelo_v2`) **fora do site** — não passou pela UI.

### 1.4. O ponto de virada

A APPA acabou de fechar. **Janela perfeita** para:
- Migrar a Rafa do V1 pro V2 sem pressão de fechamento mensal em curso.
- Preservar 100% dos dados da APPA num banco isolado.
- Soluções já entra no V2 com XML completo (que o V1 nunca teve).

---

## 2. Arquitetura-alvo (resumo)

> Detalhamento completo no arquivo [`ARQUITETURA_MULTI_EMPRESA.md`](./ARQUITETURA_MULTI_EMPRESA.md).

```
                    ┌──────────────────────────────────┐
                    │        easyesocial.com.br         │
                    │       (VPS Hostinger única)       │
                    │       Build: V2 (Vue 3 + TS)      │
                    └──────────────────┬───────────────┘
                                       │
                    ┌──────────────────▼───────────────┐
                    │     Backend V2 (FastAPI/Python)   │
                    │     auth + upload + envio + UI    │
                    └──────────────────┬───────────────┘
                                       │
                    ┌──────────────────┴────────────────┐
                    │       Roteador por empresa         │
                    │   (CNPJ → connection string DB)    │
                    └─────┬─────────────┬────────────────┘
                          │             │
            ┌─────────────▼┐  ┌─────────▼─────────┐
            │ Supabase APPA │  │ Supabase SOLUÇÕES │   ... outras empresas
            │   (DB único)  │  │   (DB único)      │       (1 DB cada)
            │   schema X    │  │   schema X        │
            │   (idêntico)  │  │   (idêntico)      │
            └───────────────┘  └───────────────────┘
```

**Princípios:**

1. **1 DB por empresa no Supabase** — isolamento total. Se eu queimar o DB Soluções, APPA continua intacta.
2. **Schema idêntico entre todos os DBs** — uma migration source-of-truth aplicada em todos.
3. **V2 conhece N empresas** via tabela mestra (no banco do sistema, fora dos DBs-cliente) que mapeia `cnpj → supabase_url + schema_version + flags`.
4. **APPA migra como está** — sem XML completo (V1 não tinha). Ela continua com a UI V2 mas com aviso "evento sem XML disponível" pra registros antigos.
5. **Soluções entra com XML completo** — todas as importações futuras + reimportações vão popular `lobject`/storage com XML por evento.

---

## 3. Fases da missão

### **Fase 0 — Salvamento de emergência (HOJE)**

> Bloqueador absoluto. Se HD falhar, perdemos `envio_paralelo_v2` e o fix `_gerar_id`.

| # | Ação | Repo | Tempo |
|---|---|---|---|
| 0.1 | Reforçar `Easy-eSocial-v2/backend/.gitignore` (bloquear `.env`, `*.pfx`, `_*.py`, `_*.log`, `envio_*.log`, `*.err`) | V2 | 5 min |
| 0.2 | Commit V2 `backend/` inteiro pela primeira vez | V2 | 10 min |
| 0.3 | Commit V2 `src/` (router, stores, painéis multi-tenant) | V2 | 5 min |
| 0.4 | Commit V1 — pasta `Solucoes Dia 2/` + docs novos do dia | V1 | 5 min |
| 0.5 | `git push` nos dois | ambos | 2 min |

### **Fase 1 — Inventário e classificação V1**

Já foi 60% feito (relatório do dia 08/05). Falta:
- Decidir destino de `python-scripts/saida_*` (centenas de pastas — propõe-se mover só amostras representativas pra `archive/scripts_legados/` no V2).
- Decidir destino dos `*.log` raiz V1 (ir pra `archive/logs_envio/`).
- Listar com a Ana/Rafa quais MDs de `docs/` ainda são consultados ativamente.

### **Fase 2 — Schema padrão + Supabase setup**

| # | Entregável |
|---|---|
| 2.1 | Reunir migrations atuais do V2 (`backend/migrations/`) num **schema único versionado** (ex.: `schema_v1.0.0.sql`). |
| 2.2 | Criar projeto Supabase `appa-prod` e aplicar schema. |
| 2.3 | Criar projeto Supabase `solucoes-prod` e aplicar mesmo schema. |
| 2.4 | Criar tabela mestra `empresas_routing` (no banco do sistema V2) com `cnpj`, `db_url`, `db_anon_key`, `db_service_key`, `nome`, `flags`. |
| 2.5 | Implementar **DB router** no backend FastAPI — ao receber requisição autenticada, resolver empresa do JWT e abrir conexão no DB certo. |
| 2.6 | Implementar **migration runner** que aplica `schema_vX.Y.Z.sql` em todos os DBs cadastrados (ordem garantida + transação). |

### **Fase 3 — Migração APPA (do banco V1 atual → Supabase APPA)**

> APPA mantém suas particularidades (sem XML completo). Frontend mostra "XML não disponível" para eventos pré-V2.

| # | Entregável |
|---|---|
| 3.1 | Dump completo do banco V1 atual filtrando `empresa_id=APPA` em todas as tabelas. |
| 3.2 | Mapeamento de tabelas V1 → V2 (algumas mudaram de nome/forma). |
| 3.3 | Script ETL `migrate_appa_v1_to_v2.py` que lê do dump e popula Supabase APPA. |
| 3.4 | Conferência: total CPFs no V1 == total CPFs no Supabase APPA. Histograma idêntico. |
| 3.5 | Smoke test pela Rafa em ambiente staging. |

### **Fase 4 — Funcionalidades faltantes no backend V2**

Portar do Node V1 → Python V2:

| # | Funcionalidade | V1 (Node) | V2 (Python) |
|---|---|---|---|
| 4.1 | Auth JWT + bcrypt | `authRoutes.ts` | criar `app/auth.py` com `pyjwt` + `passlib` |
| 4.2 | Upload XLSX Domínio | `uploadRoutes.ts` | criar `app/upload_dominio.py` com `openpyxl` |
| 4.3 | Validação rubrica | `services/rubrica-validation-service.ts` | criar `app/validacao_rubrica.py` |
| 4.4 | Validação natureza | `services/natureza-validation-service.ts` | criar `app/validacao_natureza.py` |
| 4.5 | Cruzamento contábil | `cruzamentoRoutes.ts` | criar `app/cruzamento.py` |
| 4.6 | Tabelas S-1000/1005/1010 | `tableRoutes.ts` | já existe parcial em `app/tabela.py` (auditar) |

### **Fase 5 — Build V2 + frontend conectado**

| # | Entregável |
|---|---|
| 5.1 | `Easy-eSocial-v2/src/services/` apontar todas as chamadas pra backend V2 (FastAPI port `8001`). |
| 5.2 | Adicionar interceptor Axios que injeta JWT e CNPJ ativo (header `X-Empresa-CNPJ`). |
| 5.3 | Tela de seleção de empresa (`EmpresaSelectView.vue` já existe — terminar). |
| 5.4 | Build de produção: `npm run build` gera `dist/` otimizado. |

### **Fase 6 — Deploy VPS (PONTO DE VIRADA)**

> A partir daqui o V1 sai do ar.

| # | Entregável |
|---|---|
| 6.1 | Provisionar VPS Hostinger atual com **stack V2**: Nginx + uvicorn + frontend `dist/`. |
| 6.2 | Configurar variáveis de ambiente: `SUPABASE_APPA_URL`, `SUPABASE_SOLUCOES_URL`, `JWT_SECRET`, `CERT_BASE_PATH`. |
| 6.3 | Mover certificados `.pfx` pro VPS em `/etc/easy-esocial/certs/` (modo 600, owner `esocial`). |
| 6.4 | DNS continua apontando pra mesma VPS — só troca o build. |
| 6.5 | Smoke test em produção: login Rafa, ver APPA, ver Soluções, fechar 1 lote teste. |
| 6.6 | Anúncio pra Rafa + Ana: "subiu V2, V1 fora do ar". |

### **Fase 7 — Aposentadoria V1**

| # | Entregável |
|---|---|
| 7.1 | Repo V1 em modo read-only (GitHub: archive). |
| 7.2 | Banco V1 antigo: backup full + retenção 12 meses + read-only. |
| 7.3 | `easyesocial.com.br` 100% V2. |

---

## 4. Riscos & mitigações

| Risco | Probabilidade | Impacto | Mitigação |
|---|---|---|---|
| Perder dados APPA na migração ETL | baixa | catastrófico | dump V1 + checksum por tabela antes de subir Supabase |
| Schema diverge entre Supabase APPA e Soluções | média | alto | migration runner aplica em **todos** os DBs ou aborta |
| JWT V2 difere semântica V1 → Rafa não loga | média | médio | importar usuários V1 mantendo `password_hash` bcrypt (compatível) |
| Certificado .pfx não acessível no VPS | alta | crítico | testar antes em staging, com path absoluto e perms 600 |
| Build V2 quebra em produção (algum CSS Tailwind v4) | média | médio | smoke test Lighthouse antes de DNS final |
| Rafa não consegue subir XLSX Domínio (rota nova) | alta | alto | validar rota `/api/upload/dominio` com mesmo XLSX que ela usou na última semana antes do go-live |
| Algum endpoint Node V1 era usado por integração externa não documentada | média | médio | log de acesso V1 últimos 30 dias antes de derrubar |
| `lobject` Postgres pra XML completo cresce demais | média | médio | política de compressão zstd + retenção de retornos brutos < 1 ano em quente, > 1 ano em frio |

---

## 5. Estado de prontidão (08/05/2026)

| Componente | Pronto | Faltando |
|---|---|---|
| Backend V2 — envio S-1210 paralelo | ✅ (CICLO100 valida) | — |
| Backend V2 — chain walk + explorador | ✅ | — |
| Backend V2 — auth/upload/validação | ❌ | portar do V1 |
| Frontend V2 | 80% | services apontados pro backend V2; tela seleção empresa |
| Schema multi-empresa | ❌ | consolidar migrations + criar `empresas_routing` |
| Supabase APPA | ❌ | provisionar |
| Supabase Soluções | ❌ | provisionar |
| ETL APPA V1→V2 | ❌ | escrever |
| Deploy V2 no VPS | ❌ | configurar Nginx/uvicorn |
| Certificados em `/etc/` | ❌ | mover do path local |
| Documentação | ✅ ciclo100.md, este MD, ARQUITETURA_MULTI_EMPRESA.md | — |

---

## 6. Decisões pendentes (perguntas que a missão precisa responder)

1. **Provider Supabase**: usar Supabase Cloud (managed) ou Postgres self-hosted no próprio VPS? *Recomendação: Supabase Cloud por backup/HA out-of-the-box.*
2. **Tabela `empresas_routing` mora onde?** Num banco "sistema" separado no Supabase, ou no Supabase APPA (porque é o primário)? *Recomendação: banco sistema separado pra não acoplar.*
3. **Como Rafa vê APPA pré-V2 no Explorador**? Mostrar "evento sem XML — só metadados V1"? *Recomendação: sim, com badge "histórico V1".*
4. **Tempo de paralelismo V1+V2 no VPS**: subir V2 numa subdomain (`v2.easyesocial.com.br`) e migrar Rafa gradualmente, ou cutover direto? *Recomendação: subdomain por 7 dias, depois cutover.*
5. **Retenção dos backups V1**: 12 meses parece ok? *(Confirmar com Ana.)*

---

## 7. Próximo passo imediato

Executar **Fase 0** ainda hoje (08/05/2026). Depois agendar Fase 1 e Fase 2 para a semana 12–18/05.

> Documentos relacionados:
> - [`ARQUITETURA_MULTI_EMPRESA.md`](./ARQUITETURA_MULTI_EMPRESA.md) — detalhe técnico do multi-banco e XML completo
> - [`ciclo100.md`](./ciclo100.md) — técnica de envio massivo já validada
