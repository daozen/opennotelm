CREATE TABLE slide_designs (
    id TEXT PRIMARY KEY,
    slide_id TEXT NOT NULL REFERENCES slides(id) ON DELETE CASCADE,
    input_hash TEXT NOT NULL,
    design_json TEXT NOT NULL,
    design_version TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(slide_id,input_hash)
);
CREATE INDEX slide_designs_slide ON slide_designs(slide_id,created_at);
