-- Rebuildable full-work summaries, shared by chapter decks of the same source.
CREATE TABLE work_context_cache (
    source_id TEXT PRIMARY KEY REFERENCES sources(id) ON DELETE CASCADE,
    input_hash TEXT NOT NULL,
    value_json TEXT NOT NULL
);
