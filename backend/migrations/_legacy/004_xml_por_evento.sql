-- Migration 004 — XML por evento
-- Cada explorador_eventos passa a ter seu próprio Large Object (xml_oid).
-- Backfill é separado (ver app/backfill_xml.py).

BEGIN;

ALTER TABLE explorador_eventos
    ADD COLUMN IF NOT EXISTS xml_oid OID NULL,
    ADD COLUMN IF NOT EXISTS xml_size_bytes BIGINT NULL,
    ADD COLUMN IF NOT EXISTS xml_sha256 CHAR(64) NULL;

CREATE INDEX IF NOT EXISTS ix_evt_xml_oid_pendente
    ON explorador_eventos (id)
    WHERE xml_oid IS NULL;

COMMIT;
