-- Short-lived job output, never included in the notebook's Knowledge library.
CREATE TABLE transformations (
    id TEXT PRIMARY KEY,
    notebook_id TEXT NOT NULL REFERENCES notebooks(id) ON DELETE CASCADE,
    kind TEXT NOT NULL CHECK(kind IN ('summary','outline')),
    job_id TEXT NOT NULL,
    content_markdown TEXT NOT NULL DEFAULT '',
    evidence_json TEXT NOT NULL DEFAULT '[]',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    saved_page_id TEXT,
    discarded INTEGER NOT NULL DEFAULT 0,
    expires_at INTEGER NOT NULL
);
CREATE INDEX transformations_expiry ON transformations(expires_at);
