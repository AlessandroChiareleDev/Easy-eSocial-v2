# Explicação: TODOS os eventos que vêm mês a mês do eSocial

> Documento técnico-detalhado do que descobrimos lendo os ZIPs baixados do eSocial — APPA e SOLUCOES — em **maio/2026**.
> Foco: explicar **por que um zip "do mês X" tem eventos de vários meses diferentes** e como o sistema lida com isso.

---

## 1. O QUE EU DESCOBRI EM 30 SEGUNDOS

1. **O nome do ZIP NÃO é confiável** — quem baixou nomeou pelo "mês de transmissão" ou "mês de download", não pelo mês de competência.
2. **O que importa é o `<perApur>` DENTRO do XML** — esse sim é o mês oficial da folha (competência).
3. **Folha de junho é transmitida em julho.** Por isso o zip antigo `mes 07 2025 solucoes.zip` continha XMLs com `<perApur>2025-06</perApur>`. **Não tem bug. É a regra do eSocial.**
4. **Um zip de "fechamento" sempre traz lixo de períodos antigos** (recálculos, 13º, processos trabalhistas, exclusões retroativas).
5. **Eventos cadastrais (S-22xx, S-1010, etc) NÃO têm `<perApur>`** — eles não pertencem a mês de folha. Pertencem ao trabalhador/empresa.

Padrão de nome estabelecido para evitar confusão pra sempre:

```
NOMEEMPRESA_YYYY-MM.zip
```

onde `YYYY-MM` é o **perApur dominante** (mês de competência), NÃO a data de download.

---

## 2. EVIDÊNCIA EMPÍRICA — APPA vs SOLUCOES

### 2.1 APPA — `xmls do e social mes a mes` (13 zips)

A APPA nomeou **certo** (por competência):

| Arquivo          | Total XMLs | S-1210 | perApur dominante                  |
| ---------------- | ---------: | -----: | ---------------------------------- |
| 01-jan2025.zip   |    141.004 | 22.687 | **2025-01** ✅                     |
| 02-fev2025.zip   |    136.742 | 21.602 | **2025-02** ✅                     |
| 03-marc2025.zip  |    135.193 | 20.772 | **2025-03** ✅                     |
| 04-abril2025.zip |    135.670 | 20.169 | **2025-04** ✅                     |
| 05-maio.zip      |    125.882 | 20.510 | **2025-05** ✅                     |
| 06-Jun2025.zip   |    117.722 | 19.234 | **2025-06** ✅                     |
| 07- Jul2025.zip  |    111.321 | 18.327 | **2025-07** ✅                     |
| 08- ago2025.zip  |    101.071 | 16.264 | **2025-08** ✅                     |
| 09-set2025.zip   |     98.239 | 15.542 | **2025-09** ✅                     |
| 10-out2025.zip   |     43.765 |  7.733 | **2025-10** ✅                     |
| 11-nov2025.zip   |     57.996 |  7.018 | **2025-11** ✅                     |
| 12-dez2025.zip   |     46.524 |  7.959 | **2025-12** ✅                     |
| 02-fev2025.NOVO  |    141.004 | 22.687 | 2025-01 (duplicata de janeiro!) ⚠️ |

> **Aprendizado APPA:** convenção limpa. 1 zip = 1 mês de competência. Único pegadinha: `02-fev2025.NOVO-NAOAJUDOU.zip` é cópia de janeiro com nome trocado.

### 2.2 SOLUCOES — `todos os meses 2025 SOLUCOES` (3 zips)

A SOLUCOES nomeou **errado** (por mês de transmissão). Renomeei pro padrão correto:

