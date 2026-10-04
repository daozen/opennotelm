ALTER TABLE slides ADD COLUMN visual_revision INTEGER NOT NULL DEFAULT 0;
ALTER TABLE slides ADD COLUMN image_revision INTEGER NOT NULL DEFAULT 0;
ALTER TABLE slides ADD COLUMN visual_instruction TEXT NOT NULL DEFAULT '';
ALTER TABLE slides ADD COLUMN image_instruction TEXT NOT NULL DEFAULT '';
ALTER TABLE slides ADD COLUMN current_render_revision INTEGER;
UPDATE slides SET current_render_revision=revision WHERE current_render_id IS NOT NULL;
CREATE TABLE slide_revisions (
    id TEXT PRIMARY KEY,
    deck_id TEXT NOT NULL REFERENCES decks(id) ON DELETE CASCADE,
    slide_id TEXT REFERENCES slides(id) ON DELETE SET NULL,
    action TEXT NOT NULL,
    instruction TEXT NOT NULL DEFAULT '',
    base_revision INTEGER NOT NULL,
    base_snapshot_json TEXT NOT NULL,
    target TEXT,
    decision_json TEXT,
    stage TEXT NOT NULL DEFAULT 'pending',
    status TEXT NOT NULL DEFAULT 'queued',
    job_id TEXT,
    error_code TEXT,
    error_message TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX slide_revisions_slide ON slide_revisions(slide_id,created_at);
