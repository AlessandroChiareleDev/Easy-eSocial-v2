-- =========================================================================
-- Migration 001 — Explorador de Arquivos / fundação
-- Idempotente: pode rodar quantas vezes quiser.
-- Banco alvo: easy_social_solucoes
-- =========================================================================

BEGIN;

-- -------------------------------------------------------------------------
-- 1) master_empresas: coluna tipo_estado (estado_1 / estado_2)
-- -------------------------------------------------------------------------
ALTER TABLE master_empresas
    ADD COLUMN IF NOT EXISTS tipo_estado VARCHAR(16) NOT NULL DEFAULT 'estado_1';

-- CHECK constraint só se ainda não existe
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'master_empresas_tipo_estado_chk'
    ) THEN
        ALTER TABLE master_empresas
            ADD CONSTRAINT master_empresas_tipo_estado_chk
            CHECK (tipo_estado IN ('estado_1','estado_2'));
    END IF;
END$$;

-- -------------------------------------------------------------------------
-- 2) empresa_zips_brutos — guarda o zip cru como Large Object (OID)
-- -------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS empresa_zips_brutos (
    id                       BIGSERIAL PRIMARY KEY,
    empresa_id               BIGINT NOT NULL REFERENCES master_empresas(id),
    -- período pedido pelo usuário no portal eSocial
    dt_ini                   DATE NOT NULL,
    dt_fim                   DATE NOT NULL,
    -- sequencial gerado pelo eSocial (extraído do nome do arquivo, opcional)
    sequencial_esocial       VARCHAR(40),
    -- arquivo cru
    nome_arquivo_original    TEXT NOT NULL,
    sha256                   CHAR(64) NOT NULL,
    tamanho_bytes            BIGINT NOT NULL,
    conteudo_oid             OID NOT NULL,        -- pg_largeobject
    -- contagens (preenchidas após extração)
    total_xmls               INT,
    perapur_dominante        VARCHAR(7),
    -- auditoria
    enviado_em               TIMESTAMP NOT NULL DEFAULT now(),
    extraido_em              TIMESTAMP,
    extracao_status          VARCHAR(16) NOT NULL DEFAULT 'pendente',
    extracao_erro            TEXT,
    CONSTRAINT empresa_zips_brutos_status_chk
        CHECK (extracao_status IN ('pendente','extraindo','ok','erro')),
    CONSTRAINT empresa_zips_brutos_dedup_uq
        UNIQUE (empresa_id, sha256)
);

CREATE INDEX IF NOT EXISTS ix_zips_periodo
    ON empresa_zips_brutos (empresa_id, dt_ini, dt_fim);
CREATE INDEX IF NOT EXISTS ix_zips_status
    ON empresa_zips_brutos (extracao_status);

-- -------------------------------------------------------------------------
-- 3) explorador_eventos: amarração com zip + chain walk
-- -------------------------------------------------------------------------
ALTER TABLE explorador_eventos
    ADD COLUMN IF NOT EXISTS zip_id              BIGINT REFERENCES empresa_zips_brutos(id) ON DELETE CASCADE,
    ADD COLUMN IF NOT EXISTS xml_entry_name      TEXT,
    ADD COLUMN IF NOT EXISTS referenciado_recibo VARCHAR(40);

CREATE INDEX IF NOT EXISTS ix_evt_zip
    ON explorador_eventos (zip_id);
CREATE INDEX IF NOT EXISTS ix_evt_cpf_per
    ON explorador_eventos (cpf, per_apur);
CREATE INDEX IF NOT EXISTS ix_evt_recibo
    ON explorador_eventos (nr_recibo);
CREATE INDEX IF NOT EXISTS ix_evt_ref
    ON explorador_eventos (referenciado_recibo);

COMMIT;
