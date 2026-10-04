CREATE TABLE assets (
    id TEXT PRIMARY KEY,
    slide_id TEXT NOT NULL REFERENCES slides(id) ON DELETE CASCADE,
    request_id TEXT NOT NULL,
    input_hash TEXT NOT NULL,
    type TEXT NOT NULL DEFAULT 'generated_image',
    status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','generating','ready','failed','skipped')),
    prompt TEXT,
    negative_prompt TEXT,
    style_context_json TEXT NOT NULL,
    generation_metadata_json TEXT NOT NULL DEFAULT '{}',
    file_uri TEXT,
    width INTEGER,
    height INTEGER,
    error_code TEXT,
    error_message TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(slide_id, request_id, input_hash)
);
CREATE INDEX assets_slide ON assets(slide_id);
