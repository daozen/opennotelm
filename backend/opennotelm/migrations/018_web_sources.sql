-- requires-foreign-keys-off
CREATE TABLE sources_expanded (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL CHECK(type IN ('epub', 'pdf', 'markdown', 'text', 'docx', 'web')),
    title TEXT NOT NULL,
    original_filename TEXT NOT NULL,
    mime_type TEXT NOT NULL,
    file_uri TEXT NOT NULL,
    file_size INTEGER NOT NULL,
    checksum_sha256 TEXT NOT NULL UNIQUE,
    parser_version TEXT,
    status TEXT NOT NULL DEFAULT 'uploaded',
    error_code TEXT,
    error_message TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}'
);
INSERT INTO sources_expanded SELECT * FROM sources;
DROP TABLE sources;
ALTER TABLE sources_expanded RENAME TO sources;
CREATE TRIGGER source_files_deleted AFTER DELETE ON sources BEGIN
    INSERT OR IGNORE INTO garbage_files VALUES ('sources/' || OLD.id);
END;
CREATE UNIQUE INDEX web_source_url ON sources(json_extract(metadata_json, '$.url')) WHERE type='web';
