# 👋 Olá, Copilot da janela Easy-Social-V2

Aqui é o **Copilot da janela antiga (Easy-Social)** falando com você.

O Xandão acabou de me pedir pra te deixar um recado nesse repo pra você ler quando ele abrir o chat aí.

---

## 📍 Onde você está

```
c:\Users\xandao\Documents\GitHub\Easy-Social-V2
```

Repo **NOVO**, **PRIVADO**, criado do zero. Branch `main`, 1 commit inicial.

---

## 🎯 O que esse repo é

Frontend **V2** do Easy-Social — redesign do zero baseado no conceito visual
**Liquid Glass / Ghost Green** que o Xandão desenhou nos previews HTML.

**NÃO é** o frontend antigo (`../Easy-Social/frontend`). Aquele continua
existindo intacto. Esse aqui é redesign limpo, com 6 telas, segurança blindada
desde o dia 1.

### 6 telas planejadas

1. **Painel** (`/`) — home com cérebro fantasma + 5 cards
2. **Tabelas** (`/tabelas`) — S-1000 / S-1005 / S-1010, rubricas, lotações
3. **eSocial S-1010** (`/esocial/s1010`)
4. **S-1210 Anual** (`/esocial/s1210-anual`)
5. **Logs** (`/logs`) — auditoria + respostas eSocial (XML retorno governo)
6. **Problemas** (`/problemas`) — erros L1/L2, pendências, reenvios

---

## ✅ O que JÁ está pronto

- Stack: Vue 3.5 + Vite 6 + TS strict + Tailwind v4 + Pinia + Router
- `npm install` rodado — **0 vulnerabilidades**
- `npm run type-check` — sem erros
- `npm run build` — passa em ~1s
- 6 views existem (Painel completa + 5 placeholders)
- Design tokens em [src/styles/tokens.css](src/styles/tokens.css)
- Helpers globais em [src/styles/main.css](src/styles/main.css):
  - `.liquid-glass` — card de vidro
  - `.gg-glow` — texto com halo Ghost Green
  - `.blush-aura` / `.blush-aura--secondary` — nuvens rosa difusas
- [src/components/base/BrainStage.vue](src/components/base/BrainStage.vue) — cérebro fantasma (img + hue-rotate + mix-blend screen + 3 anéis pulsando)
- Segurança: CSP no [index.html](index.html), [.gitignore](.gitignore) blindado, [SECURITY.md](SECURITY.md), `sourcemap: false`, `localStorage` proibido pra auth
- Git inicializado em `main`, commit inicial feito

---

## ⏳ O que FALTA fazer (ordem sugerida)

### Imediato

1. **Rodar `npm run dev`** (porta 5174) e validar que o cérebro renderiza certo
2. **Criar `src/layouts/AppLayout.vue`** — sidebar Liquid Glass + topbar
   - Hoje cada view é standalone. Falta um layout compartilhado.
3. **Aplicar AppLayout no router** (todas as rotas exceto talvez Painel)

### Curto prazo (Fase 3 do plano)

4. **Implementar Logs primeiro** — é a tela mais simples e a que o Xandão
   mais quer ver funcionando (precisa ler XMLs de resposta do eSocial
   capturados desde nov/2025)
5. **Backend client** em `src/services/api.ts`:
   - `fetch` com `credentials: 'include'` (httpOnly cookies)
   - Header `X-CSRF-Token` em todas as mutações
   - **NUNCA** ler/escrever token em `localStorage` — só httpOnly cookie
6. **Pinia store de auth** em `src/stores/auth.ts`
7. **Implementar Problemas** — segunda mais simples
8. **Implementar Tabelas, S-1010, S-1210** — mais complexas, deixar pro fim

### Polish

9. Skeletons / empty states
10. Page transitions (Vue Transition + view-transition-name)
11. Microinterações (hover, focus, active)

---

## 🎨 Princípios de design (NÃO esquecer)

| Token       | Cor       | Como usar                                          |
| ----------- | --------- | -------------------------------------------------- |
| Deep Ink    | `#0B0E14` | Background. O vazio que faz o vidro existir        |
| Ghost Green | `#3DF24B` | **LUZ**, nunca tinta sólida                        |
| Blush Frost | `#F0D1E5` | Contraste — luz batendo no vidro / borda topo card |

**Regra de ouro do verde:** sempre `text-shadow` ou `drop-shadow` ou
`background: radial-gradient(...)`. **Nunca** `color: #3DF24B` chapado em
texto principal. O verde é luz, não pintura.

**Cérebro:** translúcido, `mix-blend-mode: screen`, `opacity: 0.32`. A luz
verde **vem de trás** (radial gradient atrás), não está no cérebro.

Os 4 previews originais que serviram de moodboard estão em:

```
c:\Users\xandao\Documents\GitHub\preview-v2-brain.html
c:\Users\xandao\Documents\GitHub\preview-v2-painel.html  (se existir)
... e os outros HTMLs de preview
```

---

## 🔒 Segurança — REGRAS DURAS

Lê o [SECURITY.md](SECURITY.md) inteiro antes de qualquer coisa. Resumo:

- ⛔ **Certificado A1 NUNCA** trafega pelo frontend. Backend-only.
- ⛔ **Zero segredos** no código. `.env` jamais commitado.
- ⛔ **Sem `v-html`** com dado dinâmico (anti-XSS).
- ⛔ **Auth NUNCA em localStorage** — só httpOnly cookies.
- ✅ CSP já configurada no `index.html`.
- ✅ `npm audit` antes de cada release.
- ✅ Repo é PRIVADO — não tornar público sob nenhuma circunstância.

---

## 🧠 Memória crítica do Xandão (eSocial)

> **NUNCA** rodar consultas ao webservice do eSocial sem permissão EXPLÍCITA dele.
> Limite de **10 consultas/dia** no Download Cirúrgico. Scripts como `download_dia8.py`
> gastam 6-8 consultas de uma vez. Endpoints proibidos sem aval:
> `WsSolicitarDownloadEventos.svc`, `ConsultarLoteEventos`.

Mas isso é mais relevante pro repo antigo (que tem os scripts Python).
Aqui no V2 frontend você não vai esbarrar nisso, mas fica o aviso.

---

## 📂 Arquivos chave pra você ler primeiro

1. [README.md](README.md) — visão geral
2. [SECURITY.md](SECURITY.md) — regras de segurança
3. [src/styles/tokens.css](src/styles/tokens.css) — design tokens
4. [src/styles/main.css](src/styles/main.css) — helpers globais
5. [src/components/base/BrainStage.vue](src/components/base/BrainStage.vue) — referência de qualidade visual
6. [src/views/PainelView.vue](src/views/PainelView.vue) — referência de como uma tela deve parecer
7. [src/router/index.ts](src/router/index.ts) — todas as 6 rotas

---

## 💬 Recado pessoal

O Xandão é objetivo, escreve rápido em PT-BR informal, às vezes com erros de
digitação (não corrija ele, só entenda). Ele odeia:

- Respostas longas e prolixas
- Excesso de "vou fazer X, depois Y, depois Z" — prefere você FAZER
- Refatoração não pedida
- Comentários e docstrings que ele não pediu

Ele gosta:

- Trabalho autônomo (ele delega: "faz tudo do zero", "trabalha sozinho")
- Resultado visível rápido
- Honestidade quando algo falha

**Boa sorte.** O scaffold tá sólido, build limpa, segurança ok.
A partir daqui é construir as 6 telas com capricho.

— Copilot da janela antiga
26/abr/2026
