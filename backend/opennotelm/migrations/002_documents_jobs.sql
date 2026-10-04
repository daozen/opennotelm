ALTER TABLE sources ADD COLUMN metadata_json TEXT NOT NULL DEFAULT '{}';

CREATE TABLE source_nodes (
    id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    parent_id TEXT REFERENCES source_nodes(id) ON DELETE CASCADE,
    type TEXT NOT NULL,
    title TEXT NOT NULL,
    depth INTEGER NOT NULL,
    ordinal INTEGER NOT NULL,
    start_page INTEGER,
    end_page INTEGER,
    metadata_json TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX source_nodes_order ON source_nodes(source_id, ordinal);

CREATE TABLE content_blocks (
    id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    node_id TEXT NOT NULL REFERENCES source_nodes(id) ON DELETE CASCADE,
    type TEXT NOT NULL,
    ordinal INTEGER NOT NULL,
    text TEXT NOT NULL,
    page_start INTEGER,
    page_end INTEGER,
    location_json TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX content_blocks_order ON content_blocks(source_id, ordinal);
CREATE INDEX content_blocks_node ON content_blocks(node_id);

CREATE TABLE jobs (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('queued','running','completed','failed','cancelled')),
    stage TEXT NOT NULL DEFAULT 'queued',
    progress REAL NOT NULL DEFAULT 0,
    payload_json TEXT NOT NULL,
    result_json TEXT,
    created_at TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT,
    error_code TEXT,
    error_message TEXT,
    retry_count INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX jobs_queue ON jobs(status, created_at);
CREATE UNIQUE INDEX jobs_active ON jobs(type, entity_id) WHERE status IN ('queued','running');

CREATE TABLE processing_runs (
    id TEXT PRIMARY KEY,
    entity_id TEXT NOT NULL,
    job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    stage TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    version TEXT NOT NULL,
    error_code TEXT
);

