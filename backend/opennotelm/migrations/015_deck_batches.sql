CREATE TABLE deck_batches (
    id TEXT PRIMARY KEY,
    notebook_id TEXT NOT NULL REFERENCES notebooks(id) ON DELETE CASCADE,
    request_key TEXT NOT NULL,
    request_json TEXT NOT NULL,
    deck_ids_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(notebook_id, request_key)
);
