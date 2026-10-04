ALTER TABLE jobs ADD COLUMN notebook_id TEXT REFERENCES notebooks(id) ON DELETE CASCADE;
ALTER TABLE jobs ADD COLUMN source_id TEXT REFERENCES sources(id) ON DELETE CASCADE;
UPDATE jobs SET notebook_id = (
    SELECT id FROM notebooks WHERE id=json_extract(jobs.payload_json,'$.notebook_id')
);
UPDATE jobs SET notebook_id = (
    SELECT notebook_id FROM decks WHERE id=jobs.entity_id
) WHERE type IN ('deck_generate','deck_export','slide_revision');
UPDATE jobs SET source_id = (
    SELECT id FROM sources WHERE id=jobs.entity_id
) WHERE type='source_ingest';
DELETE FROM jobs WHERE
    (type='source_ingest' AND source_id IS NULL) OR
    (type IN ('chat_answer','knowledge_generate','knowledge_update','transform_source',
              'deck_generate','deck_export','slide_revision') AND notebook_id IS NULL);
CREATE INDEX jobs_notebook ON jobs(notebook_id,status);

CREATE TABLE garbage_files (relative_path TEXT PRIMARY KEY);
CREATE TRIGGER source_files_deleted AFTER DELETE ON sources BEGIN
    INSERT OR IGNORE INTO garbage_files VALUES ('sources/' || OLD.id);
END;
CREATE TRIGGER asset_files_deleted AFTER DELETE ON assets BEGIN
    INSERT OR IGNORE INTO garbage_files VALUES ('assets/' || OLD.id);
END;
CREATE TRIGGER render_files_deleted AFTER DELETE ON slide_renders BEGIN
    INSERT OR IGNORE INTO garbage_files VALUES ('renders/' || OLD.id);
END;
CREATE TRIGGER export_files_deleted AFTER DELETE ON pdf_exports BEGIN
    INSERT OR IGNORE INTO garbage_files VALUES ('exports/' || OLD.id);
END;
CREATE TRIGGER slide_revisions_deleted BEFORE DELETE ON slides BEGIN
    DELETE FROM jobs WHERE id IN (SELECT job_id FROM slide_revisions WHERE slide_id=OLD.id);
    DELETE FROM slide_revisions WHERE slide_id=OLD.id;
END;
