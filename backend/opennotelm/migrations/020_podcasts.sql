-- requires-foreign-keys-off
CREATE TABLE model_configs_new (
    role TEXT PRIMARY KEY CHECK(role IN ('language','embedding','image','speech')),
    base_url TEXT NOT NULL,
    model_id TEXT NOT NULL,
    api_key_secret_ref TEXT NOT NULL,
    max_context_tokens INTEGER NOT NULL,
    capabilities_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
INSERT INTO model_configs_new SELECT * FROM model_configs;
DROP TABLE model_configs;
ALTER TABLE model_configs_new RENAME TO model_configs;

CREATE TABLE citations_new (
    id TEXT PRIMARY KEY,
    notebook_id TEXT NOT NULL REFERENCES notebooks(id) ON DELETE CASCADE,
    owner_type TEXT NOT NULL CHECK(owner_type IN ('message','knowledge','slide','podcast_segment')),
    owner_id TEXT NOT NULL,
    evidence_id TEXT NOT NULL,
    created_at TEXT NOT NULL
);
INSERT INTO citations_new SELECT * FROM citations;
DROP TABLE citations;
ALTER TABLE citations_new RENAME TO citations;
CREATE INDEX citations_owner ON citations(owner_type,owner_id);

CREATE TABLE podcasts (
    id TEXT PRIMARY KEY,
    notebook_id TEXT NOT NULL REFERENCES notebooks(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued',
    revision INTEGER NOT NULL DEFAULT 1,
    input_json TEXT NOT NULL,
    source_scope_json TEXT NOT NULL,
    knowledge_snapshot_json TEXT,
    source_manifest_json TEXT NOT NULL,
    settings_json TEXT NOT NULL,
    understanding_json TEXT,
    plan_json TEXT,
    audio_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE podcast_segments (
    id TEXT PRIMARY KEY,
    podcast_id TEXT NOT NULL REFERENCES podcasts(id) ON DELETE CASCADE,
    ordinal INTEGER NOT NULL,
    title TEXT NOT NULL,
    plan_json TEXT NOT NULL,
    script_json TEXT,
    revision INTEGER NOT NULL DEFAULT 1,
    UNIQUE(podcast_id,ordinal)
);
CREATE TABLE podcast_audio_chunks (
    podcast_id TEXT NOT NULL REFERENCES podcasts(id) ON DELETE CASCADE,
    input_hash TEXT NOT NULL,
    file_uri TEXT NOT NULL,
    file_sha256 TEXT NOT NULL,
    duration REAL NOT NULL,
    PRIMARY KEY(podcast_id,input_hash)
);
CREATE TABLE podcast_batches (
    notebook_id TEXT NOT NULL REFERENCES notebooks(id) ON DELETE CASCADE,
    request_key TEXT NOT NULL,
    input_hash TEXT NOT NULL,
    ids_json TEXT NOT NULL,
    PRIMARY KEY(notebook_id,request_key)
);
CREATE TRIGGER podcast_files_deleted AFTER DELETE ON podcasts BEGIN
    INSERT OR IGNORE INTO garbage_files VALUES ('podcasts/' || OLD.id);
    DELETE FROM jobs WHERE entity_id=OLD.id AND type='podcast_generate';
END;
CREATE TRIGGER podcast_citations_deleted AFTER DELETE ON podcast_segments BEGIN
    DELETE FROM citations WHERE owner_type='podcast_segment' AND owner_id=OLD.id;
END;
