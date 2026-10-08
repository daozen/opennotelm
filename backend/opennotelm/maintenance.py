"""Crash-safe deletion of owned files and disposable source evidence caches."""

import json
import re
import shutil
import threading

from .errors import AppError

OWNED = {
    "podcasts": "podcasts",
    "mindmaps": "mindmaps",
    "sources": "sources",
    "assets": "assets",
    "renders": "slide_renders",
    "exports": "pdf_exports",
}
OWNED_PATH = re.compile(r"(?:sources|assets|renders|exports|podcasts|mindmaps)/[a-f0-9]{32}\Z")


def contains_id(value, identity):
    if isinstance(value, dict):
        return any(contains_id(item, identity) for item in value.values())
    if isinstance(value, list):
        return any(contains_id(item, identity) for item in value)
    return value == identity


def discard_source_caches(conn, source_id):
    affected_decks = set()
    for table in ("decks", "podcasts", "mindmaps"):
        for row in conn.execute(
            f"SELECT id,source_scope_json,understanding_json,knowledge_snapshot_json FROM {table}"
        ):
            scope = json.loads(row["source_scope_json"])
            understanding = json.loads(row["understanding_json"] or "null")
            snapshot = json.loads(row["knowledge_snapshot_json"] or "null")
            citations = list((snapshot or {}).get("citations", {}).values())
            grounded_in_source = any(
                conn.execute(
                    "SELECT 1 FROM citation_spans WHERE citation_id=? AND source_id=?",
                    (citation, source_id),
                ).fetchone()
                for citation in citations
            )
            if (
                contains_id(scope, source_id)
                or contains_id(understanding, source_id)
                or grounded_in_source
            ):
                affected_decks.add(row["id"])
                if understanding:
                    for packet in understanding["evidence"]:
                        if contains_id(packet["spans"], source_id):
                            packet["text"] = ""
                    conn.execute(
                        f"UPDATE {table} SET understanding_json=? WHERE id=?",
                        (json.dumps(understanding), row["id"]),
                    )
    for job in conn.execute("SELECT * FROM jobs").fetchall():
        if (
            job["source_id"] == source_id
            or job["entity_id"] in affected_decks
            or contains_id(json.loads(job["payload_json"]), source_id)
        ):
            if job["status"] in ("queued", "running"):
                raise AppError(
                    "SOURCE_BUSY",
                    "Wait for tasks using this source to finish before deleting it.",
                    409,
                )
            conn.execute("DELETE FROM synthesis_checkpoints WHERE job_id=?", (job["id"],))
            conn.execute("DELETE FROM transformations WHERE job_id=?", (job["id"],))


class FileMaintenance:
    def __init__(self, db, settings):
        self.db, self.root = db, settings.data_dir.resolve()
        self.lock = threading.Lock()

    def recover(self):
        # Called only at startup, under the instance lock, before any uploads/jobs.
        with self.db.connect() as conn:
            for directory, table in OWNED.items():
                if (self.root / directory).is_symlink():
                    continue
                live = {row[0] for row in conn.execute(f"SELECT id FROM {table}")}
                for path in (self.root / directory).iterdir():
                    if re.fullmatch(r"[a-f0-9]{32}", path.name) and path.name not in live:
                        conn.execute(
                            "INSERT OR IGNORE INTO garbage_files VALUES (?)",
                            (f"{directory}/{path.name}",),
                        )
        for path in (self.root / "cache").glob("upload-*"):
            if re.fullmatch(r"upload-[a-f0-9]{32}", path.name) and path.is_file():
                path.unlink(missing_ok=True)
        self.drain()

    def drain(self):
        with self.lock:
            with self.db.connect() as conn:
                paths = [row[0] for row in conn.execute("SELECT relative_path FROM garbage_files")]
            for relative in paths:
                if not OWNED_PATH.fullmatch(relative):
                    continue
                path = self.root / relative
                # Never traverse a replaced data subdirectory or follow a symlink.
                if path.parent.is_symlink() or not path.parent.resolve().is_relative_to(self.root):
                    continue
                try:
                    if path.is_symlink() or path.is_file():
                        path.unlink(missing_ok=True)
                    elif path.exists():
                        shutil.rmtree(path)
                except OSError:
                    continue  # Durable queue is retried on the next delete/startup.
                with self.db.connect() as conn:
                    conn.execute("DELETE FROM garbage_files WHERE relative_path=?", (relative,))