| Nome ANTIGO (transmissão)  | Nome NOVO (competência) | Total XMLs | perApur DENTRO do XML           |
| -------------------------- | ----------------------- | ---------: | ------------------------------- |
| `mes 07 2025 solucoes.zip` | `SOLUCOES_2025-06.zip`  |     83.548 | **2025-06** (folha de junho)    |
| `mes 09 2025 solucoes.zip` | `SOLUCOES_2025-08.zip`  |    198.153 | **2025-08** (folha de agosto)   |
| `solcuoes 12-2025.zip`     | `SOLUCOES_2025-12.zip`  |    192.512 | **2025-12** (folha de dezembro) |

**Faltam meses (SOLUCOES):** janeiro, fevereiro, março, abril, maio, julho, setembro, outubro, novembro/2025.

---

## 3. POR QUE 1 ZIP TEM EVENTOS DE VÁRIOS MESES — O ZIP DE DEZEMBRO/2025

Tomei `SOLUCOES_2025-12.zip` (192.512 XMLs lidos 100%, sem amostragem) e mapeei o `<perApur>` de cada evento.

### 3.1 Distribuição geral

| perApur                    | Eventos |          % | Comentário                                   |
| -------------------------- | ------: | ---------: | -------------------------------------------- |
| **2025-12**                | 185.897 | **99,4 %** | Período principal (folha de dez/2025)        |
| **2026-01**                |     889 |      0,5 % | 13º salário + fechamento empresa             |
| 2014→2025-11 (38 períodos) |     ~75 |      0,1 % | Resíduos: recálculos, processos trabalhistas |
| `2025` (sem mês)           |      16 |      0,0 % | Eventos anuais (S-1299/1298 fechamento)      |
| **Cadastrais sem perApur** |   5.575 |        n/a | Admissão, desligamento, ASO, etc.            |

### 3.2 Quebra por TIPO de evento

| Tipo                       |  Total | perApur principal  | Resíduo                                                 |
| -------------------------- | -----: | ------------------ | ------------------------------------------------------- |
| S-5002                     | 48.366 | 2025-12 (100 %)    | nada                                                    |
| S-1210                     | 32.170 | 2025-12 (100 %)    | nada                                                    |
| S-5001                     | 30.899 | 2025-12 (98,6 %)   | **424 em 2026-01** (13º salário INSS)                   |
| S-5003                     | 30.899 | 2025-12 (98,6 %)   | **424 em 2026-01** (13º salário FGTS)                   |
| S-1200                     | 28.203 | 2025-12 (100 %)    | 4 com perApur=`2025` (anual)                            |
| S-3000                     | 16.263 | 2025-12 (100 %)    | 65 sem perApur (exclusões puras)                        |
| S-5503                     |     39 | espalhado          | 15 períodos diferentes (2023-10 → 2026-01)              |
| S-5501                     |     36 | **2026-01** (94 %) | Totalizadores empresa do fechamento de 2025             |
| S-2500                     |     39 | espalhado          | **29 períodos de 2014 a 2026** (processos trabalhistas) |
| S-1299/5011/5012/5013/1298 |     23 | 2025-12 + `2025`   | Fechamento + totalizadores anuais                       |

### 3.3 Eventos cadastrais (sem `<perApur>`)

Esses **não pertencem a mês de folha**. Pertencem ao trabalhador ou à empresa. Se importar com `per_apur=NULL` ou jogar no mês do envio (tanto faz pra contabilidade).

| Tipo      | Qtd no zip dez | O que é                               |
| --------- | -------------: | ------------------------------------- |
| S-2299    |          2.685 | Desligamento de trabalhador           |
| S-2200    |          1.635 | Admissão de trabalhador               |
| S-2230    |            344 | Afastamento temporário                |
| S-2220    |            333 | ASO (atestado de saúde ocupacional)   |
| S-2206    |            275 | Alteração de contrato de trabalho     |
| S-2240    |            145 | EPI / risco                           |
| S-2205    |            109 | Alteração de dados cadastrais         |
| S-2501    |             34 | Processo trabalhista — info de pagto  |
| S-2221    |              4 | Toxicológico motorista                |
| S-1010    |              4 | Tabela de rubricas                    |
| S-1020    |              2 | Tabela de lotações                    |
| S-3500    |              2 | Exclusão de evento não-periódico      |
| S-2210    |              2 | Comunicado de acidente (CAT)          |
| S-8200    |              1 | Anotação judicial                     |
| **TOTAL** |      **5.575** | **NÃO entram em "folha de dezembro"** |

