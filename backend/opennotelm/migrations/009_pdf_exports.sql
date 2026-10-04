CREATE TABLE pdf_exports (
    id TEXT PRIMARY KEY,
    deck_id TEXT NOT NULL REFERENCES decks(id) ON DELETE CASCADE,
    input_hash TEXT NOT NULL,
    status TEXT NOT NULL,
    file_uri TEXT,
    file_sha256 TEXT,
    page_count INTEGER,
    file_size INTEGER,
    error_code TEXT,
    error_message TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(deck_id, input_hash)
);
