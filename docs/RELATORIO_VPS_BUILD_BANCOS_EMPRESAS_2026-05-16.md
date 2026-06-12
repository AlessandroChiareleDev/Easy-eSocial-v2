# Relatório — VPS, build, bancos e empresas do Easy-eSocial V2

Data: 16/05/2026  
Workspace analisado: `Easy-eSocial-v2`  
Branch local: `main`  
Remoto Git: `https://github.com/AlessandroChiareleDev/Easy-eSocial-v2.git`

## 0. Escopo e cuidado operacional

Este relatório foi feito por leitura do repositório local, documentação, scripts de deploy e código do backend/frontend. Não executei SSH na VPS, não consultei eSocial, não rodei downloads, não chamei APIs do governo e não mexi em banco de produção.

Fontes principais lidas:

- `deploy/README.md`
- `.github/workflows/deploy.yml`
- `deploy/scripts/deploy.sh`
- `deploy/scripts/provision.sh`
- `deploy/scripts/cutover_v1_to_v2.sh`
- `deploy/scripts/rollback_to_v1.sh`
- `deploy/nginx/easyesocial.com.br.conf`
- `deploy/easy-esocial.service`
- `backend/app/config.py`
- `backend/app/tenant.py`
- `backend/app/sistema_db.py`
- `backend/app/db.py`
- `backend/app/migrate.py`
- `backend/migrations/README.md`
- `backend/migrations/sistema/sistema_v1.0.0.sql`
- `backend/migrations/empresa/empresa_v1.0.0.sql`
- `backend/migrations/empresa/empresa_v1.1.0.sql`
- `docs/ARQUITETURA_MULTI_TENANT.md`
- `Solucoes Dia 2/BIBLIA_V2_NORTE.md`
- `Solucoes Dia 2/MIGRACAO_V1_V2.md`
- `Solucoes Dia 2/ARQUITETURA_MULTI_EMPRESA.md`
- `src/stores/auth.ts`
- `src/stores/empresa.ts`
- `src/services/api.ts`
- `src/services/pythonApi.ts`

## 1. Resumo executivo

O repositório atual é o **Easy-eSocial V2**. Ele substitui o V1 no mesmo domínio `easyesocial.com.br`, usando a mesma VPS Hostinger, o mesmo certificado SSL e um backend FastAPI em `127.0.0.1:8001` atrás do Nginx.

O build de produção do frontend não é gerado no GitHub Actions runner. O workflow do GitHub apenas entra por SSH na VPS, atualiza o clone em `/opt/easy-esocial/repo` e roda `deploy/scripts/deploy.sh` dentro da própria VPS. Esse script executa `npm ci`, `npm run build` e copia `dist/` para `/opt/easy-esocial/frontend-dist/`, que é a pasta servida pelo Nginx.

Hoje a documentação mais atual aponta para **2 empresas ativas**: APPA e SOLUCOES. Elas estão isoladas por **schema PostgreSQL**, não por banco físico individual. O modelo atual é: uma camada de sistema para autenticação/roteamento e uma camada de dados com schemas de empresa (`appa`, `solucoes`, etc.).

Existe histórico de documentação antiga defendendo “1 banco Supabase por empresa”. Isso foi o plano original em `Solucoes Dia 2/`, mas a documentação mais recente e o código atual apontam para **tenant por schema**. A diferença precisa ficar muito clara para não operar com premissa errada.

Ponto de atenção: há inconsistência entre a doc “2 Supabase” e trechos do código/scripts que usam `SISTEMA_DB_URL` também para schemas de dados. Antes de onboarding, backup ou manutenção real na VPS, a primeira checagem deve ser confirmar qual DSN contém os schemas `sistema`, `appa`, `solucoes` e `legado` no ambiente ativo.

Sobre **Biodiesel**: não encontrei nenhum arquivo, schema, empresa, CNPJ, rota ou configuração com esse nome neste workspace. Portanto, no V2 atual, Biodiesel deve ser tratado como **fora do cadastro ativo**. Se Biodiesel já existe em outro ambiente, ele está separado deste V2 analisado. Se for entrar no V2, deve entrar explicitamente como tenant separado e jamais misturado com APPA/SOLUCOES.

## 2. Onde fica o “bicho” da VPS e como o build funciona