---

## 4. POR QUE EVENTOS DE OUTROS PERÍODOS APARECEM NUM ZIP "MENSAL"?

### 4.1 13º salário (perApur = janeiro do ano seguinte)

> **424 S-5001 + 424 S-5003 com `perApur=2026-01`.**
>
> Como funciona: a 2ª parcela do 13º salário tem **competência própria**, codificada como `perApur=ANO+1-01` no eSocial (ou em alguns casos com indicador específico de 13º). O fechamento de dezembro **arrasta** esses eventos junto.

### 4.2 Fechamento de empresa — totalizadores S-5501/S-5503

> **34 dos 36 S-5501 estão em `2026-01`.**
>
> Esses são "totalizadores empregador" emitidos PELO eSocial em resposta ao S-1299 de fechamento de dezembro. Como o sistema processa em janeiro, ele datou em `2026-01`. **Cuidado:** se filtrar S-5501 só por `per_apur=2025-12`, vai perder os totalizadores principais.

### 4.3 Recálculos retroativos — S-5503 (FGTS empresa)

> **39 S-5503 espalhados em 15 períodos diferentes** (2023-10, 2023-11, 2023-12, 2024-08, 2025-02, 03, 04, 06, 07, 08, 09, 10, 11, 12, 2026-01).
>
> Acontece quando empresa **retifica** uma folha antiga: o eSocial recalcula o FGTS da competência original e devolve um S-5503 NOVO carimbado com a competência corrigida. No download de dezembro, vieram acumulados todos os recálculos pendentes.

### 4.4 Processo trabalhista — S-2500

> **39 S-2500 distribuídos em 29 períodos diferentes** (`2014-10` até `2026-01`).
>
> Cada processo trabalhista carrega o `perApur` do **fato trabalhado/julgado**, não do envio. Se um juiz mandou pagar diferenças de outubro/2014, vem `<perApur>2014-10</perApur>` no S-2500. Por isso aparece "lixo histórico" no zip recente.

### 4.5 Eventos anuais — perApur = `2025` (sem mês)

> **16 eventos com `perApur=2025`** (não `2025-12`).
>
> O eSocial aceita formato `YYYY` para alguns eventos consolidados de fechamento anual (S-1299, S-1298, S-5011, S-5012, S-5013). Não é bug — é o esquema XSD oficial.

### 4.6 Exclusões sem perApur — S-3000

> **65 dos 16.263 S-3000 sem perApur.**
>
> Quando uma exclusão se refere a evento NÃO-PERIÓDICO (cadastral), ela não traz perApur porque o evento original também não tinha.

---

## 5. COMO O SISTEMA (Easy-Social V2 + bot_api) JÁ LIDA COM ISSO

**Arquivo:** `python-scripts/esocial/explorador_routes.py`

### 5.1 Schema do banco

```sql
-- linha 88
per_apur VARCHAR(7)   -- formato 'YYYY-MM' OU NULL pra cadastrais
```

Aceita `NULL` (cadastrais) e formato `'YYYY-MM'` (periódicos). Eventos com `perApur=2025` (anual sem mês) caem como `NULL` ou são tratados separadamente.

### 5.2 Como extrai

```python
# linha 214-216
def _extract_per_apur(root_evento):
    return _xpath_text(root_evento, "perApur")

# linha 422
per_apur = _extract_per_apur(inner_esocial)
```

> **Lê do XML, NÃO do nome do arquivo.** Por isso o nome do zip não importa pro banco — só pra organização humana.

### 5.3 Detecção do "período da importação"

