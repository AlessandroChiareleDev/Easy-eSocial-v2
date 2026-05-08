# 00 — Contexto e Fontes do Explorador de Arquivos

> **Para qualquer IA, dev ou Alex chegando no projeto agora:**
> leia este MD primeiro, depois o `01_PLANO_EXPLORADOR_ARQUIVOS.md` deste mesmo diretório.
> Em 5 minutos você sabe **onde estamos**, **o que existe** e **o que ler antes de codar**.

---

## 1. ESCOPO ABSOLUTO DESTE TRABALHO

### O que vamos construir

Um **Explorador de Arquivos do eSocial** dentro do repositório **Easy-eSocial-v2**.

### Onde mexer

- ✅ **`C:\Users\xandao\Documents\GitHub\Easy-eSocial-v2`** — código novo (backend + frontend)
- ✅ Banco Postgres LOCAL `easy_social_solucoes` — já existe, vazio, schema clonado, **NÃO apagar**

### Onde NÃO mexer

- 🚫 **APPA** — empresa existe no sistema (banco Supabase em produção), aparece em todo lugar do conjunto, mas **não tocar em NADA dela** até liberação explícita do Alex. A "adequação" para os 2 tipos de empresa fica para um momento posterior.
- 🚫 **Easy-Social** (V1) — backend `bot_api`, scripts de envio S-1210/S-1298, banco APPA Supabase. Não encostar.
- 🚫 Os 13 zips da APPA em `Downloads\xmls do e social mes a mes\` — ignorar completamente.

### Regra de ouro

**Tudo o que for criado a partir de agora é exclusivo da empresa SOLUCOES, dentro do V2.** Os 2 estados/tipos de empresa serão suportados desde o início no modelo de dados, mas só SOLUCOES recebe carga de dados nesta fase.

---

## 2. OS 2 ESTADOS DE EMPRESA

O sistema precisa suportar **2 tipos/estados** distintos de empresa desde o desenho inicial:

| Estado     | Quem é hoje  |
| ---------- | ------------ |
| `estado_1` | **SOLUCOES** |
| `estado_2` | (a definir)  |

> O significado concreto de cada estado **não interessa agora**. O que importa é que o modelo já nasça preparado para os dois — uma coluna `tipo_estado ENUM('estado_1','estado_2')` na tabela de empresas. SOLUCOES é cadastrada como `estado_1` desde já.

> APPA **não** é o estado_2. APPA fica fora deste trabalho. A definição de qual empresa será o estado_2 vem depois.

---

## 3. FONTES DE INFORMAÇÃO OBRIGATÓRIAS

### 3.1 README do V2 — onde o conceito nasceu

[`Easy-eSocial-v2/README.md`](../../README.md) — seção **"Roadmap — Explorador de Arquivos"** (linhas 28-49). Define a visão original:

- Visão por CPF
- Chain walk de eventos
- XMLs baixáveis em cada nó
- XMLs **mega compactados** em storage (não inflar o banco)
- UX grafo/timeline, não tabela
- 3 decisões pendentes: formato de compactação, storage local vs S3, chave de amarração

### 3.2 MDs Norte-SOLUCOES — conhecimento técnico

Pasta `Easy-eSocial-v2/md norte solucoes/`:

- 📗 [`explicacao envio s1210 por cpf.md`](../../md%20norte%20solucoes/explicacao%20envio%20s1210%20por%20cpf.md)
  - **ENVIO**: como o sistema MANDA S-1210 pro eSocial.
  - 1 CPF pode ter de 1 a 6 S-1210 num mês (cada natureza vira 1 XML).
  - Tabelas APPA relacionadas (referência cruzada apenas — não é para mexer nelas no SOLUCOES sem replicar o schema novo).
  - Diferença `s1210_cpf_envios` (nosso) vs zip baixado (eSocial).

- 📗 [`explicacao todos eventos que vem mes a mes do esocial.md`](../../md%20norte%20solucoes/explicacao%20todos%20eventos%20que%20vem%20mes%20a%20mes%20do%20esocial.md)
  - **DOWNLOAD**: o que vem nos zips do eSocial.
  - **Nome do zip ≠ competência**. Sempre ler `<perApur>` do XML.
  - 1 zip "do mês X" sempre traz ~1% pulverizado em outras competências (13º, recálculos, processos trabalhistas).
  - Eventos cadastrais (S-22xx, S-1010, S-2500, S-3500, S-2210) **não têm `perApur`** → `NULL`.
  - Tabela detalhada de tipos de evento, exemplo dezembro/2025 SOLUCOES (192.512 XMLs).

### 3.3 chat.json — histórico das conversas

- Caminho: `C:\Users\xandao\Downloads\chat.json` (~481 MB)
- ~1.844 menções a "Easy-eSocial-v2"
- ~33 menções a "md norte solucoes"
- ~30 menções a "explicacao envio s1210"
- Origem narrativa do conceito do Explorador: durante envios em massa S-1210 e estudo dos zips do eSocial, o Alex pediu uma ferramenta para **ver e entender** todos os eventos de uma empresa, navegando por CPF/timeline com XMLs baixáveis.

### 3.4 Zips disponíveis para povoamento inicial

Pasta `C:\Users\xandao\Downloads\todos os meses 2025 SOLUCOES\`:

| Arquivo                | Tamanho |    XMLs | perApur dominante |
| ---------------------- | ------: | ------: | ----------------- |
| `SOLUCOES_2025-06.zip` |  340 MB |  83.548 | 2025-06           |
| `SOLUCOES_2025-08.zip` |  810 MB | 198.153 | 2025-08           |
| `SOLUCOES_2025-12.zip` |  802 MB | 192.512 | 2025-12           |

> Faltam: 01, 02, 03, 04, 05, 07, 09, 10, 11/2025. Não tem prazo nem urgência — quando vierem, sobem pelo upload normal.

> Esses 3 zips **só serão importados uma vez** (povoamento inicial). O sistema de upload runtime tem que continuar funcionando para qualquer zip novo no futuro.

---

## 4. ESTADO ATUAL DO REPOSITÓRIO V2

### Estrutura

```
Easy-eSocial-v2/
├─ docs/                         ← este MD vive aqui (em EXPLORADOR/)
├─ md norte solucoes/             ← 2 MDs de conhecimento técnico
├─ public/, src/                 ← frontend Vue 3 + Vite + TS strict + Tailwind v4
├─ scripts/                      ← 2 scripts Python avulsos (db_explore, db_schema_s1210)
├─ README.md                     ← roadmap + tokens visuais
└─ SECURITY.md
```

### Backend

- **Hoje não tem backend próprio** dentro do V2.
- O `bot_api` que roda em `Easy-Social/python-scripts/bot_api.py` é do V1.
- Para o Explorador, o backend Python será **criado dentro do V2** (provavelmente em `Easy-eSocial-v2/backend/`), isolado do V1. Definição final no MD 01.

### Banco

- DB local `easy_social_solucoes` (Postgres 16, `localhost:5432`, user `easy_social_user`).
- 48 tabelas existentes, todas com 0 linhas (exceto `master_empresas` com 1 linha).
- **Já existem**: `explorador_eventos`, `explorador_importacoes`, `explorador_rubricas`. Schema base existente serve de ponto de partida — pode ser estendido com novas tabelas (zips intactos, controle de upload).

### Git

- Branch atual: `main`
- Working tree: limpo, sem commits pendentes
- Último commit: `089f347 docs: pedido V1 multi-empresa, README atualizado e MDs norte solucoes`

---

## 5. GLOSSÁRIO RÁPIDO

| Termo                      | Significado                                                                     |
| -------------------------- | ------------------------------------------------------------------------------- |
| **perApur**                | Período de Apuração — competência da folha (`YYYY-MM`)                          |
| **Período do download**    | Data inicial → data final pedida pelo usuário no portal eSocial                 |
| **Zip do eSocial**         | Arquivo `.zip` que o portal devolve no download manual; pode ter 1 a 200k+ XMLs |
| **Evento periódico**       | Tem `perApur` (S-1200, S-1210, S-1298, S-1299, S-5xxx)                          |
| **Evento cadastral**       | Sem `perApur` (S-22xx, S-1010, S-2500/01, S-3500, S-2210)                       |
| **Chain walk**             | Navegar eventos amarrados: S-2200 → S-1200 → S-1210 → S-5001/02/03 → S-2299     |
| **Estado da empresa**      | Tipo da empresa (`estado_1`/`estado_2`) — muda como os eventos chegam           |
| **Sequencial do download** | Número que o eSocial inclui no nome de cada zip emitido em uma solicitação      |

---

## 6. PRINCÍPIOS NÃO-NEGOCIÁVEIS

1. **Nunca misturar APPA e SOLUCOES** em código, banco, query ou UI.
2. **Zip fica intacto, comprimido, dentro do banco** — não explodir XMLs em arquivos no disco.
3. **Período do download é a chave** — não o `perApur`. O `perApur` é processado depois.
4. **Upload deve ser eficiente, rápido, com feedback visual no front** (% de progresso, taxa, velocímetro).
5. **2 estados desde o início** no modelo, mesmo que só um seja usado agora.
6. **Não tocar em nada de APPA** sem autorização explícita.

---

## 7. PRÓXIMO PASSO

Ler o MD 01 deste mesmo diretório:
**[`01_PLANO_EXPLORADOR_ARQUIVOS.md`](./01_PLANO_EXPLORADOR_ARQUIVOS.md)** — plano técnico, decisões de arquitetura, modelo de dados, fases de execução.