### 2.1. VPS / domínio / paths

Pelos documentos de deploy e apresentação técnica, a infraestrutura esperada é:

| Item                 | Valor / caminho                                                                  |
| -------------------- | -------------------------------------------------------------------------------- |
| Provedor             | VPS Hostinger                                                                    |
| IP documentado       | `76.13.169.45`                                                                   |
| Domínio público      | `easyesocial.com.br`                                                             |
| Raiz da aplicação    | `/opt/easy-esocial/`                                                             |
| Clone do repo na VPS | `/opt/easy-esocial/repo/`                                                        |
| Backend em produção  | `/opt/easy-esocial/backend/`                                                     |
| Venv Python          | `/opt/easy-esocial/backend/.venv/`                                               |
| Frontend buildado    | `/opt/easy-esocial/frontend-dist/`                                               |
| Uploads backend      | `/opt/easy-esocial/backend/uploads/`                                             |
| Certificados A1      | `/opt/easy-esocial/certs/` ou backend `_certificados`, dependendo do fluxo       |
| Logs app             | `/opt/easy-esocial/logs/uvicorn.log` e `/opt/easy-esocial/logs/uvicorn.err.log`  |
| Logs Nginx           | `/var/log/nginx/easyesocial.access.log` e `/var/log/nginx/easyesocial.error.log` |

### 2.2. Serviço systemd

O serviço de produção é `easy-esocial.service`:

```ini
ExecStart=/opt/easy-esocial/backend/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8001 --workers 2 --proxy-headers --forwarded-allow-ips=127.0.0.1
```

Ou seja:

- O backend não fica exposto diretamente na internet.
- O Nginx recebe HTTPS em `443` e repassa `/api/` para `127.0.0.1:8001`.
- O frontend é estático, servido por Nginx a partir de `/opt/easy-esocial/frontend-dist`.

### 2.3. Fluxo de deploy automático

Workflow: `.github/workflows/deploy.yml`

Gatilhos:

- `push` na branch `main`
- `workflow_dispatch`

Fluxo:

1. GitHub Actions abre SSH na VPS usando secrets `VPS_HOST`, `VPS_USER`, `VPS_SSH_KEY`, `VPS_PORT`.
2. Entra em `/opt/easy-esocial/repo`.
3. Faz `git fetch`, `git checkout main`, `git pull --ff-only`.
4. Roda `bash /opt/easy-esocial/repo/deploy/scripts/deploy.sh main`.
5. Faz smoke público em `https://easyesocial.com.br/api/health`.

### 2.4. O que o `deploy.sh` faz

O script `deploy/scripts/deploy.sh` executa:

1. `git fetch`, `checkout`, `pull` no repo da VPS.
2. `rsync` do backend para `/opt/easy-esocial/backend/`, preservando `.env`, `.venv` e uploads.
3. `pip install -r requirements.txt` dentro da venv.
4. Build frontend: `npm ci`, `npm run build`.
5. Copia `dist/` para `/opt/easy-esocial/frontend-dist/`.
6. Reinicia `easy-esocial.service`.
7. Sincroniza config do Nginx se mudou.
8. Roda smoke local e público.

Conclusão prática: **o “build da VPS” está em `/opt/easy-esocial/frontend-dist/`**. O source que gera esse build fica em `/opt/easy-esocial/repo/`. O backend ativo fica em `/opt/easy-esocial/backend/`.

### 2.5. Nginx e compatibilidade com V1

O Nginx atual do V2:

- Redireciona HTTP para HTTPS.
- Usa certificado Let's Encrypt existente em `/etc/letsencrypt/live/easyesocial.com.br/`.
- Serve Vue estático no `/`.
- Repassa `/api/` para FastAPI V2 em `127.0.0.1:8001`.
- Mantém uma ponte de compatibilidade `/py-api/` para `127.0.0.1:8000`, descrita como backend Python legado V1.
- Trata rotas específicas de XML S-1210 em `/py-api/api/s1210-repo/xml-cpf` apontando para o V2.

Isto significa que o V2 assumiu o domínio, mas ainda existe compatibilidade legada. O V1 não deve ser considerado “deletado”; ele é preservado para rollback e alguns caminhos legados ainda aparecem na config.

## 3. Estado do repositório local

Comandos Git lidos:

- Branch atual: `main`
- Remoto: `origin https://github.com/AlessandroChiareleDev/Easy-eSocial-v2.git`
- Últimos commits:
  - `10c2137 Baixa XML S-1210 com fetch autenticado`
  - `2e0841b Compatibiliza rota legada de XML S-1210`
  - `6b64846 Ignora artefatos operacionais locais`
  - `01898d2 Corrige download de XML S-1210`
  - `d0e4a89 Atualiza fluxo S-1210 e timeline`
- Status local: limpo.

## 4. Arquitetura atual do sistema

### 4.1. Componentes

| Camada        | Tecnologia                     | Função                                                                     |
| ------------- | ------------------------------ | -------------------------------------------------------------------------- |
| Frontend      | Vue 3, Vite, TypeScript, Pinia | UI do V2, login, seletor de empresa, telas S-1210, explorador, certificado |
| Backend       | FastAPI, Uvicorn, psycopg2     | API, auth, roteamento multi-tenant, upload, validações, explorador, S-1210 |
| Nginx         | Reverse proxy + static files   | TLS, SPA, proxy `/api`, upload grande, compatibilidade `/py-api`           |
| Banco sistema | PostgreSQL/Supabase            | Usuários, empresas, permissões, auditoria                                  |
| Banco dados   | PostgreSQL/Supabase            | Dados operacionais de cada empresa em schemas separados                    |
| V1 legado     | Node/Vue/serviços antigos      | Mantido para rollback e compatibilidade parcial                            |

### 4.2. Fluxo de login e empresa ativa

1. Usuário chama `POST /api/auth/login`.
2. Backend valida em `sistema.users`.
3. Backend busca empresas permitidas em `sistema.user_empresas` + `sistema.empresas_routing`.
4. Backend retorna JWT + lista de empresas.
5. Frontend salva token e empresas no Pinia/localStorage.
6. Usuário escolhe a empresa em `EmpresaSelectView.vue`.
7. Frontend salva o CNPJ ativo.
8. Toda request nova injeta:
   - `Authorization: Bearer <jwt>`
   - `X-Empresa-CNPJ: <cnpj>`

### 4.3. Fluxo backend para resolver tenant

Rotas novas usam o caminho CNPJ-based:

1. Middleware valida JWT.
2. Middleware valida se o `X-Empresa-CNPJ` está permitido para o usuário.
3. `tenant.get_schema_for_cnpj(cnpj)` busca `schema_name` em `empresas_routing`.
4. `tenant.empresa_conn(cnpj)` pega conexão do pool e executa `SET search_path TO "<schema>", public`.
5. A query roda sem precisar prefixar tabela com schema.
6. No `finally`, executa `RESET search_path` antes de devolver conexão ao pool.

Rotas antigas ainda usam `empresa_id`:

- `1 = APPA`
- `2 = SOLUCOES`

Essas rotas dependem de mapeamento hardcoded em `backend/app/tenant.py` e `src/stores/empresa.ts`. Isso funciona para as duas empresas atuais, mas **não escala automaticamente para uma terceira empresa**.

## 5. Bancos de dados e tipos de banco

### 5.1. Sistema DB

Função: autenticação, roteamento e auditoria.

Schema principal: `sistema`

Tabelas principais:

| Tabela             | Função                                                              |
| ------------------ | ------------------------------------------------------------------- |
| `users`            | Usuários, hash bcrypt, flag `super_admin`, ativo/inativo            |
| `empresas_routing` | CNPJ -> `schema_name`, razão social, versão de schema, flags        |
| `user_empresas`    | Relação usuário x empresa com papel (`admin`, `operador`, `leitor`) |
| `audit_log`        | Ações sensíveis, login, envio, upload, etc.                         |
| `schema_meta`      | Versão aplicada no schema sistema                                   |

Esse banco não deveria guardar dados operacionais de folha/eSocial. Ele é a lista telefônica: diz quem é o usuário, a que empresas ele tem acesso e em qual schema cada empresa mora.

### 5.2. Dados DB

Função: guardar dados operacionais das empresas.

Modelo atual: **1 schema PostgreSQL por empresa**.

Schemas documentados:

| Schema     | Papel                                          |
| ---------- | ---------------------------------------------- |
| `appa`     | Dados operacionais APPA                        |
| `solucoes` | Dados operacionais SOLUCOES                    |
| `legado`   | Dump cru/histórico do V1, read-only conceitual |
| `public`   | Tabelas compartilhadas ou resíduos históricos  |

Cada schema de empresa recebe as tabelas de `empresa_v1.0.0.sql` e incrementos de `empresa_v1.1.0.sql`.

### 5.3. Banco local / desenvolvimento

O backend ainda tem variáveis para um Postgres local:

- `LOCAL_DB_HOST`
- `LOCAL_DB_PORT`
- `LOCAL_DB_NAME`
- `LOCAL_DB_USER`
- `LOCAL_DB_PASSWORD`

O exemplo aponta para `easy_social_solucoes`, que foi usado historicamente para SOLUCOES local. Hoje isso deve ser lido como ambiente de desenvolvimento/legado, não como a topologia de produção desejada.

### 5.4. V1 legado

O V1 era o sistema operacional anterior, com Node/Vue legado, PM2 e backend Python legado. O plano de deploy do V2 preserva V1 para rollback. A configuração do Nginx ainda contempla `/py-api/` apontando para `127.0.0.1:8000`.

### 5.5. Observação importante sobre DSNs

A documentação recente fala em dois Supabase:

- Sistema DB: auth/routing/audit.
- Dados DB: schemas `appa`, `solucoes`, `legado`.

Mas o código atual tem trechos onde, se `SISTEMA_DB_URL` estiver definido, rotas legadas usam esse DSN também para dados com `search_path`. O script de backup também usa `SISTEMA_DB_URL` para tentar dump de `sistema`, `appa`, `solucoes` e `legado`.

Portanto, antes de qualquer operação real, confirmar:

```sql
SELECT nspname
FROM pg_namespace
WHERE nspname IN ('sistema', 'appa', 'solucoes', 'legado', 'public')
ORDER BY nspname;
```

Fazer isso no DSN de sistema e no DSN de dados. O DSN que contém `appa` e `solucoes` é o alvo real de migration/import/backup dos tenants.

## 6. Empresas atuais

### 6.1. Snapshot documentado

Pela documentação `docs/ARQUITETURA_MULTI_TENANT.md`, o snapshot de 11/05/2026 é:

| Empresa                              |             CNPJ | Schema     | Versão  | Status |
| ------------------------------------ | ---------------: | ---------- | ------- | ------ |
| APPA SERVICOS TEMPORARIOS LTDA       | `05969071000110` | `appa`     | `1.1.0` | ativa  |
| SOLUCOES SERVICOS TERCEIRIZADOS LTDA | `09445502000109` | `solucoes` | `1.1.0` | ativa  |

Usuários documentados:

| Usuário      | Papel                               |
| ------------ | ----------------------------------- |
| `xandeadmin` | `super_admin`, vê todas as empresas |
| `Ana`        | `operador` em APPA e SOLUCOES       |

### 6.2. APPA

Características:

- Empresa histórica do V1.
- Já tinha produção e grande volume antes do V2.
- Possui dados importados/históricos.
- Parte antiga não tem XML completo do governo, porque o V1 salvava campos parseados e não preservava todo XML bruto.
- Documentação cita volumes reais de APPA em 11/05/2026:
  - `explorador_eventos`: 375.985 linhas
  - `s1210_cpf_envios`: 223.837 linhas
  - `pipeline_cpf_results`: 113.025 linhas
  - `s1210_cpf_scope`: 110.651 linhas

### 6.3. SOLUCOES

Características:

- Empresa trabalhada no V2, com importações de ZIPs e fluxo novo.
- CNPJ documentado: `09445502000109`.
- Schema: `solucoes`.
- Histórico de docs indica que SOLUCOES passou por scripts locais e depois importação/migração para o modelo V2.
- Os ZIPs de SOLUCOES foram tratados com cuidado porque os nomes originais às vezes representavam mês de transmissão, não competência.

### 6.4. Biodiesel

Não encontrei `biodiesel`, `BIODIESEL`, `Biodiesel` ou variações em arquivos do workspace.

Conclusão segura:

- Biodiesel **não está cadastrado no V2 atual deste repositório**.
- Biodiesel **não aparece como schema ativo** na documentação lida.
- Biodiesel **não deve ser assumido como parte de APPA ou SOLUCOES**.
- Se Biodiesel já existe para vocês, ele está separado em outro repositório, outro banco, outro ambiente ou ainda não foi documentado aqui.

Recomendação: criar um registro explícito de arquitetura para Biodiesel antes de qualquer migração. Pode ser:

```text
BIODIESEL
- CNPJ: <preencher>
- ambiente atual: <fora do V2 / outro banco / outro repo>
- entra no V2? sim/não
- se entrar: schema_name dedicado, ex. biodiesel
- flags: { "origem": "separado", "tem_xml_completo": <true/false> }
```

## 7. O que era plano antigo e o que é realidade atual

### 7.1. Plano antigo: 1 banco por empresa

Os documentos em `Solucoes Dia 2/`, principalmente `BIBLIA_V2_NORTE.md`, `MIGRACAO_V1_V2.md` e `ARQUITETURA_MULTI_EMPRESA.md`, defendiam inicialmente:

- 1 Supabase Sistema.
- 1 Supabase APPA.
- 1 Supabase SOLUCOES.
- Futuramente 1 Supabase por nova empresa.

Essa era uma decisão de isolamento máximo, boa para LGPD/backup independente, mas cara e mais trabalhosa operacionalmente.

### 7.2. Modelo atual: schema por empresa

A documentação mais nova `docs/ARQUITETURA_MULTI_TENANT.md`, o gerador de apresentação e o migration runner atual descrevem:

- Sistema DB para auth/routing.
- Dados DB com schemas por empresa.
- `search_path` por conexão para isolar tenant.
- `empresas_routing` com `schema_name`, não `db_url`.

Esse é o modelo que aparece implementado no código de `tenant.py` e `migrate.py`.

### 7.3. Como eu reconciliaria os documentos

O plano “1 banco por empresa” virou uma hipótese/arquitetura-alvo antiga. O modelo prático atual é “1 schema por empresa”.

O que vale para operar hoje:

1. Empresa nova normal entra como **schema novo**.
2. Banco separado só deve ser considerado se houver exigência contratual, volume muito alto ou necessidade real de backup/restore físico independente.
3. Biodiesel, por estar “separado” segundo sua observação e ausente deste repo, precisa de decisão explícita antes de entrar no modelo V2.

## 8. Como adicionar uma nova empresa hoje

### 8.1. Resposta curta

Se a nova empresa usar apenas rotas modernas CNPJ-based, **não precisa mexer no build** para ela aparecer: basta cadastrar no banco sistema, criar schema, rodar migrations e vincular usuários. O frontend busca a lista de empresas no login e renderiza os cards dinamicamente.

Mas, como ainda existem rotas e telas legadas baseadas em `empresa_id` hardcoded (`1=APPA`, `2=SOLUCOES`), uma terceira empresa só estará 100% operacional quando essas telas forem migradas para CNPJ ou receberem um mapeamento novo no código.

### 8.2. Pré-requisitos de negócio

Antes de comando técnico, preencher:

| Campo               | Exemplo                                            |
| ------------------- | -------------------------------------------------- |
| CNPJ limpo          | `12345678000199`                                   |
| Razão social        | `NOVA EMPRESA LTDA`                                |
| Slug/schema         | `nova_empresa`                                     |
| Tipo/origem         | `v2_nativo`, `v1_legado`, `separado`, etc.         |
| Tem XML completo?   | `true` ou `false`                                  |
| Usuários operadores | e-mail/login e papel                               |
| Certificado A1      | caminho/forma de upload, validade, CNPJ do titular |
| Dados iniciais      | ZIPs já baixados, XLSX Domínio, rubricas/naturezas |

Para Biodiesel, eu adicionaria também:

```json
{
  "origem": "biodiesel_separado",
  "separado_do_v2_atual": true,
  "observacao": "nao misturar com APPA/SOLUCOES sem decisao explicita"
}
```

### 8.3. Passo 1 — escolher e validar o schema

Regra do código:

```text
^[a-z][a-z0-9_]{0,62}$
```

Exemplos válidos:

- `biodiesel`
- `nova_empresa`
- `acme_corp`

Exemplos ruins:

- `Biodiesel` (maiúscula)
- `bio-diesel` (hífen)
- `123empresa` (começa com número)
- `empresa nova` (espaço)

### 8.4. Passo 2 — criar schema no banco de dados dos tenants

No DSN que contém os schemas de dados:

```sql
CREATE SCHEMA IF NOT EXISTS nova_empresa;
```

### 8.5. Passo 3 — rodar migrations no schema novo

Para schema fresco, não basta rodar só `1.1.0`. O arquivo `empresa_v1.1.0.sql` é incremental e referencia tabelas criadas em `empresa_v1.0.0.sql`. Portanto, a ordem segura é:

```bash
cd /opt/easy-esocial/backend

.venv/bin/python -m app.migrate apply \
  --target empresa \
  --version 1.0.0 \
  --schema nova_empresa \
  --dsn "$DADOS_DSN"

.venv/bin/python -m app.migrate apply \
  --target empresa \
  --version 1.1.0 \
  --schema nova_empresa \
  --dsn "$DADOS_DSN"
```

Depois validar:

```bash
.venv/bin/python -m app.migrate status --schema nova_empresa --dsn "$DADOS_DSN"
```

### 8.6. Passo 4 — seed mínimo dentro do schema da empresa

As migrations criam estrutura, não criam os dados mestres da empresa. Para várias rotas legadas e de upload, a tabela `master_empresas` precisa ter pelo menos uma linha.

Exemplo conceitual:

```sql
INSERT INTO nova_empresa.master_empresas
  (nome, cnpj, db_name, db_host, db_port, ativo, tipo_estado)
VALUES
  ('NOVA EMPRESA LTDA', '12345678000199', 'postgres', 'supabase', 5432, TRUE, 'estado_1');
```

Também avaliar `config_esocial`:

```sql
INSERT INTO nova_empresa.config_esocial
  (cnpj, ini_valid_padrao, auto_detected)
VALUES
  ('12345678000199', '2025-01', FALSE);
```

O `ini_valid_padrao` deve ser confirmado conforme a validade inicial correta da empresa no eSocial. Não chutar em produção.

Seeds que podem ser necessários dependendo do uso:

- `tabela3_esocial_oficial`
- `naturezas_esocial`
- `master_naturezas_esocial`
- rubricas/de-para vindos do Domínio
- configurações de certificado A1

### 8.7. Passo 5 — registrar no Sistema DB

No schema `sistema`:

```sql
INSERT INTO sistema.empresas_routing
  (cnpj, razao_social, schema_name, schema_version, flags, ativo)
VALUES
  (
    '12345678000199',
    'NOVA EMPRESA LTDA',
    'nova_empresa',
    '1.1.0',
    '{"origem":"v2_nativo","tem_xml_completo":true}'::jsonb,
    TRUE
  );
```

Para Biodiesel, se entrar como tenant novo:

```sql
INSERT INTO sistema.empresas_routing
  (cnpj, razao_social, schema_name, schema_version, flags, ativo)
VALUES
  (
    '<CNPJ_BIODIESEL>',
    '<RAZAO_SOCIAL_BIODIESEL>',
    'biodiesel',
    '1.1.0',
    '{"origem":"biodiesel_separado","separado_do_v2_atual":true}'::jsonb,
    TRUE
  );
```

### 8.8. Passo 6 — vincular usuários

Exemplo:

```sql
SELECT id, email, nome FROM sistema.users WHERE email = 'operador@empresa.com';

INSERT INTO sistema.user_empresas (user_id, cnpj, papel)
VALUES ('<UUID>', '12345678000199', 'operador');
```

Papéis aceitos pela migration atual:

- `admin`
- `operador`
- `leitor`

Usuário `super_admin` vê todas as empresas sem precisar de linha em `user_empresas`, pelo comportamento de `auth_routes.py`.

### 8.9. Passo 7 — certificado A1

O modelo esperado é:

- PFX nunca em Git.
- PFX salvo em storage local controlado pelo backend.
- Senha criptografada com Fernet, usando `FERNET_KEY` no `.env`.
- Metadados em `certificados_a1`.

Ponto importante: `backend/app/cert_routes.py` ainda declara no próprio cabeçalho que está **single-tenant via `app.db`** e que multi-tenant via `tenant.empresa_conn` é TODO. Então, antes de operar certificado de uma terceira empresa em produção, é preciso revisar/adaptar as rotas de certificado para usar o CNPJ ativo e o schema correto.

### 8.10. Passo 8 — importar dados iniciais

Para dados que já existem em ZIP baixado do eSocial, a importação via Explorador não consome cota de consulta eSocial. Mesmo assim, manter regras:

- Não consultar eSocial sem autorização explícita.
- Não rodar download cirúrgico sem autorização explícita.
- Para recibo S-1210, não usar `explorador_eventos` como fonte final; fontes confiáveis são ZIP baixado do eSocial e `pipeline_cpf_results`.
- Em ZIP com retificações, escolher a versão mais recente por `dtRecibido` antes de concluir que não existe recibo novo.

### 8.11. Passo 9 — precisa rebuild/deploy?

Não precisa rebuild se:

- A empresa usa somente telas/rotas que já são CNPJ-based.
- A lista aparece via retorno de login.
- Nenhum hardcode novo é necessário.

Precisa rebuild/deploy se:

- Tela usada ainda depende de `empresa_id` numérico.
- For necessário adicionar mapeamento novo em `src/stores/empresa.ts` ou `backend/app/tenant.py`.
- For corrigida a rota de certificado para multi-tenant.
- For adicionada UI/admin para cadastro.

Se houver code change:

```bash
npm run build
```

Depois merge/push em `main` ou executar o deploy padrão na VPS:

```bash
bash /opt/easy-esocial/repo/deploy/scripts/deploy.sh main
```

### 8.12. Smoke test sem gastar eSocial

Depois de cadastrar:

1. Login com usuário vinculado.
2. Ver empresa nova na tela `/empresas`.
3. Escolher empresa.
4. Confirmar headers no frontend: `Authorization` + `X-Empresa-CNPJ`.
5. Chamar endpoint simples que lê o schema novo.
6. Verificar `schema_meta` no schema novo.
7. Conferir `master_empresas` e `config_esocial`.
8. Só depois planejar upload/import/envio.

## 9. Como “adicionar à Oviz/V2 e ao build” na prática

Como não encontrei termo `OVIZ` no código, estou assumindo que “Oviz/OV2” no pedido se refere ao Easy-eSocial V2 deste workspace.

Para adicionar uma empresa ao V2 existem dois níveis:

### 9.1. Nível banco/configuração

Esse é o caminho normal:

- Criar schema.
- Rodar migrations.
- Inserir `empresas_routing`.
- Vincular usuários.
- Seedar config mínima.

Resultado: empresa aparece no seletor após login, sem novo build.

### 9.2. Nível código/build

Necessário quando a tela/rota ainda não é genérica. Hoje os pontos mais sensíveis são:

- `src/stores/empresa.ts`: mapeia CNPJ APPA/SOLUCOES para `empresa_id` 1/2.
- `backend/app/tenant.py`: `_EMPRESA_SCHEMA = {1: "appa", 2: "solucoes"}` para API legada.
- Rotas de S-1210/timeline/explorador antigas ainda usam `empresa_id`.
- `cert_routes.py` ainda está single-tenant.

Se a nova empresa precisa usar essas telas agora, há duas alternativas:

1. Solução curta: adicionar um novo `empresa_id` hardcoded e fazer deploy. Funciona, mas perpetua legado.
2. Solução certa: migrar as telas/rotas restantes para CNPJ + `tenant.empresa_conn`. Mais limpo para N empresas.

Minha recomendação: para empresa nova comum, fazer o onboarding no banco e priorizar a migração das rotas legadas para CNPJ. Evitar expandir hardcode de `empresa_id`.

## 10. Backups

O script `deploy/scripts/backup_supabase.sh` faz:

```bash
pg_dump "$SISTEMA_DB_URL" \
  --no-owner --no-privileges \
  --schema=sistema --schema=appa --schema=solucoes --schema=legado \
  | gzip > /opt/easy-esocial/backups/easyesocial_<timestamp>.sql.gz
```

Retenção: 14 dias.