```python
# linha 700-701
# Pega o perApur dominante pra rotular a importação
```

Se você importar `SOLUCOES_2025-12.zip`, o sistema vai:

- Salvar 185.897 linhas com `per_apur='2025-12'`
- Salvar 889 linhas com `per_apur='2026-01'`
- Salvar 75 linhas pulverizadas em outras competências
- Salvar 5.575 linhas com `per_apur=NULL` (cadastrais)
- Rotular a IMPORTAÇÃO em si como "competência 2025-12" (dominante)

---

## 6. REGRAS PRÁTICAS — DECISÕES QUE TOMAMOS

### 6.1 Padrão de nome de zip (FIRME)

```
NOMEEMPRESA_YYYY-MM.zip
```

- `YYYY-MM` = perApur **dominante** (>= 95% dos eventos periódicos)
- Se misturar muito, usar perApur do `S-1210` (folha de pagamento) como referência

### 6.2 Filtros de relatório no V2

| Pergunta do usuário                     | Filtro correto                                                           |
| --------------------------------------- | ------------------------------------------------------------------------ |
| "Folha de dezembro/2025"                | `per_apur='2025-12'`                                                     |
| "Tudo que veio NO download de dezembro" | `importacao_id=X` (ignora per_apur)                                      |
| "Tudo do trabalhador X"                 | `cpf_trab='...'` (ignora per_apur)                                       |
| "Resumo anual 2025"                     | `per_apur LIKE '2025-%'` OU `per_apur='2025'`                            |
| "Cadastrais (admissões/demissões)"      | `per_apur IS NULL AND tipo_evento LIKE 'S-22%'`                          |
| "13º salário 2025"                      | `tipo_evento IN ('S-5001','S-5003') AND per_apur='2026-01'` (heurística) |

### 6.3 O que NUNCA fazer

- ❌ Renomear baseado no campo "data de envio do XML" — usar **perApur** ou nome dado pelo eSocial
- ❌ Confiar no nome do zip pra saber competência — sempre conferir `<perApur>`
- ❌ Filtrar relatório de fechamento da empresa por `per_apur=2025-12` sem incluir `2026-01` (perde S-5501)
- ❌ Importar 2 zips com `per_apur` sobrepostos sem checar duplicidade (eSocial não duplica `nrRecibo`)

---

## 7. FLUXO TEMPORAL DE UMA COMPETÊNCIA

> Linha do tempo de UMA folha de pagamento (ex: dezembro/2025):

```
DEZEMBRO/2025 (mês de competência, perApur=2025-12)
├─ Empresa processa folha internamente
├─ Empresa envia eventos cadastrais conforme acontecem (S-2200, S-2299...)
│  └─ Esses NÃO têm perApur

JANEIRO/2026 (mês de transmissão)
├─ Até dia 15: empresa envia S-1200 (remuneração) e S-1210 (pagamento)
│  └─ <perApur>2025-12</perApur>
├─ Empresa envia S-1299 (fechamento da competência)
│  └─ <perApur>2025-12</perApur>
├─ eSocial processa e devolve totalizadores:
│  ├─ S-5001 (INSS por trabalhador)        → perApur=2025-12
│  ├─ S-5002 (IRRF por trabalhador)        → perApur=2025-12
│  ├─ S-5003 (FGTS por trabalhador)        → perApur=2025-12
│  ├─ S-5011 (CP consolidado empresa)      → perApur=2025-12
│  ├─ S-5012 (IRRF consolidado empresa)    → perApur=2025-12
│  ├─ S-5013 (FGTS consolidado empresa)    → perApur=2025-12
│  ├─ S-5501 (totalizador CP empresa)      → perApur=2026-01 (datado pelo eSocial!)
│  └─ S-5503 (totalizador FGTS empresa)    → perApur=2026-01
└─ Se houver 2ª parcela de 13º:
   ├─ S-1200 + S-1210 com perApur=2026-01 (ou rubrica de 13º com perApur=2025)

QUALQUER MÊS POSTERIOR (recálculo / retificação):
└─ Empresa retransmite S-1200 corrigido
   ├─ <perApur>2025-12</perApur> (mantém competência original)
   └─ eSocial gera novo S-5001/02/03/5503 com mesma perApur
```

