-- =========================================================================
-- Migration 003 — Chain Walk v2 (timeline mensal de S-1210)
-- Idempotente.
-- Ver docs/CHAIN_WALK_V2.md
-- =========================================================================

BEGIN;

-- -------------------------------------------------------------------------
-- 1) timeline_mes — uma régua por (empresa, perApur)
-- -------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS timeline_mes (
    id              BIGSERIAL PRIMARY KEY,
    empresa_id      BIGINT NOT NULL REFERENCES master_empresas(id) ON DELETE CASCADE,
    per_apur        VARCHAR(7) NOT NULL,             -- 'YYYY-MM'
    head_envio_id   BIGINT NULL,                     -- FK preenchida abaixo
    criado_em       TIMESTAMP NOT NULL DEFAULT now(),
    CONSTRAINT timeline_mes_uq UNIQUE (empresa_id, per_apur)
);

CREATE INDEX IF NOT EXISTS ix_timeline_mes_emp
    ON timeline_mes (empresa_id, per_apur DESC);

-- -------------------------------------------------------------------------
-- 2) timeline_envio — cada bolinha da régua
-- -------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS timeline_envio (
    id                BIGSERIAL PRIMARY KEY,
    timeline_mes_id   BIGINT NOT NULL REFERENCES timeline_mes(id) ON DELETE CASCADE,
    sequencia         INT NOT NULL,                  -- 0 = zip_inicial
    tipo              VARCHAR(20) NOT NULL,          -- zip_inicial | envio_massa | envio_individual
    iniciado_em       TIMESTAMP NOT NULL DEFAULT now(),
    finalizado_em     TIMESTAMP NULL,
    status            VARCHAR(16) NOT NULL DEFAULT 'concluido',
    total_tentados    INT NOT NULL DEFAULT 0,
    total_sucesso     INT NOT NULL DEFAULT 0,
    total_erro        INT NOT NULL DEFAULT 0,
    resumo            JSONB NULL,
    CONSTRAINT timeline_envio_seq_uq UNIQUE (timeline_mes_id, sequencia),
    CONSTRAINT timeline_envio_tipo_chk
        CHECK (tipo IN ('zip_inicial','envio_massa','envio_individual')),
    CONSTRAINT timeline_envio_status_chk
        CHECK (status IN ('em_andamento','concluido','falhou'))
);

CREATE INDEX IF NOT EXISTS ix_timeline_envio_mes
    ON timeline_envio (timeline_mes_id, sequencia);

-- FK head_envio_id agora que timeline_envio existe
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'timeline_mes_head_fk'
    ) THEN
        ALTER TABLE timeline_mes
            ADD CONSTRAINT timeline_mes_head_fk
            FOREIGN KEY (head_envio_id) REFERENCES timeline_envio(id) ON DELETE SET NULL;
    END IF;
END$$;

-- -------------------------------------------------------------------------
-- 3) timeline_envio_item — granular por CPF dentro do envio
-- -------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS timeline_envio_item (
    id                  BIGSERIAL PRIMARY KEY,
    timeline_envio_id   BIGINT NOT NULL REFERENCES timeline_envio(id) ON DELETE CASCADE,
    cpf                 VARCHAR(14) NOT NULL,
    tipo_evento         VARCHAR(8)  NOT NULL DEFAULT 'S-1210',
    status              VARCHAR(24) NOT NULL,
    versao_anterior_id  BIGINT NULL,                 -- FK explorador_eventos (sem ON DELETE)
    versao_nova_id      BIGINT NULL,
    nr_recibo_anterior  VARCHAR(40) NULL,
    nr_recibo_novo      VARCHAR(40) NULL,
    xml_enviado_oid     OID NULL,
    xml_retorno_oid     OID NULL,
    erro_codigo         VARCHAR(20) NULL,
    erro_mensagem       TEXT NULL,
    duracao_ms          INT NULL,
    criado_em           TIMESTAMP NOT NULL DEFAULT now(),
    CONSTRAINT timeline_envio_item_status_chk
        CHECK (status IN ('sucesso','erro_esocial','rejeitado_local','falha_rede','pendente'))
);

CREATE INDEX IF NOT EXISTS ix_timeline_item_envio
    ON timeline_envio_item (timeline_envio_id);
CREATE INDEX IF NOT EXISTS ix_timeline_item_cpf
    ON timeline_envio_item (cpf, tipo_evento);

-- -------------------------------------------------------------------------
-- 4) explorador_eventos: ponteiros de cadeia
-- -------------------------------------------------------------------------
ALTER TABLE explorador_eventos
    ADD COLUMN IF NOT EXISTS retificado_por_id BIGINT NULL,
    ADD COLUMN IF NOT EXISTS origem_envio_id   BIGINT NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'explorador_eventos_retif_fk'
    ) THEN
        ALTER TABLE explorador_eventos
            ADD CONSTRAINT explorador_eventos_retif_fk
            FOREIGN KEY (retificado_por_id) REFERENCES explorador_eventos(id) ON DELETE SET NULL;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'explorador_eventos_origem_envio_fk'
    ) THEN
        ALTER TABLE explorador_eventos
            ADD CONSTRAINT explorador_eventos_origem_envio_fk
            FOREIGN KEY (origem_envio_id) REFERENCES timeline_envio(id) ON DELETE SET NULL;
    END IF;
END$$;

-- Índices úteis
CREATE INDEX IF NOT EXISTS ix_evt_cadeia_s1210
    ON explorador_eventos (cpf, per_apur, tipo_evento)
    WHERE tipo_evento = 'S-1210';

CREATE INDEX IF NOT EXISTS ix_evt_head_s1210
    ON explorador_eventos (cpf, per_apur)
    WHERE tipo_evento = 'S-1210' AND retificado_por_id IS NULL;

CREATE INDEX IF NOT EXISTS ix_evt_origem_envio
    ON explorador_eventos (origem_envio_id);

COMMIT;
