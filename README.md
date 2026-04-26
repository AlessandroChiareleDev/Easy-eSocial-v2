# Easy-Social V2

> **Repositório PRIVADO** — frontend redesign do Easy-Social.
> Conceito visual: **Liquid Glass / Ghost Green** (Deep Ink + Blush Frost + Ghost Green).

## Stack

- **Vue 3** + **TypeScript** (strict mode)
- **Vite 6**
- **Vue Router 4**
- **Pinia**
- **Tailwind v4** (via `@tailwindcss/vite`)

## Por que V2

O V1 (`../Easy-Social/frontend`) acumulou erros de segurança e UX. Este repo é
um redesign do zero focado em:

1. **Segurança desde o dia 1** (ver [SECURITY.md](./SECURITY.md))
2. **UI Liquid Glass** — cérebro fantasma, glow Ghost Green como luz, contraste Blush Frost
3. **Captura de dados de resposta do eSocial** (XMLs de retorno do governo)
4. **6 telas** ao invés de N — escopo enxuto:
   - Painel (home, cérebro operacional)
   - Tabelas (S-1000/S-1005/S-1010, rubricas)
   - eSocial S-1010
   - S-1210 Anual
   - Logs de Sistema
   - Problemas

## Setup

```powershell
# 1. Instalar deps
npm install

# 2. Configurar env
Copy-Item .env.example .env
# editar .env com URL do backend

# 3. Rodar
npm run dev
# http://localhost:5174

# 4. Build
npm run build

# 5. Auditar deps
npm audit
```

## Estrutura

```
Easy-Social-V2/
├─ public/                 # Assets estáticos servidos como /
├─ src/
│  ├─ assets/
│  │  └─ brain/            # PNGs do cérebro neural (do BrainNav v1)
│  ├─ components/
│  │  └─ base/             # Primitivos (BrainStage, GlassCard, etc)
│  ├─ composables/         # Composition API hooks
│  ├─ layouts/             # Layouts compartilhados
│  ├─ router/              # Vue Router
│  ├─ services/            # Cliente HTTP, integrações
│  ├─ stores/              # Pinia stores
│  ├─ styles/              # tokens.css + main.css
│  ├─ types/               # Tipagens compartilhadas
│  ├─ views/               # 1 view por rota (6 no total)
│  ├─ App.vue
│  ├─ main.ts
│  └─ env.d.ts
├─ docs/
├─ .env.example
├─ .gitignore              # BLINDADO — ver lista de segredos bloqueados
├─ index.html              # CSP + headers de segurança via <meta>
├─ package.json
├─ SECURITY.md
├─ tsconfig.json
└─ vite.config.ts
```

## Princípios visuais

| Token       | Cor       | Papel                                                        |
| ----------- | --------- | ------------------------------------------------------------ |
| Deep Ink    | `#0B0E14` | O vazio que faz o vidro existir                              |
| Ghost Green | `#3DF24B` | **LUZ**, nunca tinta sólida (text-shadow / drop-shadow)      |
| Blush Frost | `#F0D1E5` | Contraste elegante (luz batendo no vidro / borda topo card)  |

Helpers globais em `src/styles/main.css`:

- `.liquid-glass` — card de vidro com glow verde + borda Blush Frost
- `.gg-glow` — texto branco com halo Ghost Green
- `.blush-aura` — nuvem rosa difusa atrás de tudo

## Plano por fases

- **Fase 0** — Moodboard de referências (Apple, Linear, Vercel, Raycast, shadcn-vue, etc.)
- **Fase 1** — Design system V2 (tokens, componentes base, motion)
- **Fase 2** — Esqueleto + Painel (esta fase)
- **Fase 3** — As 5 telas restantes (Logs → Problemas → Tabelas → S-1010 → S-1210)
- **Fase 4** — Polish (transitions, skeletons, empty states, microinterações)

Estado atual: **Fase 2 inicial** — scaffold + Painel rodando com cérebro fantasma.
