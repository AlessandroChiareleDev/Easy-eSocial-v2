-- =====================================================================
-- empresa_v1.0.0.sql
-- Schema base por empresa (1 DB por CNPJ) - eSocial pipeline
-- =====================================================================
-- Origem: pg_dump --schema-only do banco V1 (easy_social_solucoes)
-- Tabelas: 36 (eSocial pipeline + master + timeline + s1210 + certificados)
-- Idempotente: CREATE TABLE/SEQUENCE/INDEX usam IF NOT EXISTS.
-- ALTER TABLE ADD CONSTRAINT: roda apenas em DB fresco (primeira aplicacao).
-- =====================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS public.schema_meta (
    target text NOT NULL CHECK (target IN ('sistema','empresa')),
    version text NOT NULL,
    aplicado_em timestamp with time zone NOT NULL DEFAULT now(),
    PRIMARY KEY (target, version)
);
--
--



SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_table_access_method = heap;

--
-- Name: auditoria_naturezas; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.auditoria_naturezas (
    id integer NOT NULL,
    analise_natureza_id integer,
    codigoevento character varying(255),
    natureza_anterior text,
    natureza_nova text,
    usuario character varying(255) DEFAULT 'sistema'::character varying,
    data_alteracao timestamp with time zone DEFAULT now(),
    motivo text
);


--
-- Name: auditoria_naturezas_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE IF NOT EXISTS public.auditoria_naturezas_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: auditoria_naturezas_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.auditoria_naturezas_id_seq OWNED BY public.auditoria_naturezas.id;


--
-- Name: certificados_a1; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.certificados_a1 (
    id integer NOT NULL,
    cnpj character varying(14) NOT NULL,
    titular character varying(255),
    emissor character varying(255),
    numero_serie character varying(100),
    validade_inicio timestamp without time zone,
    validade_fim timestamp without time zone,
    arquivo_path character varying(500) NOT NULL,
    senha_encrypted text NOT NULL,
    ativo boolean DEFAULT false,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now(),
    empresa_id integer
);


--
-- Name: certificados_a1_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE IF NOT EXISTS public.certificados_a1_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: certificados_a1_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.certificados_a1_id_seq OWNED BY public.certificados_a1.id;


