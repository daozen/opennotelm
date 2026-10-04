CREATE TABLE knowledge_pages (
    id TEXT PRIMARY KEY,
    notebook_id TEXT NOT NULL REFERENCES notebooks(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    slug TEXT NOT NULL,
    content_markdown TEXT NOT NULL DEFAULT '',
    generation_metadata_json TEXT NOT NULL DEFAULT '{}',
    revision INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(notebook_id, slug)
);
CREATE INDEX knowledge_notebook ON knowledge_pages(notebook_id, updated_at);
CREATE TABLE synthesis_checkpoints (
    job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    step TEXT NOT NULL,
    input_hash TEXT NOT NULL,
    content TEXT NOT NULL,
    PRIMARY KEY(job_id, step)
);
