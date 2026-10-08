"""Deliberately selected operational fields, never a database dump or raw log bundle."""

import json
import math
import re
from datetime import UTC, datetime

from . import __version__
from .error_codes import safe_error_code
from .generation_attempts import safe_attempt
from .telemetry import current_os

JOB_TYPES = {
    "source_ingest",
    "source_reindex",
    "source_web_images",
    "chat_answer",
    "knowledge_generate",
    "knowledge_update",
    "transform_source",
    "podcast_generate",
    "mindmap_generate",
    "deck_generate",
    "deck_export",
    "slide_revision",
}
STAGES = JOB_TYPES | {
    "podcast_reading",
    "mindmap_reading",
    "mindmap_mapping",
    "mindmap_exporting",
    "podcast_planning",
    "podcast_writing",
    "podcast_speech",
    "podcast_assembling",
    "queued",
    "resuming",
    "completed",
    "parsing",
    "fetching_web",
    "fetching_images",
    "recognizing_images",
    "normalizing",
    "chunking",
    "embedding",
    "retrieving",
    "answering",
    "verifying_citations",
    "synthesizing_sections",
    "synthesizing_page",
    "updating_knowledge",
    "understanding",
    "planning",
    "styling",
    "authoring",
    "art_directing",
    "generating_assets",
    "rendering",
    "exporting",
    "revising",
}


def identity(value):
    return value if isinstance(value, str) and re.fullmatch(r"[0-9a-f]{32}", value) else None


def timestamp(value):
    try:
        parsed = datetime.fromisoformat(value) if value else None
        if parsed and parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.isoformat() if parsed else None
    except (TypeError, ValueError):
        return None


def diagnostic_report(app):
    db = app.state.db
    models, configurations = [], []
    for role in ("language", "embedding", "image", "speech"):
        try:
            config, key = app.state.models.configured(role)
        except Exception:
            continue
        configurations.append((role, config.model_id, key))
    keys = [key for _, _, key in configurations if key]
    for role, model_id, _ in configurations:
        if (
            not re.fullmatch(r"[A-Za-z0-9_./:@-]{1,200}", model_id)
            or "://" in model_id
            or any(key in model_id for key in keys)
        ):
            model_id = "[redacted]"
        models.append({"role": role, "model_id": model_id})
    with db.connect() as conn:
        versions = [
            row[0]
            for row in conn.execute("SELECT version FROM schema_migrations ORDER BY version")
            if re.fullmatch(r"[0-9]{3}_[a-z_]+", row[0])
        ]
        source_counts = {
            row["type"]: row["count"]
            for row in conn.execute("SELECT type,count(*) AS count FROM sources GROUP BY type")
            if row["type"] in app.state.sources.parsers
        }
        jobs = []
        for row in conn.execute(
            "SELECT id,type,stage,status,progress,error_code,retry_count,created_at,started_at,"
            "finished_at FROM jobs ORDER BY created_at DESC,rowid DESC LIMIT 100"
        ):
            jobs.append(
                {
                    "id": identity(row["id"]),
                    "type": row["type"] if row["type"] in JOB_TYPES else "unknown",
                    "stage": row["stage"] if row["stage"] in STAGES else "unknown",
                    "status": row["status"],
                    "error_code": safe_error_code(row["error_code"]),
                    "retry_count": row["retry_count"],
                    **{
                        key: timestamp(row[key])
                        for key in ("created_at", "started_at", "finished_at")
                    },
                }
            )
        traces = [
            {
                "job_id": identity(row["job_id"]),
                "stage": row["stage"] if row["stage"] in STAGES else "unknown",
                "started_at": timestamp(row["started_at"]),
                "finished_at": timestamp(row["finished_at"]),
                "error_code": safe_error_code(row["error_code"]),
            }
            for row in conn.execute(
                "SELECT job_id,stage,started_at,finished_at,error_code FROM processing_runs "
                "ORDER BY rowid DESC LIMIT 100"
            )
        ]
        attempts = [
            {
                "job_id": identity(row["job_id"]),
                "stage": row["stage"],
                **safe_attempt(json.loads(row["metadata_json"])),
            }
            for row in conn.execute(
                "SELECT job_id,stage,metadata_json FROM generation_attempts "
                "ORDER BY id DESC LIMIT 100"
            )
        ]
        scores = []
        for row in conn.execute(
            "SELECT metadata_json FROM messages WHERE role='assistant' ORDER BY rowid DESC LIMIT 50"
        ):
            try:
                values = json.loads(row[0]).get("retrieval", {}).get("scores", [])
                scores.extend(
                    value
                    for value in values
                    if type(value) in (int, float) and math.isfinite(value) and -1 <= value <= 1
                )
            except (ValueError, TypeError, AttributeError):
                continue
    return {
        "report_version": 1,
        "app_version": __version__,
        "os": current_os(),
        "schema_versions": versions,
        "parser_versions": {kind: parser[0] for kind, parser in app.state.sources.parsers.items()},
        "source_counts": source_counts,
        "models": models,
        "jobs": jobs,
        "job_traces": traces,
        "generation_attempts": attempts,
        "retrieval_scores": {
            "count": len(scores),
            "min": round(min(scores), 4) if scores else None,
            "max": round(max(scores), 4) if scores else None,
            "mean": round(sum(scores) / len(scores), 4) if scores else None,
        },
        "telemetry": app.state.telemetry.status(),
    }