---

## 8. CHECKLIST AO RECEBER NOVO ZIP

1. ✅ Rodar `_perapur_zip_dez.py` (genérico para qualquer zip) — descobrir perApur dominante
2. ✅ Renomear pro padrão `NOMEEMPRESA_YYYY-MM.zip`
3. ✅ Mover pra pasta `todos os meses 2025 NOMEEMPRESA/`
4. ✅ Conferir se já existe outro zip da mesma competência (evitar dupe)
5. ⏳ Importar via endpoint do bot_api (ainda não documentado nessa missão)

---

## 9. ESTADO ATUAL DOS ZIPs (06/05/2026)

### APPA — `C:\Users\xandao\Downloads\xmls do e social mes a mes\` (13 zips, completo 2025)

- ✅ Banco APPA Supabase já carregado: ~219.113 envios
- 🚫 NUNCA tocar (já em produção)

### SOLUCOES — `C:\Users\xandao\Downloads\todos os meses 2025 SOLUCOES\` (3 zips)

- ✅ `SOLUCOES_2025-06.zip` (340 MB, 83.548 XMLs)
- ✅ `SOLUCOES_2025-08.zip` (810 MB, 198.153 XMLs)
- ✅ `SOLUCOES_2025-12.zip` (802 MB, 192.512 XMLs) ← novo
- ⏳ Faltam: 01, 02, 03, 04, 05, 07, 09, 10, 11/2025
- 🆗 Banco local `easy_social_solucoes`: ZERADO (após truncate de hoje), pronto pra reimportar

---

## 10. ARQUIVO DE GLOSSÁRIO RÁPIDO

| Termo                | Significado                                                        |
| -------------------- | ------------------------------------------------------------------ |
| `perApur`            | Período de Apuração — competência da folha (`YYYY-MM`)             |
| `dtPgto`             | Data de pagamento (dentro do S-1210)                               |
| Mês de transmissão   | Quando a empresa enviou pro eSocial (≠ competência)                |
| Mês de competência   | Mês a que a folha se refere (perApur)                              |
| Evento periódico     | Tem perApur (S-1200, S-1210, S-1298, S-1299, S-5xxx)               |
| Evento não-periódico | Sem perApur (S-22xx, S-1010, S-1020, S-2500/01, S-3500, S-2210)    |
| Totalizador          | Calculado pelo eSocial e devolvido (S-50xx, S-55xx)                |
| Recibo               | Identificador único do evento (`nrRecibo`)                         |
| Reciprocidade        | Eventos amarrados — S-1210 referencia S-1200 que referencia S-2200 |

---

## 11. SCRIPTS QUE GERARAM ESSA ANÁLISE

Todos em `python-scripts/`:

- `_inspect_zips_solucoes.py` — lista nomes e tipos por nome de arquivo
- `_check_perapur_zips.py` — lê `<perApur>` dos S-1210
- `_compara_appa_solucoes.py` — compara 3 zips lado a lado
- `_compara_grupos.py` — APPA (13 zips) vs SOLUCOES (2 zips)
- `_perapur_zip_dez.py` — perApur por TIPO de evento (amostra)
- `_relatorio_perapur_dez.py` — perApur completo, lê 100% dos XMLs ← gerou a seção 3

---

> **TL;DR:** Um zip "do mês X" baixado do eSocial sempre vai ter ~1% de eventos pulverizados em outras competências. **Isso é normal e esperado.** O sistema importa cada evento no `per_apur` correto baseado no XML, não no nome do zip. O nome do zip só serve pra organização humana.
