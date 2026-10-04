CREATE TABLE notebooks (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE sources (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL CHECK(type IN ('epub', 'pdf', 'markdown', 'text')),
    title TEXT NOT NULL,
    original_filename TEXT NOT NULL,
    mime_type TEXT NOT NULL,
    file_uri TEXT NOT NULL,
    file_size INTEGER NOT NULL,
    checksum_sha256 TEXT NOT NULL UNIQUE,
    parser_version TEXT,
    status TEXT NOT NULL DEFAULT 'uploaded',
    error_code TEXT,
    error_message TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE notebook_sources (
    notebook_id TEXT NOT NULL REFERENCES notebooks(id) ON DELETE CASCADE,
    source_id TEXT NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    ordinal INTEGER NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1 CHECK(enabled IN (0,1)),
    added_at TEXT NOT NULL,
    PRIMARY KEY(notebook_id, source_id)
);

CREATE TABLE model_configs (
    role TEXT PRIMARY KEY CHECK(role IN ('language', 'embedding', 'image')),
    base_url TEXT NOT NULL,
    model_id TEXT NOT NULL,
    api_key_secret_ref TEXT NOT NULL,
    max_context_tokens INTEGER NOT NULL,
    capabilities_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE app_settings (
    key TEXT PRIMARY KEY,
    value_json TEXT NOT NULL
);

