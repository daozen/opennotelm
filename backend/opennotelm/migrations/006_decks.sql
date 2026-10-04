CREATE TABLE decks (
    id TEXT PRIMARY KEY,
    notebook_id TEXT NOT NULL REFERENCES notebooks(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    source_scope_json TEXT NOT NULL,
    target_slide_count INTEGER NOT NULL CHECK(target_slide_count IN (10,15,20)),
    language TEXT NOT NULL,
    instruction TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft',
    brief_json TEXT,
    plan_json TEXT,
    style_json TEXT,
    understanding_json TEXT,
    knowledge_snapshot_json TEXT,
    generation_metadata_json TEXT NOT NULL DEFAULT '{}',
    revision INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX decks_notebook ON decks(notebook_id, updated_at);
CREATE TABLE slides (
    id TEXT PRIMARY KEY,
    deck_id TEXT NOT NULL REFERENCES decks(id) ON DELETE CASCADE,
    ordinal INTEGER NOT NULL,
    plan_json TEXT NOT NULL,
    spec_json TEXT,
    status TEXT NOT NULL DEFAULT 'planned',
    revision INTEGER NOT NULL DEFAULT 0,
    error_code TEXT,
    error_message TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(deck_id, ordinal)
);
CREATE INDEX slides_deck ON slides(deck_id, ordinal);
