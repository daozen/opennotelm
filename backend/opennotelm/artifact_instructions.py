"""Reuse saved artifact instructions without copying user text into another store."""

from typing import Literal

from fastapi import APIRouter, Request

from .db import Database

ArtifactKind = Literal["deck", "podcast", "mindmap"]
HISTORY_LIMIT = 20
router = APIRouter(prefix="/api")


def instruction_history(db: Database, kind: ArtifactKind) -> dict:
    # Only these application-owned columns can be queried; kind is never SQL text.
    table, column = {
        "deck": ("decks", "instruction"),
        "podcast": (
            "podcasts",
            "CASE WHEN json_valid(input_json) THEN CASE "
            "WHEN json_type(input_json,'$.instruction')='text' "
            "THEN json_extract(input_json,'$.instruction') END END",
        ),
        "mindmap": (
            "mindmaps",
            "CASE WHEN json_valid(input_json) THEN CASE WHEN "
            "json_type(input_json,'$.instruction')='text' THEN "
            "json_extract(input_json,'$.instruction') END END",
        ),
    }[kind]
    items = []
    seen = set()
    with db.connect() as conn:
        rows = conn.execute(
            f"SELECT {column} AS instruction, MAX(created_at) AS last_used FROM {table} "
            f"WHERE typeof({column})='text' AND length({column}) BETWEEN 1 AND 4000 "
            "GROUP BY instruction ORDER BY last_used DESC, instruction ASC"
        )
        for row in rows:
            text = row["instruction"].strip()
            if not text or text in seen:
                continue
            seen.add(text)
            items.append({"instruction": text})
            if len(items) == HISTORY_LIMIT:
                break
    return {"items": items}


@router.get("/artifacts/instruction-history")
def list_instruction_history(request: Request, kind: ArtifactKind):
    # This is user content for the local UI, never diagnostic or telemetry data.
    return instruction_history(request.app.state.db, kind)
