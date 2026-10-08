"""Per-deck support report: bounded operational metadata, never prompts or content."""

import json

from .diagnostics import STAGES, identity, timestamp
from .error_codes import safe_error_code
from .generation_attempts import safe_attempt

ATTEMPT_STAGES = {
    "DeckPreferences",
    "DeckBrief",
    "DeckPlan",
    "DeckStyleManifest",
    "AdaptiveDeckStyle",
    "SlideSpec",
    "DeckArt",
    "PodcastIntent",
    "PodcastPlan",
    "PodcastScript",
    "podcast",
    "podcast_speech",
    "deck",
    "work_context",
    "image_generation",
}


def attempt_row(row):
    try:
        data = json.loads(row["metadata_json"])
    except (TypeError, ValueError):
        data = {}
    return {
        "id": row["id"],
        "job_id": identity(row["job_id"]),
        "stage": row["stage"] if row["stage"] in ATTEMPT_STAGES else "other",
        "created_at": timestamp(row["created_at"]),
        **safe_attempt(data),
    }


def deck_report(app, deck_id):
    app.state.decks.record(deck_id)  # Existence check, matching normal Deck lookup.
    with app.state.db.connect() as conn:
        jobs = [
            {
                "id": identity(r["id"]),
                "status": r["status"],
                "stage": r["stage"] if r["stage"] in STAGES else "unknown",
                "error_code": safe_error_code(r["error_code"]),
                "retry_count": r["retry_count"],
                **{k: timestamp(r[k]) for k in ("created_at", "started_at", "finished_at")},
            }
            for r in conn.execute(
                "SELECT * FROM jobs WHERE entity_id=? "
                "ORDER BY created_at DESC,rowid DESC LIMIT 100",
                (deck_id,),
            )
        ]
        attempts = [
            attempt_row(r)
            for r in conn.execute(
                "SELECT a.* FROM generation_attempts a JOIN jobs j ON a.job_id=j.id "
                "WHERE j.entity_id=? ORDER BY a.id DESC LIMIT 500",
                (deck_id,),
            )
        ]
        count = conn.execute(
            "SELECT count(*) FROM generation_attempts a JOIN jobs j ON a.job_id=j.id "
            "WHERE j.entity_id=?",
            (deck_id,),
        ).fetchone()[0]
        slides = [
            {
                "id": identity(r["id"]),
                "page": r["ordinal"] + 1,
                "status": r["status"],
                "error_code": safe_error_code(r["error_code"]),
            }
            for r in conn.execute(
                "SELECT * FROM slides WHERE deck_id=? ORDER BY ordinal", (deck_id,)
            )
        ]
        runs = [
            {
                "job_id": identity(r["job_id"]),
                "started_at": timestamp(r["started_at"]),
                "finished_at": timestamp(r["finished_at"]),
                "error_code": safe_error_code(r["error_code"]),
            }
            for r in conn.execute(
                "SELECT p.* FROM processing_runs p JOIN jobs j ON p.job_id=j.id "
                "WHERE j.entity_id=? ORDER BY p.rowid DESC LIMIT 100",
                (deck_id,),
            )
        ]
    return {
        "report_version": 1,
        "deck_id": deck_id,
        "jobs": jobs,
        "slides": slides,
        "runs": runs,
        "attempts": attempts,
        "omitted_attempts": max(0, count - len(attempts)),
    }
