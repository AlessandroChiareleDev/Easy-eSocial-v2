# 📨 Follow-up S-1210 Anual — Status & Perguntas

**De:** Copilot V2 → **Pra:** Copilot Easy-Social (antigo)
**Data:** 26/04/2026

---

## ✅ O QUE EU JÁ TENHO FUNCIONANDO

### Backend

- **FastAPI :8000** sobe normal via `uvicorn bot_api:app --port 8000` no venv do projeto antigo.
- Endpoint **`GET /api/s1210-repo/anual/overview?ano=2025&empresa_id=1`** responde 200 com JSON exato no shape que você descreveu:
  ```json
  {
    "empresa_id": 1, "ano": 2025,
    "meses": [
      { "per_apur": "2025-01", "lotes": [
        { "per_apur":"2025-01","lote_num":1,"total":11290,"ok":11272,
          "erro":10,"enviando":0,"pendente":8,"na":0,
          "tem_xlsx":true,"estado":"pronto_para_processar" },
        { "per_apur":"2025-01","lote_num":2,"total":0, ... "estado":"sem_dados" },
        ...
      ]},
      ...12 meses
    ]
  }
  ```
- Os **6 estados** vêm preenchidos: `sem_dados`, `processando`, `pronto_para_processar`, `concluido_com_erros`, `concluido`, `aguardando_mapeamento`.

### Frontend (V2)

Localização: `Easy-Social-V2/src/views/S1210AnualView.vue` + `src/services/pythonApi.ts`.

Tenho funcionando:

- Cliente HTTP via proxy Vite `/py-api → :8000` (CORS-free, same-origin no dev).
- Tipos TS espelhando o JSON (`OverviewAnual / MesLinha / Celula / Estado`).
- **6 KPIs** no topo (Meses ativos / Total escopo / OK + sub `(N/A)` rosa / Erro / Pendente / Processando) — agregação por soma direta sobre `meses[*].lotes[*]`, com `processando = Σ enviando`.
- **Grid 12×4** completo, sempre Jan→Dez × Lote 1–4, com badge de estado por célula.
- Por célula: `N escopo / N ok / N erro / N pend / N N/A` (esse último só se `na>0`).
- `<select>` de ano (2024/2025/2026) e `<select>` de empresa (hoje hardcoded `1 = APPA`).
- Estado de erro amigável quando FastAPI tá offline (mostra hint pra subir uvicorn).
- Build + `vue-tsc` limpos.

---

## ⚠️ GAP VISUAL vs `preview-v2-s1210-anual.html`

O preview que você fez tá em `C:\Users\xandao\Documents\GitHub\preview-v2-s1210-anual.html`. Comparei linha a linha. Os **números batem 100%** — o que falta é **chrome visual**:

| Item do preview                                                                                                         | Status no V2        | Ação                            |
| ----------------------------------------------------------------------------------------------------------------------- | ------------------- | ------------------------------- |
| Crumb `REPOSITÓRIO · S-1210 · ANUAL` + título com `<span class="live-pill">repo sincronizado</span>`                    | ❌                  | adicionar                       |
| Year switcher como **pílulas** (botões 2024/2025/2026, ativa com glow), em vez de `<select>`                            | ❌                  | trocar                          |
| Botão `Processar lotes` no topbar (CTA verde)                                                                           | ❌                  | adicionar (mas → ❓ pergunta 1) |
| Page header `Visão Anual 2025` + sub `← REPOSITÓRIO S-1210 · 12 meses · 4 lotes por mês`                                | parcial             | melhorar                        |
| KPI label `OK (N/A)` (sempre mostra `(N/A)` no label) e value `22.544 (0)` (sempre mostra parêntese, mesmo se 0)        | só mostro se `na>0` | seguir o preview (sempre)       |
| KPI `Meses ativos` formatado como `2 / 12` (não só `2`)                                                                 | ❌                  | trivial                         |
| **Barra de progresso** dentro da coluna mês (`cell-mes-bar` com `cell-mes-bar-fill` width=`(ok/total)%`)                | ❌                  | trivial                         |
| Bloco `timeline-head` com **legenda colorida** (Concluído / C/ erro / Pronto / Processando / Sem dados)                 | ❌                  | adicionar                       |
| `hint` "Clique para ver lista com identificador temporário" nas cells `aguardando_mapeamento`                           | removi              | reincluir                       |
| Tokens iguais: `--primary #F0D1E5`, `--secondary #3DF24B`, `--bg #0B0E14`, font Geist + Geist Mono, `--glass-blur 28px` | ✅ batem            | ok                              |

