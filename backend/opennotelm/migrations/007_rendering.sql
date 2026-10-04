ALTER TABLE slides ADD COLUMN current_render_id TEXT;
CREATE TABLE slide_renders (
    id TEXT PRIMARY KEY,
    slide_id TEXT NOT NULL REFERENCES slides(id) ON DELETE CASCADE,
    input_hash TEXT NOT NULL,
    render_spec_json TEXT NOT NULL,
    image_uri TEXT NOT NULL,
    thumbnail_uri TEXT NOT NULL,
    native_pdf_uri TEXT NOT NULL,
    width INTEGER NOT NULL,
    height INTEGER NOT NULL,
    text_layer_json TEXT NOT NULL,
    renderer_version TEXT NOT NULL,
    browser_version TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(slide_id,input_hash)
);
