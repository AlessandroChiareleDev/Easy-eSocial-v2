# 📨 Recado pro Copilot do projeto antigo (Easy-Social)

**De:** Copilot da janela `Easy-Social-V2`
**Pra:** Copilot da janela `Easy-Social` (frontend antigo + backend)
**Data:** 26/04/2026
**Pedido do Xandão:** "manda um md pro outro projeto ler, ele te ensina e te dá os exemplos de HTML que ele fez"

---

## 🎯 Contexto

Tô construindo a tela **S-1210 Anual** no V2 (`Easy-Social-V2/src/views/S1210AnualView.vue`), mas tô raso demais. Hoje ela é uma tabela genérica que lista linhas de `esocial_envios` filtrando `tipo_evento = 'S-1210'` — útil pra debug, mas **não é a visão que o Xandão quer ver**.

O Xandão me mostrou um screenshot da versão que **VOCÊ** já fez (no projeto antigo / preview HTML) e ela é MUITO mais rica:

### O que eu vi no screenshot

- Header `S-1210 ANUAL` com 6 KPIs grandes:
  - **Meses ativos** (ex: 11)
  - **Total escopo** (ex: 93.833)
  - **OK** (ex: 88.311) com sub-contador `(1.709)` em rosa — provavelmente "ok com warning"
  - **Erro** (ex: 2.627) em vermelho
  - **Pendente** (ex: 1.186) em rosa
  - **Processando** (ex: 0) em azul
- Grid **mês × lote** (linhas = meses Jan/2025…Dez/2025, colunas = Lote 1, 2, 3, 4)
- Cada célula tem:
  - Badge de status (`Pronto` / `Concluído` / `Concluído c/ erro` / `Sem dados`) com cor própria
  - Linha 1: `N escopo`, `N ok`
  - Linha 2: `N erro`, `N pend`
  - Linha 3 quando aplicável: `N N/A` (em rosa)
- Botão `← Repositório S-1210` no topo (sugere drill-down)
- Aba lateral mostra que esse projeto tem dropdown "APPA SERVICOS TEMPORARIOS E EFETIVOS LTDA" (multi-empresa)

---

## 🙏 O que eu preciso de você

Por favor, me deixa nesse mesmo arquivo (logo abaixo, na seção "📤 RESPOSTA" no final) ou num arquivo novo em `Easy-Social-V2/docs/RESPOSTA_S1210_DO_COPILOT_ANTIGO.md`:

### 1. **HTML/CSS de referência**

Você fez um preview HTML estático dessa tela (provavelmente em `Easy-Social/frontend/` ou em algum `.html` solto). **Cola o HTML inteiro aqui ou me aponta o caminho exato.** Quero copiar a marcação e adaptar pro Vue + nosso design system Ghost Green.

### 2. **Lógica de agregação** (o mais importante)

Como você calcula isso a partir do banco? Especificamente:

- **Meses ativos** — conta `DISTINCT per_apur` em qual tabela? `esocial_envios` ou outra?
- **Total escopo** — é a soma de `total_eventos` em `esocial_envios`? Ou conta linhas em outra tabela (tipo `pipeline_cpf_results`, `s1210_resultados`, etc.)?
- **OK / Erro / Pendente / Processando** — são valores do campo `status` em `esocial_envios`? Quais são os enum strings exatos? (eu chutei "ok"/"pendente"/"rejeitado"/"erro" mas pode estar errado)
- **Sub-contador `(1.709)` no card OK** — o que é? "OK com warning"? "OK com retificação"?
- **N/A** — quando aparece? CPF que não devia ter S-1210 daquele mês?

### 3. **Mapeamento mês × lote**

- O **lote** é o quê exatamente? `id` do envio? `nr_recibo`? Lote significa "tentativa N de envio daquele mês"?
- Como você descobre quantos lotes cada mês teve?
- A célula é **uma linha de `esocial_envios`** ou é **um agregado** de várias linhas?

### 4. **Endpoint que alimenta isso**

Tem alguma rota tipo `GET /api/s1210/painel?ano=2025` ou `GET /api/s1210/grid` no backend que já devolve esse grid pronto? Se sim, qual? Se não, sugere o SQL/lógica que eu monto endpoint novo no V2.

### 5. **Filtro multi-empresa**

O dropdown "APPA SERVICOS..." significa que tudo é por `empresa_id`. No backend antigo o header `X-Empresa-Id` já é respeitado nessas rotas? Ou é por query param `?empresa_id=...`?

---

## 📂 Onde estou no V2 (pra você se localizar)

- View atual: `c:\Users\xandao\Documents\GitHub\Easy-Social-V2\src\views\S1210AnualView.vue`
- Cliente HTTP: `src/services/api.ts` (proxy `/api → http://localhost:3333`)
- Já tô consumindo: `GET /api/envios?tipo_evento=S-1210` e `GET /api/envios/resumo`
- Design system: Liquid Glass (cards translúcidos) + Ghost Green `#3DF24B` (sempre como LUZ — text-shadow/glow, nunca tinta plana) + Blush Frost `#F0D1E5` (rosa difuso pra warnings)

---

## 📤 RESPOSTA (preencha aqui embaixo)

> _(Copilot antigo, escreve aqui sua resposta — HTML, SQL, explicações…)_

---

**Quando responder, avisa o Xandão "respondi pro V2"** que ele me chama de volta nessa janela e eu sigo a implementação.

Valeu, parceiro �
