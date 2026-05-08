# Migrations V2 — Schema Único

Estrutura de migrations consolidada conforme **BIBLIA_V2_NORTE.md** Fase 2.

## Layout

```
migrations/
├── sistema/
│   └── sistema_v1.0.0.sql      # DB de sistema (auth, routing, audit)
├── empresa/
│   └── empresa_v1.0.0.sql      # Schema base por empresa (1 DB por CNPJ)
└── _legacy/
    ├── 001_explorador_init.sql       # pre-consolidacao (NAO roda)
    ├── 002_explorador_atividade.sql
    ├── 003_chain_walk.sql
    ├── 004_xml_por_evento.sql
    ├── _dump_full.sql                # pg_dump bruto (origem do empresa_v1.0.0)
    └── _dump_base.sql                # dumps de extracao
```

## Modelo

- **Sistema DB** (1 unico): tabelas `users`, `empresas_routing`, `user_empresas`, `audit_log`, `schema_meta`.
- **Empresa DB** (1 por CNPJ): 36 tabelas do pipeline eSocial (S-1210, master, timeline, certificados, pipeline, naturezas, etc).
- **schema_meta** existe nos DOIS escopos e registra `(target, version)` aplicada.

## Como rodar

### 1. Sistema

```powershell
$env:LOCAL_DB_NAME = 'easy_social_sistema'   # ou crie esse DB e ajuste .env
python -m app.migrate apply --target sistema --version 1.0.0
```

### 2. Empresa (uma por CNPJ)

```powershell
# Crie o DB primeiro: CREATE DATABASE empresa_09445502000109;
python -m app.migrate apply --target empresa --version 1.0.0 --db empresa_09445502000109
```

Ou via DSN completo (override total):

```powershell
python -m app.migrate apply --target empresa --version 1.0.0 --dsn "postgresql://user:pass@host:5432/empresa_X"
```

### 3. Status

```powershell
python -m app.migrate status                               # DB do .env
python -m app.migrate status --db empresa_09445502000109   # DB especifico
python -m app.migrate status --target empresa
```

## Idempotencia

- O **runner** consulta `schema_meta` ANTES de aplicar e PULA se a versao ja existe.
- O **SQL** usa `IF NOT EXISTS` em CREATE TABLE / SEQUENCE / INDEX, mas `ALTER TABLE ADD CONSTRAINT` NAO eh idempotente.
- Logo: **nao tente re-aplicar a mesma versao em DB ja migrado** — o runner ja te protege, mas se forcar via `psql -f` direto, vai dar erro de duplicate constraint. Use o runner.

## Origem do empresa_v1.0.0.sql

Extraido via `pg_dump --schema-only` do banco `easy_social_solucoes` (V1 producao local), filtrando 36 tabelas eSocial:

- master_empresas, master_atividades, master_perfis, master_usuario_empresa, master_naturezas_esocial
- explorador_eventos, explorador_atividade, explorador_importacoes, explorador_rubricas
- empresa_zips_brutos
- pipeline_cpf_results, pipeline_runs, pipeline_snapshots, pipeline_audit, pipeline_correcao
- s1210_cpf_blocklist, s1210_cpf_envios, s1210_cpf_recibo, s1210_cpf_scope, s1210_lote1_codfunc_scope, s1210_operadoras, s1210_xlsx
- timeline_envio, timeline_envio_item, timeline_mes
- esocial_envios, esocial_depara, esocial_tabela3_natureza, tabela3_esocial_oficial, tabela_marcos
- naturezas_esocial
- certificados_a1, senha_certificado_salva, config_esocial
- rubrica_corrections, correcoes_staging, auditoria_naturezas

**FKs removidos**: `auditoria_naturezas → analise_natureza`, `correcoes_staging → analise_natureza`, `rubrica_corrections → tabela_eb` (todas tabelas V1-legacy nao incluidas no schema empresa V2).

## Proximas versoes

Para evoluir o schema, criar:

- `sistema/sistema_v1.1.0.sql` — incremento sobre sistema_v1.0.0
- `empresa/empresa_v1.1.0.sql` — incremento sobre empresa_v1.0.0

Cada arquivo deve registrar a propria versao no fim:

```sql
INSERT INTO public.schema_meta (target, version) VALUES ('empresa','1.1.0')
ON CONFLICT (target, version) DO NOTHING;
```
