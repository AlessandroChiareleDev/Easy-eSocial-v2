-- =========================================================================
-- Empresa schema v1.1.0 — Landing tables F8 (porte V1)
-- =========================================================================
-- Adiciona tabelas usadas pelo upload de XLSX Dominio + cruzamento contabil.
-- Compativel com V1: tabela_eb / analise_natureza* / cruzamento_*.
--
-- Idempotente. Aplicar com:
--   python -m app.migrate apply --target empresa --version 1.1.0 --schema <appa|solucoes> --dsn $SISTEMA_DB_URL
-- =========================================================================

BEGIN;

-- -------------------------------------------------------------------------
-- 1) tabela_eb — landing do XLSX da Tabela EB do Datamace (rubricas)
--    V1 usa col_a..col_x (Excel A-X). Mantemos col_a..col_z para folga.
-- -------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.tabela_eb (
    id          SERIAL PRIMARY KEY,
    col_a       TEXT, col_b TEXT, col_c TEXT, col_d TEXT, col_e TEXT,
    col_f       TEXT, col_g TEXT, col_h TEXT, col_i TEXT, col_j TEXT,
    col_k       TEXT, col_l TEXT, col_m TEXT, col_n TEXT, col_o TEXT,
    col_p       TEXT, col_q TEXT, col_r TEXT, col_s TEXT, col_t TEXT,
    col_u       TEXT, col_v TEXT, col_w TEXT, col_x TEXT, col_y TEXT, col_z TEXT,
    raw_data    JSONB,
    upload_id   INTEGER,
    criado_em   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tabela_eb_col_a ON public.tabela_eb (col_a);
CREATE INDEX IF NOT EXISTS idx_tabela_eb_upload ON public.tabela_eb (upload_id);

-- FK em rubrica_corrections.tabela_eb_id (criado em v1.0.0 mas sem FK)
DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
         WHERE table_schema = current_schema()
           AND table_name   = 'rubrica_corrections'
           AND constraint_name = 'rubrica_corrections_tabela_eb_id_fkey'
    ) THEN
        ALTER TABLE public.rubrica_corrections
            ADD CONSTRAINT rubrica_corrections_tabela_eb_id_fkey
            FOREIGN KEY (tabela_eb_id) REFERENCES public.tabela_eb(id)
            ON DELETE SET NULL
            NOT VALID;  -- nao valida historico V1 (orfaos), so insercoes novas
    END IF;
END $$;

-- -------------------------------------------------------------------------
-- 2) analise_natureza — landing do XLSX de analise de naturezas (Domínio)
-- -------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.analise_natureza (
    id          SERIAL PRIMARY KEY,
    row_number  INTEGER,
    col_a       TEXT, col_b TEXT, col_c TEXT, col_d TEXT, col_e TEXT,
    col_f       TEXT, col_g TEXT, col_h TEXT, col_i TEXT, col_j TEXT,
    upload_id   INTEGER,
    criado_em   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_analise_natureza_col_a ON public.analise_natureza (col_a);
CREATE INDEX IF NOT EXISTS idx_analise_natureza_status ON public.analise_natureza ((UPPER(TRIM(col_d))));

-- FK em correcoes_staging.analise_natureza_id (existente em v1.0.0)
DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
         WHERE table_schema = current_schema()
           AND table_name   = 'correcoes_staging'
           AND constraint_name = 'correcoes_staging_analise_natureza_id_fkey'
    ) THEN
        ALTER TABLE public.correcoes_staging
            ADD CONSTRAINT correcoes_staging_analise_natureza_id_fkey
            FOREIGN KEY (analise_natureza_id) REFERENCES public.analise_natureza(id)
            ON DELETE CASCADE
            NOT VALID;  -- nao valida historico V1 (orfaos), so insercoes novas
    END IF;
END $$;

