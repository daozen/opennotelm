-- requires-foreign-keys-off
DROP TRIGGER podcast_citations_deleted;
CREATE TABLE citations_new (
    id TEXT PRIMARY KEY,
    notebook_id TEXT NOT NULL REFERENCES notebooks(id) ON DELETE CASCADE,
    owner_type TEXT NOT NULL CHECK(owner_type IN ('message','knowledge','slide','podcast_segment','mindmap')),
    owner_id TEXT NOT NULL,
    evidence_id TEXT NOT NULL,
    created_at TEXT NOT NULL
);
INSERT INTO citations_new SELECT * FROM citations;
DROP TABLE citations;
ALTER TABLE citations_new RENAME TO citations;
CREATE INDEX citations_owner ON citations(owner_type,owner_id);
CREATE TRIGGER podcast_citations_deleted AFTER DELETE ON podcast_segments BEGIN
    DELETE FROM citations WHERE owner_type='podcast_segment' AND owner_id=OLD.id;
END;

CREATE TABLE mindmaps (
    id TEXT PRIMARY KEY,
    notebook_id TEXT NOT NULL REFERENCES notebooks(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued',
    input_json TEXT NOT NULL,
    source_scope_json TEXT NOT NULL,
    knowledge_snapshot_json TEXT,
    source_manifest_json TEXT NOT NULL,
    settings_json TEXT NOT NULL,
    understanding_json TEXT,
    tree_json TEXT,
    export_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE mindmap_batches (
    notebook_id TEXT NOT NULL REFERENCES notebooks(id) ON DELETE CASCADE,
    request_key TEXT NOT NULL,
    input_hash TEXT NOT NULL,
    ids_json TEXT NOT NULL,
    PRIMARY KEY(notebook_id,request_key)
);
CREATE TRIGGER mindmap_deleted AFTER DELETE ON mindmaps BEGIN
    DELETE FROM citations WHERE owner_type='mindmap' AND owner_id=OLD.id;
    DELETE FROM jobs WHERE entity_id=OLD.id AND type='mindmap_generate';
    INSERT OR IGNORE INTO garbage_files VALUES ('mindmaps/' || OLD.id);
END;
