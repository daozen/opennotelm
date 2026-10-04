import json
import logging
import re
import sys

from . import __version__
from .diagnostics import JOB_TYPES
from .error_codes import safe_error_code
from .telemetry import EventProperties, size_bucket

logger = logging.getLogger("opennotelm.jobs")


def configure_logging():
    console = next(
        (handler for handler in logger.handlers if getattr(handler, "opennotelm_console", False)),
        None,
    )
    if console:
        console.stream = sys.stderr
    else:
        handler = logging.StreamHandler()
        handler.opennotelm_console = True
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


def record_job(service, job, outcome, duration_ms=0, error=None, result=None):
    try:
        _record_job(service, job, outcome, duration_ms, error, result)
    except Exception:
        logger.warning("Optional job event recording unavailable")


def _record_job(service, job, outcome, duration_ms, error, result):
    logger.info(
        json.dumps(
            {
                "event": f"job_{outcome}",
                "stage": job["type"] if job["type"] in JOB_TYPES else "unknown",
                "entity_id": job["entity_id"]
                if re.fullmatch(r"[a-f0-9]{32}", job["entity_id"])
                else None,
                "error_code": safe_error_code(error.code) if error else None,
                "duration_ms": duration_ms,
                "app_version": __version__,
            }
        )
    )
    if outcome == "cancelled":
        return
    telemetry = service.telemetry
    if not telemetry:
        return
    properties = {} if outcome == "started" else {"duration_ms": min(86400000, max(0, duration_ms))}
    if error:
        properties["error_code"] = error.code
    with service.db.connect() as conn:
        if job["type"] == "source_ingest":
            row = conn.execute(
                "SELECT type,file_size FROM sources WHERE id=?", (job["entity_id"],)
            ).fetchone()
            if row:
                properties.update(
                    source_type=row["type"], size_bucket=size_bucket(row["file_size"])
                )
        if job["type"] in ("deck_generate", "slide_revision", "deck_export"):
            row = conn.execute(
                "SELECT target_slide_count,(SELECT count(*) FROM slides WHERE deck_id=decks.id) "
                "AS actual FROM decks WHERE id=?",
                (job["entity_id"],),
            ).fetchone()
            if row:
                properties["slide_count"] = row["actual"] or row["target_slide_count"]
        revision = conn.execute(
            "SELECT action FROM slide_revisions WHERE job_id=?", (job["id"],)
        ).fetchone()
    if outcome == "started":
        name = {
            "source_ingest": "source_import_started",
            "chat_answer": "chat_message_sent",
            "deck_generate": "deck_generation_started",
        }.get(job["type"])
    elif outcome == "completed":
        name = {
            "source_ingest": "source_import_completed",
            "chat_answer": "chat_response_completed",
            "knowledge_generate": "knowledge_generated",
            "knowledge_update": "knowledge_updated",
            "deck_generate": "deck_generation_completed",
        }.get(job["type"])
        if job["type"] == "deck_generate" and (result or {}).get("failed_slide_ids"):
            name = "deck_generation_failed"
        if job["type"] == "slide_revision" and revision:
            name = (
                "slide_revised" if revision["action"] in ("revise", "text") else "slide_regenerated"
            )
    else:
        name = {
            "source_ingest": "source_import_failed",
            "chat_answer": "chat_response_failed",
            "deck_generate": "deck_generation_failed",
        }.get(job["type"])
    if name:
        telemetry.capture(name, EventProperties(**properties))