--
-- Name: config_esocial; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.config_esocial (
    id integer NOT NULL,
    cnpj character varying(20) NOT NULL,
    ini_valid_padrao character varying(10),
    auto_detected boolean DEFAULT false,
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: config_esocial_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE IF NOT EXISTS public.config_esocial_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: config_esocial_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.config_esocial_id_seq OWNED BY public.config_esocial.id;


--
-- Name: correcoes_staging; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.correcoes_staging (
    id integer NOT NULL,
    analise_natureza_id integer NOT NULL,
    codigoevento character varying(20) NOT NULL,
    nome_evento character varying(500),
    natureza_anterior character varying(500),
    natureza_nova_codigo character varying(20) NOT NULL,
    natureza_nova_nome character varying(500) NOT NULL,
    motivo text DEFAULT ''::text,
    usuario_id integer,
    usuario_nome character varying(200) DEFAULT 'sistema'::character varying,
    status character varying(20) DEFAULT 'pendente'::character varying,
    criado_em timestamp with time zone DEFAULT now(),
    aplicado_em timestamp with time zone
);


--
-- Name: correcoes_staging_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE IF NOT EXISTS public.correcoes_staging_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: correcoes_staging_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.correcoes_staging_id_seq OWNED BY public.correcoes_staging.id;


--
-- Name: empresa_zips_brutos; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.empresa_zips_brutos (
    id bigint NOT NULL,
    empresa_id bigint NOT NULL,
    dt_ini date NOT NULL,
    dt_fim date NOT NULL,
    sequencial_esocial character varying(40),
    nome_arquivo_original text NOT NULL,
    sha256 character(64) NOT NULL,
    tamanho_bytes bigint NOT NULL,
    conteudo_oid oid NOT NULL,
    total_xmls integer,
    perapur_dominante character varying(7),
    enviado_em timestamp without time zone DEFAULT now() NOT NULL,
    extraido_em timestamp without time zone,
    extracao_status character varying(16) DEFAULT 'pendente'::character varying NOT NULL,
    extracao_erro text,
    CONSTRAINT empresa_zips_brutos_status_chk CHECK (((extracao_status)::text = ANY ((ARRAY['pendente'::character varying, 'extraindo'::character varying, 'ok'::character varying, 'erro'::character varying])::text[])))
);


--
-- Name: empresa_zips_brutos_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE IF NOT EXISTS public.empresa_zips_brutos_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: empresa_zips_brutos_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.empresa_zips_brutos_id_seq OWNED BY public.empresa_zips_brutos.id;


--
-- Name: esocial_depara; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.esocial_depara (
    id integer NOT NULL,
    cod_rubrica text NOT NULL,
    campo text NOT NULL,
    valor_anterior text,
    valor_novo text NOT NULL,
    nome_rubrica text,
    regra text DEFAULT 'manual'::text,
    status character varying(20) DEFAULT 'pendente'::character varying,
    created_at timestamp with time zone DEFAULT now(),
    aplicado_em timestamp with time zone
);


--
-- Name: esocial_depara_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE IF NOT EXISTS public.esocial_depara_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: esocial_depara_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.esocial_depara_id_seq OWNED BY public.esocial_depara.id;


--
-- Name: esocial_envios; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.esocial_envios (
    id integer NOT NULL,
    tipo_evento character varying(30) DEFAULT 'S-1010'::character varying NOT NULL,
    modo character varying(20) DEFAULT 'alteracao'::character varying NOT NULL,
    status character varying(30) DEFAULT 'enviado'::character varying NOT NULL,
    protocolo_envio character varying(100),
    codigo_resposta character varying(10),
    descricao_resposta text,
    total_eventos integer DEFAULT 0,
    rubrica_ids jsonb,
    xml_retorno text,
    ocorrencias jsonb,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    ambiente character varying(2) DEFAULT '2'::character varying NOT NULL,
    ini_valid character varying(10),
    rubrica_detalhes jsonb,
    xml_enviado text,
    recibo_consulta jsonb,
    nr_recibo character varying(100)
);


--
-- Name: esocial_envios_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE IF NOT EXISTS public.esocial_envios_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: esocial_envios_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.esocial_envios_id_seq OWNED BY public.esocial_envios.id;


--
-- Name: esocial_tabela3_natureza; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.esocial_tabela3_natureza (
    codigo integer NOT NULL,
    nome character varying(200) NOT NULL,
    dt_inicio date NOT NULL,
    dt_fim date,
    descricao text,
    versao integer DEFAULT 17
);


--
-- Name: explorador_atividade; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.explorador_atividade (
    id bigint NOT NULL,
    empresa_id integer NOT NULL,
    acao text NOT NULL,
    zip_id integer,
    nome_arquivo text,
    sha256 text,
    tamanho_bytes bigint,
    total_xmls integer,
    detalhe jsonb,
    criado_em timestamp without time zone DEFAULT now() NOT NULL,
    CONSTRAINT explorador_atividade_acao_check CHECK ((acao = ANY (ARRAY['upload'::text, 'exclusao'::text, 'extracao'::text, 'duplicado'::text])))
);


--
-- Name: explorador_atividade_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE IF NOT EXISTS public.explorador_atividade_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: explorador_atividade_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.explorador_atividade_id_seq OWNED BY public.explorador_atividade.id;


--
-- Name: explorador_eventos; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.explorador_eventos (
    id integer NOT NULL,
    importacao_id integer,
    tipo_evento character varying(10) NOT NULL,
    cpf character varying(11),
    per_apur character varying(7),
    nr_recibo character varying(40),
    id_evento character varying(80),
    dt_processamento timestamp with time zone,
    cd_resposta character varying(10),
    arquivo_origem character varying(120),
    dados_json jsonb,
    created_at timestamp with time zone DEFAULT now(),
    zip_id bigint,
    xml_entry_name text,
    referenciado_recibo character varying(40),
    retificado_por_id bigint,
    origem_envio_id bigint,
    xml_oid oid,
    xml_size_bytes bigint,
    xml_sha256 character(64)
);


--
-- Name: explorador_eventos_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE IF NOT EXISTS public.explorador_eventos_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: explorador_eventos_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.explorador_eventos_id_seq OWNED BY public.explorador_eventos.id;


--
-- Name: explorador_importacoes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.explorador_importacoes (
    id integer NOT NULL,
    pasta text NOT NULL,
    periodo character varying(7),
    total_arquivos integer DEFAULT 0,
    importado_em timestamp with time zone DEFAULT now()
);


--
-- Name: explorador_importacoes_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE IF NOT EXISTS public.explorador_importacoes_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: explorador_importacoes_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.explorador_importacoes_id_seq OWNED BY public.explorador_importacoes.id;


--
-- Name: explorador_rubricas; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.explorador_rubricas (
    id integer NOT NULL,
    evento_id integer,
    cod_rubr character varying(30),
    ide_tab_rubr character varying(10),
    nat_rubr character varying(10),
    tp_rubr character varying(2),
    cod_inc_cp character varying(10),
    cod_inc_irrf character varying(10),
    cod_inc_fgts character varying(10),
    vr_rubr numeric(15,2),
    ind_ap_ir character varying(2)
);


--
-- Name: explorador_rubricas_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE IF NOT EXISTS public.explorador_rubricas_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: explorador_rubricas_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.explorador_rubricas_id_seq OWNED BY public.explorador_rubricas.id;


--
-- Name: master_atividades; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.master_atividades (
    id integer NOT NULL,
    usuario_id integer NOT NULL,
    username character varying(100) NOT NULL,
    metodo character varying(10) NOT NULL,
    rota character varying(500) NOT NULL,
    status_code integer,
    duracao_ms integer,
    ip character varying(50),
    user_agent character varying(500),
    empresa_id integer,
    body_resumo character varying(500),
    criado_em timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: master_atividades_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE IF NOT EXISTS public.master_atividades_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: master_atividades_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.master_atividades_id_seq OWNED BY public.master_atividades.id;


--
-- Name: master_empresas; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.master_empresas (
    id integer NOT NULL,
    nome character varying(255) NOT NULL,
    cnpj character varying(18),
    db_name character varying(100) NOT NULL,
    db_host character varying(255) DEFAULT 'localhost'::character varying,
    db_port integer DEFAULT 5432,
    ativo boolean DEFAULT true,
    criado_em timestamp with time zone DEFAULT now(),
    tipo_estado character varying(16) DEFAULT 'estado_1'::character varying NOT NULL,
    CONSTRAINT master_empresas_tipo_estado_chk CHECK (((tipo_estado)::text = ANY ((ARRAY['estado_1'::character varying, 'estado_2'::character varying])::text[])))
);


--
-- Name: master_empresas_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE IF NOT EXISTS public.master_empresas_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: master_empresas_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.master_empresas_id_seq OWNED BY public.master_empresas.id;


--
-- Name: master_naturezas_esocial; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.master_naturezas_esocial (
    id integer NOT NULL,
    codigo character varying(10) NOT NULL,
    nome character varying(500) NOT NULL,
    descricao text,
    data_inicio date,
    data_fim date,
    criado_em timestamp with time zone DEFAULT now()
);


--
-- Name: master_naturezas_esocial_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE IF NOT EXISTS public.master_naturezas_esocial_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: master_naturezas_esocial_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.master_naturezas_esocial_id_seq OWNED BY public.master_naturezas_esocial.id;


--
-- Name: master_perfis; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.master_perfis (
    id integer NOT NULL,
    email character varying(255) NOT NULL,
    nome character varying(255) NOT NULL,
    senha_hash text,
    role character varying(20) DEFAULT 'operador'::character varying,
    ativo boolean DEFAULT true,
    criado_em timestamp with time zone DEFAULT now(),
    atualizado_em timestamp with time zone DEFAULT now(),
    username character varying(100),
    CONSTRAINT master_perfis_role_check CHECK (((role)::text = ANY (ARRAY[('admin'::character varying)::text, ('operador'::character varying)::text])))
);


--
-- Name: master_perfis_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE IF NOT EXISTS public.master_perfis_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: master_perfis_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.master_perfis_id_seq OWNED BY public.master_perfis.id;


--
-- Name: master_usuario_empresa; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.master_usuario_empresa (
    id integer NOT NULL,
    usuario_id integer,
    empresa_id integer,
    role_emp character varying(20) DEFAULT 'operador'::character varying,
    criado_em timestamp with time zone DEFAULT now(),
    CONSTRAINT master_usuario_empresa_role_emp_check CHECK (((role_emp)::text = ANY (ARRAY[('admin'::character varying)::text, ('operador'::character varying)::text])))
);


--
-- Name: master_usuario_empresa_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE IF NOT EXISTS public.master_usuario_empresa_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: master_usuario_empresa_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.master_usuario_empresa_id_seq OWNED BY public.master_usuario_empresa.id;


--
-- Name: naturezas_esocial; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.naturezas_esocial (
    id integer NOT NULL,
    codigo character varying(10) NOT NULL,
    nome character varying(500) NOT NULL,
    descricao text,
    data_inicio date,
    data_fim date,
    criado_em timestamp with time zone DEFAULT now()
);


--
-- Name: naturezas_esocial_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE IF NOT EXISTS public.naturezas_esocial_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: naturezas_esocial_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.naturezas_esocial_id_seq OWNED BY public.naturezas_esocial.id;


--
-- Name: pipeline_audit; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.pipeline_audit (
    id integer NOT NULL,
    cpf character varying(11) NOT NULL,
    per_apur character varying(7) NOT NULL,
    tipo character varying(20) NOT NULL,
    dados jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: pipeline_audit_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE IF NOT EXISTS public.pipeline_audit_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: pipeline_audit_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.pipeline_audit_id_seq OWNED BY public.pipeline_audit.id;


--
-- Name: pipeline_correcao; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.pipeline_correcao (
    id integer NOT NULL,
    cpf character varying(11) NOT NULL,
    per_apur character varying(7) NOT NULL,
    ambiente character varying(2) DEFAULT '2'::character varying NOT NULL,
    status character varying(30) DEFAULT 'iniciado'::character varying NOT NULL,
    step_atual integer DEFAULT 0,
    s1010_protocolo character varying(100),
    s1010_nr_recibo character varying(100),
    s1298_protocolo character varying(100),
    s1298_nr_recibo character varying(100),
    s1200_protocolo character varying(100),
    s1200_nr_recibo character varying(100),
    s1210_protocolo character varying(100),
    s1210_nr_recibo character varying(100),
    s1299_protocolo character varying(100),
    s1299_nr_recibo character varying(100),
    steps_log jsonb DEFAULT '[]'::jsonb,
    erro text,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now()
);


--
-- Name: pipeline_correcao_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE IF NOT EXISTS public.pipeline_correcao_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: pipeline_correcao_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.pipeline_correcao_id_seq OWNED BY public.pipeline_correcao.id;


--
-- Name: pipeline_cpf_results; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.pipeline_cpf_results (
    id integer NOT NULL,
    run_id integer NOT NULL,
    cpf character varying(11) NOT NULL,
    status character varying(20) DEFAULT 'pendente'::character varying NOT NULL,
    nr_recibo_original character varying(100),
    nr_recibo_novo character varying(100),
    pagamentos jsonb,
    info_ir_cr jsonb,
    erro_descricao text,
    lote_num integer,
    processed_at timestamp with time zone
);


--
-- Name: pipeline_cpf_results_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE IF NOT EXISTS public.pipeline_cpf_results_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: pipeline_cpf_results_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.pipeline_cpf_results_id_seq OWNED BY public.pipeline_cpf_results.id;


--
-- Name: pipeline_runs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.pipeline_runs (
    id integer NOT NULL,
    per_apur character varying(7) NOT NULL,
    status character varying(20) DEFAULT 'preparando'::character varying NOT NULL,
    total_cpfs integer DEFAULT 0,
    cpfs_ok integer DEFAULT 0,
    cpfs_erro integer DEFAULT 0,
    cpfs_ignorados integer DEFAULT 0,
    s1298_done boolean DEFAULT false,
    s1298_recibo character varying(100),
    s1299_done boolean DEFAULT false,
    s1299_recibo character varying(100),
    lote_atual integer DEFAULT 0,
    total_lotes integer DEFAULT 0,
    started_at timestamp with time zone DEFAULT now(),
    finished_at timestamp with time zone,
    erro_fatal text
);


--
-- Name: pipeline_runs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE IF NOT EXISTS public.pipeline_runs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: pipeline_runs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.pipeline_runs_id_seq OWNED BY public.pipeline_runs.id;


--
-- Name: pipeline_snapshots; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.pipeline_snapshots (
    id integer NOT NULL,
    run_id integer,
    per_apur character varying(7) NOT NULL,
    tipo character varying(10) NOT NULL,
    cpf character varying(11) NOT NULL,
    dados_s5002 jsonb,
    nr_recibo_s5002 character varying(40),
    captured_at timestamp with time zone DEFAULT now()
);


--
-- Name: pipeline_snapshots_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE IF NOT EXISTS public.pipeline_snapshots_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: pipeline_snapshots_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.pipeline_snapshots_id_seq OWNED BY public.pipeline_snapshots.id;


--
-- Name: rubrica_corrections; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.rubrica_corrections (
    id integer NOT NULL,
    tabela_eb_id integer,
    cod_rubrica text NOT NULL,
    descricao text,
    inss_antes text,
    irrf_antes text,
    fgts_antes text,
    inss_correto text,
    irrf_correto text,
    fgts_correto text,
    status character varying(50) DEFAULT 'pendente'::character varying,
    corrigido_em timestamp with time zone,
    observacao text,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: rubrica_corrections_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE IF NOT EXISTS public.rubrica_corrections_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: rubrica_corrections_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.rubrica_corrections_id_seq OWNED BY public.rubrica_corrections.id;


--
-- Name: s1210_cpf_blocklist; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.s1210_cpf_blocklist (
    id bigint NOT NULL,
    empresa_id integer NOT NULL,
    cpf character varying(11) NOT NULL,
    per_apur character varying(7),
    lote_num integer,
    motivo text,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: s1210_cpf_blocklist_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE IF NOT EXISTS public.s1210_cpf_blocklist_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: s1210_cpf_blocklist_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.s1210_cpf_blocklist_id_seq OWNED BY public.s1210_cpf_blocklist.id;


--
-- Name: s1210_cpf_envios; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.s1210_cpf_envios (
    id bigint NOT NULL,
    empresa_id integer NOT NULL,
    per_apur character varying(7) NOT NULL,
    cpf character(11) NOT NULL,
    lote_num smallint NOT NULL,
    status character varying(20) NOT NULL,
    nr_recibo_usado character varying(50),
    nr_recibo_novo character varying(50),
    protocolo character varying(100),
    codigo_resposta character varying(10),
    descricao_resposta text,
    erro_descricao text,
    xml_enviado text,
    xml_resposta text,
    pagamentos jsonb,
    info_ir jsonb,
    enviado_por integer,
    enviado_em timestamp with time zone DEFAULT now() NOT NULL,
    duracao_ms integer,
    CONSTRAINT s1210_cpf_envios_lote_num_check CHECK (((lote_num >= 1) AND (lote_num <= 4)))
);


--
-- Name: s1210_cpf_envios_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE IF NOT EXISTS public.s1210_cpf_envios_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: s1210_cpf_envios_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.s1210_cpf_envios_id_seq OWNED BY public.s1210_cpf_envios.id;


--
-- Name: s1210_cpf_recibo; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.s1210_cpf_recibo (
    id bigint NOT NULL,
    empresa_id integer NOT NULL,
    per_apur character varying(7) NOT NULL,
    cpf character(11) NOT NULL,
    nr_recibo_zip character varying(50),
    nr_recibo_usado character varying(50),
    nr_recibo_esocial character varying(50),
    ide_dm_dev character varying(100),
    dh_processamento_zip timestamp with time zone,
    fonte character varying(30) DEFAULT 'zip'::character varying NOT NULL,
    atualizado_em timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: s1210_cpf_recibo_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE IF NOT EXISTS public.s1210_cpf_recibo_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: s1210_cpf_recibo_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.s1210_cpf_recibo_id_seq OWNED BY public.s1210_cpf_recibo.id;


--
-- Name: s1210_cpf_scope; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.s1210_cpf_scope (
    id bigint NOT NULL,
    xlsx_id bigint NOT NULL,
    empresa_id integer NOT NULL,
    per_apur character varying(7) NOT NULL,
    cpf character(11) NOT NULL,
    nome character varying(255),
    matricula character varying(50),
    lote_num smallint NOT NULL,
    row_number integer,
    raw_row jsonb,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT s1210_cpf_scope_lote_num_check CHECK (((lote_num >= 1) AND (lote_num <= 4)))
);


--
-- Name: s1210_cpf_scope_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE IF NOT EXISTS public.s1210_cpf_scope_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: s1210_cpf_scope_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.s1210_cpf_scope_id_seq OWNED BY public.s1210_cpf_scope.id;


--
-- Name: s1210_lote1_codfunc_scope; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.s1210_lote1_codfunc_scope (
    id bigint NOT NULL,
    empresa_id integer NOT NULL,
    per_apur character varying(7) NOT NULL,
    codigo_empresa character varying(32),
    codigo_lote character varying(64),
    codigo_filial character varying(64),
    codigo_funcionario character varying(64) NOT NULL,
    concatenar character varying(128),
    lote_label character varying(64),
    source_filename character varying(255),
    source_sha256 character varying(64),
    created_at timestamp with time zone DEFAULT now(),
    cpf character varying(11)
);


--
-- Name: s1210_lote1_codfunc_scope_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE IF NOT EXISTS public.s1210_lote1_codfunc_scope_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: s1210_lote1_codfunc_scope_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.s1210_lote1_codfunc_scope_id_seq OWNED BY public.s1210_lote1_codfunc_scope.id;


--
-- Name: s1210_operadoras; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.s1210_operadoras (
    id bigint NOT NULL,
    xlsx_id bigint,
    empresa_id integer NOT NULL,
    per_apur character varying(7) NOT NULL,
    cpf character(11) NOT NULL,
    rubrica_origem character varying(10) NOT NULL,
    cnpj_operadora character varying(14),
    reg_ans character varying(20),
    nome_operadora character varying(255),
    valor numeric(18,2),
    raw_row jsonb,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    lote_num integer
);


--
-- Name: s1210_operadoras_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE IF NOT EXISTS public.s1210_operadoras_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: s1210_operadoras_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.s1210_operadoras_id_seq OWNED BY public.s1210_operadoras.id;


--
-- Name: s1210_xlsx; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.s1210_xlsx (
    id bigint NOT NULL,
    empresa_id integer NOT NULL,
    per_apur character varying(7) NOT NULL,
    nome_arquivo character varying(255) NOT NULL,
    tamanho_bytes bigint NOT NULL,
    sha256 character(64) NOT NULL,
    storage_path text NOT NULL,
    aba_geral character varying(100) NOT NULL,
    aba_operadoras character varying(100),
    uploaded_at timestamp with time zone DEFAULT now() NOT NULL,
    uploaded_by integer,
    parse_ok boolean DEFAULT false NOT NULL,
    parse_erro text,
    totais_json jsonb
);


--
-- Name: s1210_xlsx_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE IF NOT EXISTS public.s1210_xlsx_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: s1210_xlsx_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.s1210_xlsx_id_seq OWNED BY public.s1210_xlsx.id;


--
-- Name: senha_certificado_salva; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.senha_certificado_salva (
    id integer NOT NULL,
    senha_encrypted text NOT NULL,
    saved_at timestamp without time zone DEFAULT now(),
    expires_at timestamp without time zone NOT NULL
);


--
-- Name: senha_certificado_salva_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE IF NOT EXISTS public.senha_certificado_salva_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: senha_certificado_salva_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.senha_certificado_salva_id_seq OWNED BY public.senha_certificado_salva.id;


--
-- Name: tabela3_esocial_oficial; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.tabela3_esocial_oficial (
    id integer NOT NULL,
    row_number integer,
    col_a text,
    col_b text,
    col_c text,
    col_d text,
    col_e text,
    col_f text,
    raw_data jsonb,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: tabela3_esocial_oficial_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE IF NOT EXISTS public.tabela3_esocial_oficial_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: tabela3_esocial_oficial_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.tabela3_esocial_oficial_id_seq OWNED BY public.tabela3_esocial_oficial.id;


--
-- Name: tabela_marcos; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.tabela_marcos (
    id integer NOT NULL,
    codigo text,
    prioridade_calculo text,
    descricao text,
    tipo_rb text,
    tipo text,
    tipo_lancamento text,
    tipo_evento text,
    inss_flag text,
    irrf_flag text,
    fgts_flag text,
    nat_rb text,
    descr_nat_rub text,
    cod_natureza text,
    descr_natureza_esocial text,
    incid_inss text,
    cod_inss text,
    incid_inss_esocial text,
    inss_tipo_processo text,
    inss_nro_processo text,
    incid_irrf text,
    cod_irrf text,
    incid_irrf_esocial text,
    irrf_nro_processo text,
    incid_fgts text,
    cod_fgts text,
    incid_fgts_esocial text,
    fgts_nro_processo text,
    cod_pis_pasep text,
    incid_pis_esocial text,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: tabela_marcos_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE IF NOT EXISTS public.tabela_marcos_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: tabela_marcos_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.tabela_marcos_id_seq OWNED BY public.tabela_marcos.id;


--
-- Name: timeline_envio; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.timeline_envio (
    id bigint NOT NULL,
    timeline_mes_id bigint NOT NULL,
    sequencia integer NOT NULL,
    tipo character varying(20) NOT NULL,
    iniciado_em timestamp without time zone DEFAULT now() NOT NULL,
    finalizado_em timestamp without time zone,
    status character varying(16) DEFAULT 'concluido'::character varying NOT NULL,
    total_tentados integer DEFAULT 0 NOT NULL,
    total_sucesso integer DEFAULT 0 NOT NULL,
    total_erro integer DEFAULT 0 NOT NULL,
    resumo jsonb,
    CONSTRAINT timeline_envio_status_chk CHECK (((status)::text = ANY ((ARRAY['em_andamento'::character varying, 'concluido'::character varying, 'falhou'::character varying])::text[]))),
    CONSTRAINT timeline_envio_tipo_chk CHECK (((tipo)::text = ANY ((ARRAY['zip_inicial'::character varying, 'envio_massa'::character varying, 'envio_individual'::character varying])::text[])))
);


--
-- Name: timeline_envio_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE IF NOT EXISTS public.timeline_envio_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: timeline_envio_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.timeline_envio_id_seq OWNED BY public.timeline_envio.id;


--
-- Name: timeline_envio_item; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.timeline_envio_item (
    id bigint NOT NULL,
    timeline_envio_id bigint NOT NULL,
    cpf character varying(14) NOT NULL,
    tipo_evento character varying(8) DEFAULT 'S-1210'::character varying NOT NULL,
    status character varying(24) NOT NULL,
    versao_anterior_id bigint,
    versao_nova_id bigint,
    nr_recibo_anterior character varying(40),
    nr_recibo_novo character varying(40),
    xml_enviado_oid oid,
    xml_retorno_oid oid,
    erro_codigo character varying(20),
    erro_mensagem text,
    duracao_ms integer,
    criado_em timestamp without time zone DEFAULT now() NOT NULL,
    CONSTRAINT timeline_envio_item_status_check CHECK (((status)::text = ANY ((ARRAY['sucesso'::character varying, 'erro_esocial'::character varying, 'rejeitado_local'::character varying, 'falha_rede'::character varying, 'pendente'::character varying, 'pendente_consulta'::character varying, 'erro_preparo'::character varying, 'sem_mudanca'::character varying])::text[])))
);


--
-- Name: timeline_envio_item_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE IF NOT EXISTS public.timeline_envio_item_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: timeline_envio_item_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.timeline_envio_item_id_seq OWNED BY public.timeline_envio_item.id;


--
-- Name: timeline_mes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE IF NOT EXISTS public.timeline_mes (
    id bigint NOT NULL,
    empresa_id bigint NOT NULL,
    per_apur character varying(7) NOT NULL,
    head_envio_id bigint,
    criado_em timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: timeline_mes_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE IF NOT EXISTS public.timeline_mes_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: timeline_mes_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.timeline_mes_id_seq OWNED BY public.timeline_mes.id;


--
-- Name: auditoria_naturezas id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auditoria_naturezas ALTER COLUMN id SET DEFAULT nextval('public.auditoria_naturezas_id_seq'::regclass);


--
-- Name: certificados_a1 id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.certificados_a1 ALTER COLUMN id SET DEFAULT nextval('public.certificados_a1_id_seq'::regclass);


--
-- Name: config_esocial id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.config_esocial ALTER COLUMN id SET DEFAULT nextval('public.config_esocial_id_seq'::regclass);


--
-- Name: correcoes_staging id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.correcoes_staging ALTER COLUMN id SET DEFAULT nextval('public.correcoes_staging_id_seq'::regclass);


--
-- Name: empresa_zips_brutos id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.empresa_zips_brutos ALTER COLUMN id SET DEFAULT nextval('public.empresa_zips_brutos_id_seq'::regclass);


--
-- Name: esocial_depara id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.esocial_depara ALTER COLUMN id SET DEFAULT nextval('public.esocial_depara_id_seq'::regclass);


--
-- Name: esocial_envios id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.esocial_envios ALTER COLUMN id SET DEFAULT nextval('public.esocial_envios_id_seq'::regclass);


--
-- Name: explorador_atividade id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.explorador_atividade ALTER COLUMN id SET DEFAULT nextval('public.explorador_atividade_id_seq'::regclass);


--
-- Name: explorador_eventos id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.explorador_eventos ALTER COLUMN id SET DEFAULT nextval('public.explorador_eventos_id_seq'::regclass);


--
-- Name: explorador_importacoes id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.explorador_importacoes ALTER COLUMN id SET DEFAULT nextval('public.explorador_importacoes_id_seq'::regclass);


--
-- Name: explorador_rubricas id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.explorador_rubricas ALTER COLUMN id SET DEFAULT nextval('public.explorador_rubricas_id_seq'::regclass);


--
-- Name: master_atividades id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.master_atividades ALTER COLUMN id SET DEFAULT nextval('public.master_atividades_id_seq'::regclass);


--
-- Name: master_empresas id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.master_empresas ALTER COLUMN id SET DEFAULT nextval('public.master_empresas_id_seq'::regclass);


--
-- Name: master_naturezas_esocial id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.master_naturezas_esocial ALTER COLUMN id SET DEFAULT nextval('public.master_naturezas_esocial_id_seq'::regclass);


--
-- Name: master_perfis id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.master_perfis ALTER COLUMN id SET DEFAULT nextval('public.master_perfis_id_seq'::regclass);


--
-- Name: master_usuario_empresa id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.master_usuario_empresa ALTER COLUMN id SET DEFAULT nextval('public.master_usuario_empresa_id_seq'::regclass);


--
-- Name: naturezas_esocial id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.naturezas_esocial ALTER COLUMN id SET DEFAULT nextval('public.naturezas_esocial_id_seq'::regclass);


--
-- Name: pipeline_audit id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pipeline_audit ALTER COLUMN id SET DEFAULT nextval('public.pipeline_audit_id_seq'::regclass);


--
-- Name: pipeline_correcao id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pipeline_correcao ALTER COLUMN id SET DEFAULT nextval('public.pipeline_correcao_id_seq'::regclass);


--
-- Name: pipeline_cpf_results id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pipeline_cpf_results ALTER COLUMN id SET DEFAULT nextval('public.pipeline_cpf_results_id_seq'::regclass);


--
-- Name: pipeline_runs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pipeline_runs ALTER COLUMN id SET DEFAULT nextval('public.pipeline_runs_id_seq'::regclass);


--
-- Name: pipeline_snapshots id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pipeline_snapshots ALTER COLUMN id SET DEFAULT nextval('public.pipeline_snapshots_id_seq'::regclass);


--
-- Name: rubrica_corrections id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rubrica_corrections ALTER COLUMN id SET DEFAULT nextval('public.rubrica_corrections_id_seq'::regclass);


--
-- Name: s1210_cpf_blocklist id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.s1210_cpf_blocklist ALTER COLUMN id SET DEFAULT nextval('public.s1210_cpf_blocklist_id_seq'::regclass);


--
-- Name: s1210_cpf_envios id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.s1210_cpf_envios ALTER COLUMN id SET DEFAULT nextval('public.s1210_cpf_envios_id_seq'::regclass);


--
-- Name: s1210_cpf_recibo id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.s1210_cpf_recibo ALTER COLUMN id SET DEFAULT nextval('public.s1210_cpf_recibo_id_seq'::regclass);


--
-- Name: s1210_cpf_scope id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.s1210_cpf_scope ALTER COLUMN id SET DEFAULT nextval('public.s1210_cpf_scope_id_seq'::regclass);


--
-- Name: s1210_lote1_codfunc_scope id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.s1210_lote1_codfunc_scope ALTER COLUMN id SET DEFAULT nextval('public.s1210_lote1_codfunc_scope_id_seq'::regclass);


--
-- Name: s1210_operadoras id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.s1210_operadoras ALTER COLUMN id SET DEFAULT nextval('public.s1210_operadoras_id_seq'::regclass);


--
-- Name: s1210_xlsx id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.s1210_xlsx ALTER COLUMN id SET DEFAULT nextval('public.s1210_xlsx_id_seq'::regclass);


--
-- Name: senha_certificado_salva id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.senha_certificado_salva ALTER COLUMN id SET DEFAULT nextval('public.senha_certificado_salva_id_seq'::regclass);


--
-- Name: tabela3_esocial_oficial id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tabela3_esocial_oficial ALTER COLUMN id SET DEFAULT nextval('public.tabela3_esocial_oficial_id_seq'::regclass);


--
-- Name: tabela_marcos id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tabela_marcos ALTER COLUMN id SET DEFAULT nextval('public.tabela_marcos_id_seq'::regclass);


--
-- Name: timeline_envio id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.timeline_envio ALTER COLUMN id SET DEFAULT nextval('public.timeline_envio_id_seq'::regclass);


--
-- Name: timeline_envio_item id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.timeline_envio_item ALTER COLUMN id SET DEFAULT nextval('public.timeline_envio_item_id_seq'::regclass);


--
-- Name: timeline_mes id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.timeline_mes ALTER COLUMN id SET DEFAULT nextval('public.timeline_mes_id_seq'::regclass);


--
-- Name: auditoria_naturezas auditoria_naturezas_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auditoria_naturezas
    ADD CONSTRAINT auditoria_naturezas_pkey PRIMARY KEY (id);


--
-- Name: certificados_a1 certificados_a1_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.certificados_a1
    ADD CONSTRAINT certificados_a1_pkey PRIMARY KEY (id);


--
-- Name: config_esocial config_esocial_cnpj_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.config_esocial
    ADD CONSTRAINT config_esocial_cnpj_key UNIQUE (cnpj);


--
-- Name: config_esocial config_esocial_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.config_esocial
    ADD CONSTRAINT config_esocial_pkey PRIMARY KEY (id);


--
-- Name: correcoes_staging correcoes_staging_analise_natureza_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.correcoes_staging
    ADD CONSTRAINT correcoes_staging_analise_natureza_id_key UNIQUE (analise_natureza_id);


--
-- Name: correcoes_staging correcoes_staging_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.correcoes_staging
    ADD CONSTRAINT correcoes_staging_pkey PRIMARY KEY (id);


--
-- Name: empresa_zips_brutos empresa_zips_brutos_dedup_uq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.empresa_zips_brutos
    ADD CONSTRAINT empresa_zips_brutos_dedup_uq UNIQUE (empresa_id, sha256);


--
-- Name: empresa_zips_brutos empresa_zips_brutos_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.empresa_zips_brutos
    ADD CONSTRAINT empresa_zips_brutos_pkey PRIMARY KEY (id);


--
-- Name: esocial_depara esocial_depara_cod_rubrica_campo_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.esocial_depara
    ADD CONSTRAINT esocial_depara_cod_rubrica_campo_key UNIQUE (cod_rubrica, campo);


--
-- Name: esocial_depara esocial_depara_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.esocial_depara
    ADD CONSTRAINT esocial_depara_pkey PRIMARY KEY (id);


--
-- Name: esocial_envios esocial_envios_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.esocial_envios
    ADD CONSTRAINT esocial_envios_pkey PRIMARY KEY (id);


--
-- Name: esocial_tabela3_natureza esocial_tabela3_natureza_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.esocial_tabela3_natureza
    ADD CONSTRAINT esocial_tabela3_natureza_pkey PRIMARY KEY (codigo);


--
-- Name: explorador_atividade explorador_atividade_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.explorador_atividade
    ADD CONSTRAINT explorador_atividade_pkey PRIMARY KEY (id);


--
-- Name: explorador_eventos explorador_eventos_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.explorador_eventos
    ADD CONSTRAINT explorador_eventos_pkey PRIMARY KEY (id);


--
-- Name: explorador_importacoes explorador_importacoes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.explorador_importacoes
    ADD CONSTRAINT explorador_importacoes_pkey PRIMARY KEY (id);


--
-- Name: explorador_rubricas explorador_rubricas_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.explorador_rubricas
    ADD CONSTRAINT explorador_rubricas_pkey PRIMARY KEY (id);


--
-- Name: master_atividades master_atividades_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.master_atividades
    ADD CONSTRAINT master_atividades_pkey PRIMARY KEY (id);


--
-- Name: master_empresas master_empresas_cnpj_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.master_empresas
    ADD CONSTRAINT master_empresas_cnpj_key UNIQUE (cnpj);


--
-- Name: master_empresas master_empresas_db_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.master_empresas
    ADD CONSTRAINT master_empresas_db_name_key UNIQUE (db_name);


--
-- Name: master_empresas master_empresas_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.master_empresas
    ADD CONSTRAINT master_empresas_pkey PRIMARY KEY (id);


--
-- Name: master_naturezas_esocial master_naturezas_esocial_codigo_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.master_naturezas_esocial
    ADD CONSTRAINT master_naturezas_esocial_codigo_key UNIQUE (codigo);


--
-- Name: master_naturezas_esocial master_naturezas_esocial_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.master_naturezas_esocial
    ADD CONSTRAINT master_naturezas_esocial_pkey PRIMARY KEY (id);


--
-- Name: master_perfis master_perfis_email_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.master_perfis
    ADD CONSTRAINT master_perfis_email_key UNIQUE (email);


--
-- Name: master_perfis master_perfis_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.master_perfis
    ADD CONSTRAINT master_perfis_pkey PRIMARY KEY (id);


--
-- Name: master_perfis master_perfis_username_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.master_perfis
    ADD CONSTRAINT master_perfis_username_key UNIQUE (username);


--
-- Name: master_usuario_empresa master_usuario_empresa_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.master_usuario_empresa
    ADD CONSTRAINT master_usuario_empresa_pkey PRIMARY KEY (id);


--
-- Name: master_usuario_empresa master_usuario_empresa_usuario_id_empresa_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.master_usuario_empresa
    ADD CONSTRAINT master_usuario_empresa_usuario_id_empresa_id_key UNIQUE (usuario_id, empresa_id);


--
-- Name: naturezas_esocial naturezas_esocial_codigo_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.naturezas_esocial
    ADD CONSTRAINT naturezas_esocial_codigo_key UNIQUE (codigo);


--
-- Name: naturezas_esocial naturezas_esocial_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.naturezas_esocial
    ADD CONSTRAINT naturezas_esocial_pkey PRIMARY KEY (id);


--
-- Name: pipeline_audit pipeline_audit_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pipeline_audit
    ADD CONSTRAINT pipeline_audit_pkey PRIMARY KEY (id);


--
-- Name: pipeline_correcao pipeline_correcao_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pipeline_correcao
    ADD CONSTRAINT pipeline_correcao_pkey PRIMARY KEY (id);


--
-- Name: pipeline_cpf_results pipeline_cpf_results_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pipeline_cpf_results
    ADD CONSTRAINT pipeline_cpf_results_pkey PRIMARY KEY (id);


--
-- Name: pipeline_runs pipeline_runs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pipeline_runs
    ADD CONSTRAINT pipeline_runs_pkey PRIMARY KEY (id);


--
-- Name: pipeline_snapshots pipeline_snapshots_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pipeline_snapshots
    ADD CONSTRAINT pipeline_snapshots_pkey PRIMARY KEY (id);


--
-- Name: rubrica_corrections rubrica_corrections_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rubrica_corrections
    ADD CONSTRAINT rubrica_corrections_pkey PRIMARY KEY (id);


--
-- Name: s1210_cpf_blocklist s1210_cpf_blocklist_empresa_id_cpf_per_apur_lote_num_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.s1210_cpf_blocklist
    ADD CONSTRAINT s1210_cpf_blocklist_empresa_id_cpf_per_apur_lote_num_key UNIQUE (empresa_id, cpf, per_apur, lote_num);


--
-- Name: s1210_cpf_blocklist s1210_cpf_blocklist_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.s1210_cpf_blocklist
    ADD CONSTRAINT s1210_cpf_blocklist_pkey PRIMARY KEY (id);


--
-- Name: s1210_cpf_envios s1210_cpf_envios_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.s1210_cpf_envios
    ADD CONSTRAINT s1210_cpf_envios_pkey PRIMARY KEY (id);


--
-- Name: s1210_cpf_recibo s1210_cpf_recibo_empresa_id_per_apur_cpf_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.s1210_cpf_recibo
    ADD CONSTRAINT s1210_cpf_recibo_empresa_id_per_apur_cpf_key UNIQUE (empresa_id, per_apur, cpf);


--
-- Name: s1210_cpf_recibo s1210_cpf_recibo_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.s1210_cpf_recibo
    ADD CONSTRAINT s1210_cpf_recibo_pkey PRIMARY KEY (id);


--
-- Name: s1210_cpf_scope s1210_cpf_scope_empresa_id_per_apur_cpf_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.s1210_cpf_scope
    ADD CONSTRAINT s1210_cpf_scope_empresa_id_per_apur_cpf_key UNIQUE (empresa_id, per_apur, cpf);


--
-- Name: s1210_cpf_scope s1210_cpf_scope_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.s1210_cpf_scope
    ADD CONSTRAINT s1210_cpf_scope_pkey PRIMARY KEY (id);


--
-- Name: s1210_lote1_codfunc_scope s1210_lote1_codfunc_scope_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.s1210_lote1_codfunc_scope
    ADD CONSTRAINT s1210_lote1_codfunc_scope_pkey PRIMARY KEY (id);


--
-- Name: s1210_operadoras s1210_operadoras_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.s1210_operadoras
    ADD CONSTRAINT s1210_operadoras_pkey PRIMARY KEY (id);


--
-- Name: s1210_xlsx s1210_xlsx_empresa_id_per_apur_sha256_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.s1210_xlsx
    ADD CONSTRAINT s1210_xlsx_empresa_id_per_apur_sha256_key UNIQUE (empresa_id, per_apur, sha256);


--
-- Name: s1210_xlsx s1210_xlsx_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.s1210_xlsx
    ADD CONSTRAINT s1210_xlsx_pkey PRIMARY KEY (id);


--
-- Name: senha_certificado_salva senha_certificado_salva_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.senha_certificado_salva
    ADD CONSTRAINT senha_certificado_salva_pkey PRIMARY KEY (id);


--
-- Name: tabela3_esocial_oficial tabela3_esocial_oficial_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tabela3_esocial_oficial
    ADD CONSTRAINT tabela3_esocial_oficial_pkey PRIMARY KEY (id);


--
-- Name: tabela_marcos tabela_marcos_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tabela_marcos
    ADD CONSTRAINT tabela_marcos_pkey PRIMARY KEY (id);


--
-- Name: timeline_envio_item timeline_envio_item_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.timeline_envio_item
    ADD CONSTRAINT timeline_envio_item_pkey PRIMARY KEY (id);


--
-- Name: timeline_envio timeline_envio_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.timeline_envio
    ADD CONSTRAINT timeline_envio_pkey PRIMARY KEY (id);


--
-- Name: timeline_envio timeline_envio_seq_uq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.timeline_envio
    ADD CONSTRAINT timeline_envio_seq_uq UNIQUE (timeline_mes_id, sequencia);


--
-- Name: timeline_mes timeline_mes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.timeline_mes
    ADD CONSTRAINT timeline_mes_pkey PRIMARY KEY (id);


--
-- Name: timeline_mes timeline_mes_uq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.timeline_mes
    ADD CONSTRAINT timeline_mes_uq UNIQUE (empresa_id, per_apur);


--
-- Name: idx_atividades_criado; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_atividades_criado ON public.master_atividades USING btree (criado_em);


--
-- Name: idx_atividades_rota; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_atividades_rota ON public.master_atividades USING btree (rota);


--
-- Name: idx_atividades_usuario; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_atividades_usuario ON public.master_atividades USING btree (usuario_id);


--
-- Name: idx_auditoria_naturezas_an; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_auditoria_naturezas_an ON public.auditoria_naturezas USING btree (analise_natureza_id);


--
-- Name: idx_expl_eventos_cpf; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_expl_eventos_cpf ON public.explorador_eventos USING btree (cpf);


--
-- Name: idx_expl_eventos_per; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_expl_eventos_per ON public.explorador_eventos USING btree (per_apur);


--
-- Name: idx_expl_eventos_recibo; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_expl_eventos_recibo ON public.explorador_eventos USING btree (nr_recibo);


--
-- Name: idx_expl_eventos_tipo; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_expl_eventos_tipo ON public.explorador_eventos USING btree (tipo_evento);


--
-- Name: idx_expl_rubricas_cod; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_expl_rubricas_cod ON public.explorador_rubricas USING btree (cod_rubr);


--
-- Name: idx_expl_rubricas_evt; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_expl_rubricas_evt ON public.explorador_rubricas USING btree (evento_id);


--
-- Name: idx_expl_rubricas_irrf; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_expl_rubricas_irrf ON public.explorador_rubricas USING btree (cod_inc_irrf);


--
-- Name: idx_explorador_atividade_emp_dt; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_explorador_atividade_emp_dt ON public.explorador_atividade USING btree (empresa_id, criado_em DESC);


--
-- Name: idx_naturezas_codigo; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_naturezas_codigo ON public.naturezas_esocial USING btree (codigo);


--
-- Name: idx_pcr_cpf; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_pcr_cpf ON public.pipeline_cpf_results USING btree (cpf);


--
-- Name: idx_pcr_run_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_pcr_run_id ON public.pipeline_cpf_results USING btree (run_id);


--
-- Name: idx_pcr_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_pcr_status ON public.pipeline_cpf_results USING btree (status);


--
-- Name: idx_rubrica_corrections_eb; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_rubrica_corrections_eb ON public.rubrica_corrections USING btree (tabela_eb_id);


--
-- Name: idx_rubrica_corrections_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_rubrica_corrections_status ON public.rubrica_corrections USING btree (status);


--
-- Name: idx_s1210_lote1_codfunc_scope_per; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_s1210_lote1_codfunc_scope_per ON public.s1210_lote1_codfunc_scope USING btree (empresa_id, per_apur);


--
-- Name: idx_s1210_operadoras_lookup; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_s1210_operadoras_lookup ON public.s1210_operadoras USING btree (empresa_id, per_apur, cpf);


--
-- Name: idx_s1210_operadoras_lote; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_s1210_operadoras_lote ON public.s1210_operadoras USING btree (empresa_id, per_apur, lote_num);


--
-- Name: idx_snapshots_cpf_per; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_snapshots_cpf_per ON public.pipeline_snapshots USING btree (cpf, per_apur, tipo);


--
-- Name: idx_snapshots_run_tipo; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS idx_snapshots_run_tipo ON public.pipeline_snapshots USING btree (run_id, tipo);


--
-- Name: ix_evt_cadeia_s1210; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS ix_evt_cadeia_s1210 ON public.explorador_eventos USING btree (cpf, per_apur, tipo_evento) WHERE ((tipo_evento)::text = 'S-1210'::text);


--
-- Name: ix_evt_cpf_per; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS ix_evt_cpf_per ON public.explorador_eventos USING btree (cpf, per_apur);


--
-- Name: ix_evt_head_s1210; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS ix_evt_head_s1210 ON public.explorador_eventos USING btree (cpf, per_apur) WHERE (((tipo_evento)::text = 'S-1210'::text) AND (retificado_por_id IS NULL));


--
-- Name: ix_evt_origem_envio; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS ix_evt_origem_envio ON public.explorador_eventos USING btree (origem_envio_id);


--
-- Name: ix_evt_recibo; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS ix_evt_recibo ON public.explorador_eventos USING btree (nr_recibo);


--
-- Name: ix_evt_ref; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS ix_evt_ref ON public.explorador_eventos USING btree (referenciado_recibo);


--
-- Name: ix_evt_xml_oid_pendente; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS ix_evt_xml_oid_pendente ON public.explorador_eventos USING btree (id) WHERE (xml_oid IS NULL);


--
-- Name: ix_evt_zip; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS ix_evt_zip ON public.explorador_eventos USING btree (zip_id);


--
-- Name: ix_s1210_envios_cpf; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS ix_s1210_envios_cpf ON public.s1210_cpf_envios USING btree (empresa_id, per_apur, cpf);


--
-- Name: ix_s1210_envios_enviado_em; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS ix_s1210_envios_enviado_em ON public.s1210_cpf_envios USING btree (enviado_em DESC);


--
-- Name: ix_s1210_envios_latest_lote; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS ix_s1210_envios_latest_lote ON public.s1210_cpf_envios USING btree (empresa_id, per_apur, lote_num, cpf, enviado_em DESC NULLS LAST, id DESC) INCLUDE (status);


--
-- Name: ix_s1210_envios_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS ix_s1210_envios_status ON public.s1210_cpf_envios USING btree (empresa_id, per_apur, lote_num, status);


--
-- Name: ix_s1210_operadoras_key; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS ix_s1210_operadoras_key ON public.s1210_operadoras USING btree (empresa_id, per_apur, cpf);


--
-- Name: ix_s1210_recibo_empresa_per; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS ix_s1210_recibo_empresa_per ON public.s1210_cpf_recibo USING btree (empresa_id, per_apur);


--
-- Name: ix_s1210_scope_contadores; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS ix_s1210_scope_contadores ON public.s1210_cpf_scope USING btree (empresa_id, per_apur, lote_num, cpf);


--
-- Name: ix_s1210_scope_cpf; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS ix_s1210_scope_cpf ON public.s1210_cpf_scope USING btree (cpf);


--
-- Name: ix_s1210_scope_empresa_per_lote; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS ix_s1210_scope_empresa_per_lote ON public.s1210_cpf_scope USING btree (empresa_id, per_apur, lote_num);


--
-- Name: ix_s1210_xlsx_empresa_per; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS ix_s1210_xlsx_empresa_per ON public.s1210_xlsx USING btree (empresa_id, per_apur);


--
-- Name: ix_timeline_envio_mes; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS ix_timeline_envio_mes ON public.timeline_envio USING btree (timeline_mes_id, sequencia);


--
-- Name: ix_timeline_item_cpf; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS ix_timeline_item_cpf ON public.timeline_envio_item USING btree (cpf, tipo_evento);


--
-- Name: ix_timeline_item_envio; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS ix_timeline_item_envio ON public.timeline_envio_item USING btree (timeline_envio_id);


--
-- Name: ix_timeline_mes_emp; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS ix_timeline_mes_emp ON public.timeline_mes USING btree (empresa_id, per_apur DESC);


--
-- Name: ix_zips_periodo; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS ix_zips_periodo ON public.empresa_zips_brutos USING btree (empresa_id, dt_ini, dt_fim);


--
-- Name: ix_zips_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX IF NOT EXISTS ix_zips_status ON public.empresa_zips_brutos USING btree (extracao_status);


--
-- Name: ux_explorador_eventos_id_evento; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX IF NOT EXISTS ux_explorador_eventos_id_evento ON public.explorador_eventos USING btree (id_evento) WHERE (id_evento IS NOT NULL);


-- (FK removidos: analise_natureza eh tabela V1-legacy nao incluida no schema empresa V2)


--
-- Name: empresa_zips_brutos empresa_zips_brutos_empresa_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.empresa_zips_brutos
    ADD CONSTRAINT empresa_zips_brutos_empresa_id_fkey FOREIGN KEY (empresa_id) REFERENCES public.master_empresas(id);


--
-- Name: explorador_eventos explorador_eventos_importacao_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.explorador_eventos
    ADD CONSTRAINT explorador_eventos_importacao_id_fkey FOREIGN KEY (importacao_id) REFERENCES public.explorador_importacoes(id) ON DELETE CASCADE;


--
-- Name: explorador_eventos explorador_eventos_origem_envio_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.explorador_eventos
    ADD CONSTRAINT explorador_eventos_origem_envio_fk FOREIGN KEY (origem_envio_id) REFERENCES public.timeline_envio(id) ON DELETE SET NULL;


--
-- Name: explorador_eventos explorador_eventos_retif_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.explorador_eventos
    ADD CONSTRAINT explorador_eventos_retif_fk FOREIGN KEY (retificado_por_id) REFERENCES public.explorador_eventos(id) ON DELETE SET NULL;


--
-- Name: explorador_eventos explorador_eventos_zip_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.explorador_eventos
    ADD CONSTRAINT explorador_eventos_zip_id_fkey FOREIGN KEY (zip_id) REFERENCES public.empresa_zips_brutos(id) ON DELETE CASCADE;


--
-- Name: explorador_rubricas explorador_rubricas_evento_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.explorador_rubricas
    ADD CONSTRAINT explorador_rubricas_evento_id_fkey FOREIGN KEY (evento_id) REFERENCES public.explorador_eventos(id) ON DELETE CASCADE;


--
-- Name: master_usuario_empresa master_usuario_empresa_empresa_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.master_usuario_empresa
    ADD CONSTRAINT master_usuario_empresa_empresa_id_fkey FOREIGN KEY (empresa_id) REFERENCES public.master_empresas(id) ON DELETE CASCADE;


--
-- Name: master_usuario_empresa master_usuario_empresa_usuario_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.master_usuario_empresa
    ADD CONSTRAINT master_usuario_empresa_usuario_id_fkey FOREIGN KEY (usuario_id) REFERENCES public.master_perfis(id) ON DELETE CASCADE;


--
-- Name: pipeline_cpf_results pipeline_cpf_results_run_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pipeline_cpf_results
    ADD CONSTRAINT pipeline_cpf_results_run_id_fkey FOREIGN KEY (run_id) REFERENCES public.pipeline_runs(id) ON DELETE CASCADE;


-- (FK removido: tabela_eb eh tabela V1-legacy nao incluida no schema empresa V2)


--
-- Name: s1210_cpf_scope s1210_cpf_scope_xlsx_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.s1210_cpf_scope
    ADD CONSTRAINT s1210_cpf_scope_xlsx_id_fkey FOREIGN KEY (xlsx_id) REFERENCES public.s1210_xlsx(id) ON DELETE CASCADE;


--
-- Name: s1210_operadoras s1210_operadoras_xlsx_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.s1210_operadoras
    ADD CONSTRAINT s1210_operadoras_xlsx_id_fkey FOREIGN KEY (xlsx_id) REFERENCES public.s1210_xlsx(id) ON DELETE CASCADE;


--
-- Name: timeline_envio_item timeline_envio_item_timeline_envio_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.timeline_envio_item
    ADD CONSTRAINT timeline_envio_item_timeline_envio_id_fkey FOREIGN KEY (timeline_envio_id) REFERENCES public.timeline_envio(id) ON DELETE CASCADE;


--
-- Name: timeline_envio timeline_envio_timeline_mes_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.timeline_envio
    ADD CONSTRAINT timeline_envio_timeline_mes_id_fkey FOREIGN KEY (timeline_mes_id) REFERENCES public.timeline_mes(id) ON DELETE CASCADE;


--
-- Name: timeline_mes timeline_mes_empresa_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.timeline_mes
    ADD CONSTRAINT timeline_mes_empresa_id_fkey FOREIGN KEY (empresa_id) REFERENCES public.master_empresas(id) ON DELETE CASCADE;


--
-- Name: timeline_mes timeline_mes_head_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.timeline_mes
    ADD CONSTRAINT timeline_mes_head_fk FOREIGN KEY (head_envio_id) REFERENCES public.timeline_envio(id) ON DELETE SET NULL;


--
--


-- =====================================================================
-- Marcacao de versao aplicada
-- =====================================================================
INSERT INTO public.schema_meta (target, version) VALUES ('empresa','1.0.0')
ON CONFLICT (target, version) DO NOTHING;

COMMIT;