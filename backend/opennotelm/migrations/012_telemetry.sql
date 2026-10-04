CREATE TABLE telemetry_queue (
    id TEXT PRIMARY KEY,
    event TEXT NOT NULL,
    properties_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    queued_at INTEGER NOT NULL
);
CREATE INDEX telemetry_queue_age ON telemetry_queue(queued_at);