-- -------------------------------------------------------------------------
-- 3) analise_natureza_certo — espelho com correcoes aplicadas (col_c reflete natureza_nova)
-- -------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.analise_natureza_certo (
    id                      SERIAL PRIMARY KEY,
    analise_natureza_id     INTEGER REFERENCES public.analise_natureza(id) ON DELETE CASCADE,
    codigoevento            TEXT,
    nome_evento             TEXT,
    col_c                   TEXT,                 -- natureza atualizada (= natureza_nova)
    col_d                   TEXT DEFAULT 'OK',    -- status
    natureza_anterior       TEXT,
    natureza_nova           TEXT,
    motivo                  TEXT,
    usuario_correcao        TEXT,
    data_correcao           TIMESTAMPTZ DEFAULT NOW(),
    criado_em               TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_anc_codevento ON public.analise_natureza_certo (codigoevento);

-- -------------------------------------------------------------------------
-- 4) cruzamento_uploads — metadata de cada upload de cruzamento
-- -------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.cruzamento_uploads (
    id              SERIAL PRIMARY KEY,
    filename        TEXT,
    original_name   TEXT,
    file_size       BIGINT,
    sheet_count     INTEGER,
    sheet_names     JSONB,             -- array das abas
    criado_em       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- -------------------------------------------------------------------------
-- 5) cruzamento_tabela_a / cruzamento_tabela_b — landing das 2 abas do XLSX de cruzamento
--    V1 mapeia col_a..col_zz dinamico. Materializamos col_a..col_az (52 colunas) + raw_data.
-- -------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.cruzamento_tabela_a (
    id                      SERIAL PRIMARY KEY,
    cruzamento_upload_id    INTEGER REFERENCES public.cruzamento_uploads(id) ON DELETE CASCADE,
    row_number              INTEGER,
    col_a TEXT, col_b TEXT, col_c TEXT, col_d TEXT, col_e TEXT,
    col_f TEXT, col_g TEXT, col_h TEXT, col_i TEXT, col_j TEXT,
    col_k TEXT, col_l TEXT, col_m TEXT, col_n TEXT, col_o TEXT,
    col_p TEXT, col_q TEXT, col_r TEXT, col_s TEXT, col_t TEXT,
    col_u TEXT, col_v TEXT, col_w TEXT, col_x TEXT, col_y TEXT, col_z TEXT,
    col_aa TEXT, col_ab TEXT, col_ac TEXT, col_ad TEXT, col_ae TEXT,
    col_af TEXT, col_ag TEXT, col_ah TEXT, col_ai TEXT, col_aj TEXT,
    col_ak TEXT, col_al TEXT, col_am TEXT, col_an TEXT, col_ao TEXT,
    col_ap TEXT, col_aq TEXT, col_ar TEXT, col_as TEXT, col_at TEXT,
    col_au TEXT, col_av TEXT, col_aw TEXT, col_ax TEXT, col_ay TEXT, col_az TEXT,
    raw_data                JSONB,
    criado_em               TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cruzamento_a_upload ON public.cruzamento_tabela_a (cruzamento_upload_id);
CREATE INDEX IF NOT EXISTS idx_cruzamento_a_col_a  ON public.cruzamento_tabela_a (col_a);

CREATE TABLE IF NOT EXISTS public.cruzamento_tabela_b (
    id                      SERIAL PRIMARY KEY,
    cruzamento_upload_id    INTEGER REFERENCES public.cruzamento_uploads(id) ON DELETE CASCADE,
    row_number              INTEGER,
    col_a TEXT, col_b TEXT, col_c TEXT, col_d TEXT, col_e TEXT,
    col_f TEXT, col_g TEXT, col_h TEXT, col_i TEXT, col_j TEXT,
    col_k TEXT, col_l TEXT, col_m TEXT, col_n TEXT, col_o TEXT,
    col_p TEXT, col_q TEXT, col_r TEXT, col_s TEXT, col_t TEXT,
    col_u TEXT, col_v TEXT, col_w TEXT, col_x TEXT, col_y TEXT, col_z TEXT,
    col_aa TEXT, col_ab TEXT, col_ac TEXT, col_ad TEXT, col_ae TEXT,
    col_af TEXT, col_ag TEXT, col_ah TEXT, col_ai TEXT, col_aj TEXT,
    col_ak TEXT, col_al TEXT, col_am TEXT, col_an TEXT, col_ao TEXT,
    col_ap TEXT, col_aq TEXT, col_ar TEXT, col_as TEXT, col_at TEXT,
    col_au TEXT, col_av TEXT, col_aw TEXT, col_ax TEXT, col_ay TEXT, col_az TEXT,
    raw_data                JSONB,
    criado_em               TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cruzamento_b_upload ON public.cruzamento_tabela_b (cruzamento_upload_id);
CREATE INDEX IF NOT EXISTS idx_cruzamento_b_col_a  ON public.cruzamento_tabela_b (col_a);

-- -------------------------------------------------------------------------
-- 6) cruzamento_resultado — INNER JOIN A x B por col_a (codigo)
-- -------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.cruzamento_resultado (
    id                      SERIAL PRIMARY KEY,
    cruzamento_upload_id    INTEGER REFERENCES public.cruzamento_uploads(id) ON DELETE CASCADE,
    row_number              INTEGER,
    codigo                  TEXT,
    nome_evento             TEXT,
    natureza_esocial        TEXT,
    cod_inss                TEXT,
    cod_irrf                TEXT,
    cod_fgts                TEXT,
    criado_em               TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cruzamento_res_upload ON public.cruzamento_resultado (cruzamento_upload_id);
CREATE INDEX IF NOT EXISTS idx_cruzamento_res_codigo ON public.cruzamento_resultado (codigo);

-- -------------------------------------------------------------------------
-- 7) Atualiza schema_meta -> 1.1.0
-- -------------------------------------------------------------------------
INSERT INTO public.schema_meta (target, version)
    VALUES ('empresa', '1.1.0')
    ON CONFLICT (target, version) DO NOTHING;

COMMIT;
