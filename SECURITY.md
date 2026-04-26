# SECURITY — Easy-Social V2

Repositório **privado**. Lista do que aplicamos desde o dia 1 pra não repetir
os erros do V1.

## Frontend

- ✅ **Sem segredos no código.** Zero tokens, chaves ou certificados em `.vue`/`.ts`.
- ✅ **`.env` NUNCA commitado.** Apenas `.env.example` (sem valores).
- ✅ **CSP** restritiva no [index.html](./index.html) (`default-src 'self'`,
  `frame-ancestors 'none'`, `object-src 'none'`).
- ✅ **X-Content-Type-Options: nosniff** + **Referrer-Policy: strict-origin-when-cross-origin**.
- ✅ **Permissions-Policy** desabilita camera/microphone/geolocation por padrão.
- ✅ **Sem `v-html` com dado dinâmico** (anti-XSS). Se for inevitável, sanitizar com DOMPurify.
- ✅ **Sanitização client-side** de CPF, CNPJ, datas antes de enviar pro backend.
- ✅ **Auth tokens em httpOnly cookies** (backend seta). Frontend nunca vê o token.
  - Quando precisar de fallback em memória, **NUNCA usar `localStorage`** (vulnerável a XSS).
- ✅ **CSRF**: header `X-CSRF-Token` em toda mutação (configurado em `src/services/`).
- ✅ **HTTPS-only** em produção (configurado no Nginx/CDN, não no app).
- ✅ **Auditoria de dependências**: `npm run audit` antes de cada release.
- ✅ **Source maps desligados** em build de produção (`vite.config.ts` → `sourcemap: false`).
- ✅ **TypeScript strict + `noUncheckedIndexedAccess`** — pega bugs de
  `obj.foo!` esquecido em runtime.

## Certificado A1 (eSocial)

| Regra                                                | Por quê                                                                |
| ---------------------------------------------------- | ---------------------------------------------------------------------- |
| ⛔ **NUNCA** trafega pelo frontend                   | Se vazar via XSS/CSP fraca, atacante pode emitir eventos como a empresa |
| ⛔ **NUNCA** commitado no git                        | Repos privados ainda podem ser clonados/forkados/leakados              |
| 🔒 Path do A1 sempre em variável de ambiente backend | Não hardcode                                                           |
| 🔒 Permissões `0400` no servidor                     | Apenas o usuário do app lê                                              |
| 🔒 Senha do A1 em secret manager (não em `.env`)     | Vault, AWS Secrets Manager, ou similar                                 |
| 🔒 **Nunca logar** conteúdo do A1                    | Logs vazam mais que código                                             |

## Repo (GitHub)

- 🔒 **Privado** (não tornar público sob nenhuma circunstância)
- 🔒 **Branch protection** em `main` — exige PR + review
- 🔒 **Secret scanning** ativo (alerta se segredo for empurrado)
- 🔒 **Dependabot** ativo (alertas de vulnerabilidade nas deps)
- 🔒 **Nunca dar push --force** em `main`

## Checklist antes de cada commit

```powershell
# 1. Não há .env nem certificados nos arquivos staged
git diff --cached --name-only | Select-String -Pattern '\.env$|\.pfx$|\.p12$|\.A1$|\.pem$|\.key$'

# 2. npm audit não acusa vulnerabilidade alta/crítica
npm audit --audit-level=high

# 3. Build passa
npm run build
```

## Reportar problema de segurança

Email: `seguranca@easysocial.local` (interno).
**Não** abrir Issue público.