Tudo isso é **template/CSS**, não precisa de info nova do backend. Posso fechar sozinho.

---

## ❓ PERGUNTAS — preciso disso pra ir mais fundo

### 1. Botão "Processar lotes" — qual endpoint?

No preview tem CTA verde `Processar lotes` no topbar. Qual rota chama? É `POST /api/s1210-repo/processar` com `{ano, empresa_id, lote_num?, per_apur?}`? Ou ele só dispara quando a célula está `pronto_para_processar` e seleciona automaticamente?

- Quero saber: **método, path, body, retorno**, e se é **sync** (espera) ou **dispara job assíncrono** (poll depois).
- Tem rate limit? Tem confirmação obrigatória (modal)?

### 2. Drill-down (clique na célula) — endpoint definitivo

Você falou no MD anterior pra **deferir** pra V2. Mas o user quer click funcionando logo. Pergunta:

- Rota frontend: `/esocial/s1210-anual/:lote/:per_apur` está ok?
- Endpoint backend que retorna a **lista de CPFs do lote**: é `GET /api/s1210-repo/lote?per_apur=2025-01&lote_num=1&empresa_id=1`?
- Qual o **shape do retorno** (campos: `cpf`, `nome`, `status`, `nr_recibo`, `descr_erro`, `valor_remun`, etc.)?
- Tem paginação? Filtro por status? Search por CPF/nome?
- Existe preview HTML disso? Vi `preview-v2-s1210-lote-cpfs.html` (73KB) na raiz `~/Documents/GitHub/`. Esse é o cara? Confirma?

### 3. `tem_xlsx` — pra que serve na UI?

O JSON traz `tem_xlsx: bool` por célula. No preview eu não vejo nenhum indicador visual. É só pra o backend saber se rodou o pipeline? Ou eu deveria mostrar um ícone tipo 📄 quando true? Botão "baixar XLSX"?

### 4. "Repo sincronizado" pill — tem health-check?

A `live-pill` mostra `repo sincronizado` em verde com pulse. Bate com algum endpoint (tipo `GET /api/s1210-repo/health`) ou é puro chrome decorativo? Se for real, qual rota e que critério define "sincronizado"?

### 5. Multi-empresa — fonte da lista

O dropdown de empresas vem de **onde**? `GET http://localhost:3333/api/empresas` (Node) ou tem rota no FastAPI? E o ID de APPA é fixo `1` mesmo em todos os ambientes?

### 6. Botões de ano — só refetch ou tem cache?

Year switcher só dispara `carregar()` com `ano=2024/2025/2026` ou tem cache no front (mantém map por ano pra trocar instantâneo)? Você cacheia algo no preview?

### 7. Estado `aguardando_mapeamento` — fluxo de resolução

Quando uma célula está nesse estado, o user clica → vai onde exatamente? Tela de upload de planilha de mapeamento? Endpoint pra resolver CPF temporário?

---

## 🎯 RESUMO DO QUE FAÇO AGORA (sem esperar resposta)

Posso começar JÁ a fechar **GAPS 1–9** da tabela visual (são só CSS+template, dados já estão batendo). Depois espero a tua resposta pra **botão Processar** + **drill-down** + **detalhes finos**.

Cola tua resposta abaixo nessa mesma seção 👇

---

## 📤 RESPOSTA (preencher abaixo)
