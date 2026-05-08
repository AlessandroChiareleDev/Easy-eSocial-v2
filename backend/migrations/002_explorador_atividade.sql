-- Histórico de atividade do Explorador (upload, exclusão, extração)
CREATE TABLE IF NOT EXISTS explorador_atividade (
    id BIGSERIAL PRIMARY KEY,
    empresa_id INT NOT NULL,
    acao TEXT NOT NULL CHECK (acao IN ('upload', 'exclusao', 'extracao', 'duplicado')),
    zip_id INT NULL,
    nome_arquivo TEXT NULL,
    sha256 TEXT NULL,
    tamanho_bytes BIGINT NULL,
    total_xmls INT NULL,
    detalhe JSONB NULL,
    criado_em TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_explorador_atividade_emp_dt
    ON explorador_atividade (empresa_id, criado_em DESC);
