ALTER TABLE decks ADD COLUMN title_mode TEXT NOT NULL DEFAULT 'auto'
    CHECK(title_mode IN ('auto','source','custom'));
ALTER TABLE decks ADD COLUMN export_title TEXT NOT NULL DEFAULT '';
ALTER TABLE decks ADD COLUMN source_manifest_json TEXT;
-- Preserve existing export signatures; a display rename must not rewrite a saved PDF.
UPDATE decks SET export_title=title;
