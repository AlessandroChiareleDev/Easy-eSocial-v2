-- =========================================================================
-- Sistema DB — schema v1.0.0
-- =========================================================================
-- Banco central que NÃO contém dados de empresa.
-- Responsável por: autenticação, roteamento multi-tenant, auditoria global.
--
-- Idempotente. Pode rodar várias vezes sem erro.
-- =========================================================================

BEGIN;

-- pgcrypto pra gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- -------------------------------------------------------------------------
-- 1) users — autenticação centralizada
-- -------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           TEXT UNIQUE NOT NULL,
    password_hash   TEXT NOT NULL,                  -- bcrypt (compat V1)
    nome            TEXT,
    ativo           BOOLEAN NOT NULL DEFAULT TRUE,
    super_admin     BOOLEAN NOT NULL DEFAULT FALSE,
    criado_em       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ultimo_login    TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_users_email_ativo
    ON users (email) WHERE ativo = TRUE;

-- -------------------------------------------------------------------------
-- 2) empresas_routing — diretório de empresas + conn string do DB de cada uma
-- -------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS empresas_routing (
    cnpj            TEXT PRIMARY KEY CHECK (length(cnpj) = 14),
    razao_social    TEXT NOT NULL,
    db_url          TEXT NOT NULL,                  -- conn string do banco da empresa
    schema_version  TEXT NOT NULL,                  -- ex: '1.0.0' (deve casar com empresa_vX.Y.Z.sql)
    flags           JSONB NOT NULL DEFAULT '{}'::jsonb,
    ativo           BOOLEAN NOT NULL DEFAULT TRUE,
    criado_em       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    atualizado_em   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_empresas_routing_ativo
    ON empresas_routing (ativo) WHERE ativo = TRUE;

-- -------------------------------------------------------------------------
-- 3) user_empresas — N:N usuário ↔ empresa com papel
-- -------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS user_empresas (
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    cnpj        TEXT NOT NULL REFERENCES empresas_routing(cnpj) ON DELETE CASCADE,
    papel       TEXT NOT NULL CHECK (papel IN ('admin','operador','leitor')),
    criado_em   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, cnpj)
);

CREATE INDEX IF NOT EXISTS idx_user_empresas_cnpj ON user_empresas (cnpj);

-- -------------------------------------------------------------------------
-- 4) audit_log — registro de ações sensíveis (login, upload cert, envio, etc)
-- -------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS audit_log (
    id          BIGSERIAL PRIMARY KEY,
    ts          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    user_id     UUID,
    cnpj        TEXT,
    acao        TEXT NOT NULL,
    ip          TEXT,
    detalhes    JSONB
);

CREATE INDEX IF NOT EXISTS idx_audit_ts        ON audit_log (ts DESC);
CREATE INDEX IF NOT EXISTS idx_audit_user      ON audit_log (user_id, ts DESC);
CREATE INDEX IF NOT EXISTS idx_audit_cnpj      ON audit_log (cnpj, ts DESC) WHERE cnpj IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_audit_acao      ON audit_log (acao, ts DESC);

-- -------------------------------------------------------------------------
-- 5) schema_meta — controle de versão do próprio Sistema DB
-- -------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS schema_meta (
    target          TEXT PRIMARY KEY CHECK (target IN ('sistema','empresa')),
    version         TEXT NOT NULL,
    aplicado_em     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO schema_meta (target, version)
    VALUES ('sistema', '1.0.0')
    ON CONFLICT (target) DO UPDATE
        SET version = EXCLUDED.version,
            aplicado_em = NOW();

COMMIT;