Ponto de atenção: se `Sistema DB` e `Dados DB` forem realmente projetos separados, esse script só funciona se `SISTEMA_DB_URL` apontar para o banco que contém também `appa`, `solucoes` e `legado`. Caso contrário, o backup não cobre os dados operacionais. Antes de confiar no backup, validar com `pg_restore --list` ou `zcat | grep "CREATE SCHEMA"` em um dump recente.

Recomendação:

- Ter backup separado do Sistema DB.
- Ter backup separado do Dados DB.
- Ter comando de restore testado.
- Se Biodiesel ficar separado, backup dele também separado e documentado.

## 11. Pontos fracos / riscos atuais

| Risco                                                                                     | Impacto                                                | Recomendação                                      |
| ----------------------------------------------------------------------------------------- | ------------------------------------------------------ | ------------------------------------------------- |
| Documentos antigos falam “1 DB por empresa”, docs novas/código falam “schema por empresa” | Operação confusa, onboarding no alvo errado            | Marcar docs antigas como histórico ou atualizar   |
| DSN de sistema vs dados inconsistente em código/scripts                                   | Backup/migration pode mirar banco errado               | Confirmar schemas em cada DSN e ajustar scripts   |
| `cert_routes.py` single-tenant                                                            | Certificado de nova empresa pode cair no schema errado | Migrar para `tenant.empresa_conn(cnpj)`           |
| Rotas legadas com `empresa_id` hardcoded                                                  | Terceira empresa não funciona em todas as telas        | Migrar para CNPJ-based                            |
| `auth.ts` usa localStorage para JWT                                                       | Diverge do plano de cookie httpOnly do SECURITY        | Planejar migração para cookie httpOnly/CSRF real  |
| `vite.config.ts` proxy local aponta `/api` para porta 8000, mas produção usa 8001         | Dev local pode bater backend errado                    | Revisar proxy dev para refletir backend atual     |
| Backup usa `SISTEMA_DB_URL` para schemas de dados                                         | Pode não backupear tenants                             | Separar `SISTEMA_DSN` e `DADOS_DSN`               |
| Não há cadastro admin via UI                                                              | Onboarding depende de SQL/terminal                     | Criar `/api/admin/empresas` e tela admin          |
| Biodiesel não documentado                                                                 | Risco de mistura ou esquecimento                       | Criar documento/registro explícito antes de mover |

## 12. Checklist final para nova empresa

Use isto como roteiro operacional:

- [ ] Confirmar se a empresa é V2 normal ou caso separado tipo Biodiesel.
- [ ] Confirmar CNPJ, razão social, slug/schema e flags.
- [ ] Confirmar o DSN correto do Dados DB.
- [ ] Criar schema.
- [ ] Rodar `empresa_v1.0.0.sql` no schema.
- [ ] Rodar `empresa_v1.1.0.sql` no schema.
- [ ] Conferir `schema_meta`.
- [ ] Inserir linha em `schema.master_empresas`.
- [ ] Inserir linha em `schema.config_esocial`, se aplicável.
- [ ] Seedar tabelas mestras necessárias.
- [ ] Inserir `sistema.empresas_routing`.
- [ ] Vincular usuários em `sistema.user_empresas`.
- [ ] Validar login e seletor de empresa.
- [ ] Validar endpoint CNPJ-based simples.
- [ ] Ajustar rotas legadas se a empresa precisar usar S-1210/timeline antigo.
- [ ] Corrigir/validar certificado A1 multi-tenant.
- [ ] Importar dados iniciais sem consultar eSocial, se já houver ZIPs locais.
- [ ] Fazer backup antes e depois da carga.
- [ ] Documentar o que foi feito.

## 13. Conclusão

O V2 está estruturado para virar o sistema principal: build automatizado na VPS, FastAPI com Nginx, frontend Vue, auth, seletor de empresa e roteamento multi-tenant. O desenho operacional atual é **schema por empresa**, com APPA e SOLUCOES ativas.

Para uma empresa nova, o caminho correto hoje é cadastrar como novo schema + `empresas_routing` + vínculo de usuário. O build só entra se a empresa precisar usar telas ainda presas a `empresa_id` ou se formos corrigir gaps como certificado multi-tenant.

Biodiesel deve permanecer tratado como separado até existir registro formal neste V2. Não há evidência no repo de que ele já esteja no conjunto APPA/SOLUCOES.
