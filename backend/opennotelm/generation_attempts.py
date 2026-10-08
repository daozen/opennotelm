"""Task-local, content-free generation diagnostics, safe under concurrent requests."""

import json
import re
import time
from contextvars import ContextVar

from pydantic import ValidationError

from .error_codes import safe_error_code
from .output_repair import EvidenceValidationError, FieldValidationError

SAFE_FIELDS = {
    "sections",
    "nodes",
    "parent_id",
    "detail",
    "turns",
    "speaker",
    "focus",
    "title",
    "slides",
    "pages",
    "form",
    "surface",
    "viewpoint",
    "text_placement",
    "scene",
    "layout",
    "reading_path",
    "reason",
    "visual_identity",
    "typography",
    "source_element",
    "target_element",
    "id",
    "index",
    "evidence_ids",
    "language",
    "slide_count",
    "topic",
    "goal",
    "audience",
    "content_principles",
    "content_elements",
    "text",
    "label",
    "items",
    "citations",
    "basis",
    "type",
    "key_message",
    "visual_direction",
    "asset_requests",
    "visual_relationships",
    "reading_budget",
    "visual_concept",
    "visual_grammar",
    "teaching_points",
    "hierarchy",
    "narrative",
    "composition_intent",
}


REASONS = {
    "field_constraint",
    "copy_budget",
    "citation_basis",
    "source_only",
    "evidence",
    "json_invalid",
    "semantic",
    "citation_primary_missing",
    "output_truncated",
    "output_tokens",
    "output_bytes",
    "synthesis_insufficient",
    "art_order",
    "art_unsupported_form",
    "art_variety",
    "art_adjacency",
    "art_frequency",
    "art_viewpoints",
    "art_placements",
    "art_framing",
    "art_layouts",
}
SCHEMA_CODES = {
    "missing",
    "extra_forbidden",
    "string_too_long",
    "string_too_short",
    "too_long",
    "too_short",
    "literal_error",
    "string_type",
    "list_type",
    "dict_type",
    "int_type",
    "int_parsing",
    "greater_than_equal",
    "less_than_equal",
    "string_pattern_mismatch",
    "model_type",
    "value_error",
    "json_invalid",
    "bool_type",
    "bool_parsing",
}
SEMANTIC_REASONS = {
    "Solo narration uses speaker A only": "podcast_speaker",
    "Use only supplied evidence IDs": "evidence",
    "Source content requires passage evidence IDs": "citation_missing",
    "Background, analogies and conversation must not claim source citations": "citation_basis",
    "Put evidence IDs in evidence_ids, never in spoken text": "podcast_spoken_citation",
    "Each section needs source-grounded content": "citation_missing",
    "The user requested source-only content; remove outside elaboration": "source_only",
    "This element requires structured items": "element_items",
    "This element requires text": "element_text",
    "Element IDs must be unique": "element_ids",
    "Visual hierarchy references unknown content": "hierarchy_reference",
    "Visual relationships must refer to saved content elements": "relationship_reference",
    "Only a cycle may connect an element to itself": "relationship_cycle",
    "Asset request IDs must be unique": "asset_ids",
    "Visual relationship IDs must be unique": "relationship_ids",
    "Source content and interpretations need supplied passage citations": "citation_missing",
    "A quotation must be actual source content, not model elaboration": "quote_basis",
    "Remove unsolicited author-opinion/interpretation-boundary copy": "editorial_notes",
    "The page needs at least one supplied original-source citation": "citation_missing",
}
REASONS.update(SEMANTIC_REASONS.values())


def safe_path(path):
    return isinstance(path, (tuple, list)) and all(
        (type(k) is int and 0 <= k <= 10000) or (isinstance(k, str) and k in SAFE_FIELDS)
        for k in path
    )


def safe_validation(errors):
    paths, codes, issues = [], [], []
    for error in errors:
        if isinstance(error, ValidationError):
            codes.append("schema")
            for value in error.errors(include_input=False, include_url=False):
                path = list(value["loc"]) if safe_path(value["loc"]) else []
                code = value["type"] if value["type"] in SCHEMA_CODES else "schema"
                ctx = value.get("ctx") or {}
                reason = SEMANTIC_REASONS.get(str(ctx.get("error")), code)
                issues.append(
                    {
                        "code": reason,
                        "path": path,
                        **{
                            k: v
                            for k, v in ctx.items()
                            if k in ("max_length", "min_length", "actual_length", "ge", "le")
                            and type(v) in (int, float)
                            and 0 <= v <= 10_000_000
                        },
                    }
                )
            locations = [e["loc"] for e in error.errors()]
        else:
            code = (
                "evidence"
                if isinstance(error, EvidenceValidationError)
                else "field"
                if isinstance(error, FieldValidationError)
                else "semantic"
            )
            codes.append(code)
            locations = getattr(error, "paths", ())
            reason = (
                "json_invalid"
                if isinstance(error, json.JSONDecodeError)
                else "evidence"
                if isinstance(error, EvidenceValidationError)
                else "copy_budget"
                if isinstance(error, FieldValidationError)
                and error.progress is not None
                and error.reason not in ("output_tokens", "output_bytes")
                else SEMANTIC_REASONS.get(str(error), getattr(error, "reason", "semantic"))
            )
            issue = {
                "code": reason if reason in REASONS else "semantic",
                "path": next((list(p) for p in locations if safe_path(p)), []),
                **(
                    {
                        "max_length": error.details["ceiling"],
                        "actual_length": error.details["ceiling"] + error.progress,
                    }
                    if isinstance(error, FieldValidationError)
                    and type(error.details.get("ceiling")) is int
                    and type(error.progress) is int
                    else {}
                ),
            }
            if isinstance(error, FieldValidationError) and reason == "art_layouts":
                for name in ("max_length", "actual_length"):
                    value = error.details.get(name)
                    if type(value) is int and 0 <= value <= 10_000_000:
                        issue[name] = value
                issues.extend({**issue, "path": list(p)} for p in locations if safe_path(p))
            else:
                issues.append(issue)
        paths.extend(list(p) for p in locations if safe_path(p))
    return {
        "validation_codes": list(dict.fromkeys(codes)),
        "field_paths": paths[:32],
        "issues": issues[:32],
    }


def safe_attempt(data):
    """Whitelist again on export, including old or manually corrupted metadata."""
    if not isinstance(data, dict):
        return {}

    def values(key):
        return data[key] if isinstance(data.get(key), list) else []

    result = {
        key: data[key]
        for key in (
            "attempt",
            "elapsed_ms",
            "images",
            "validation_error_count",
            "prompt_tokens",
            "completion_tokens",
            "total_tokens",
            "http_status",
        )
        if type(data.get(key)) is int and 0 <= data[key] <= 100_000_000
    }
    for key, allowed in {
        "outcome": {"valid", "invalid", "request_failed", "visual_cache_hit"},
        "finish_reason": {"stop", "length", "content_filter", "tool_calls", "unknown"},
    }.items():
        if isinstance(data.get(key), str) and data[key] in allowed:
            result[key] = data[key]
    if isinstance(data.get("error_code"), str):
        result["error_code"] = safe_error_code(data["error_code"])
    if isinstance(data.get("subject_id"), str) and re.fullmatch(
        r"[0-9a-f]{32}", data["subject_id"]
    ):
        result["subject_id"] = data["subject_id"]
    result["normalized_citations"] = data.get("normalized_citations") is True
    result["validation_codes"] = [
        v
        for v in values("validation_codes")
        if isinstance(v, str) and v in {"schema", "evidence", "field", "semantic"}
    ][:32]
    result["field_paths"] = [p for p in values("field_paths") if safe_path(p)][:32]
    result["issues"] = []
    for issue in values("issues")[:32]:
        if not isinstance(issue, dict):
            continue
        code = issue.get("code")
        result["issues"].append(
            {
                "code": code
                if isinstance(code, str) and code in REASONS | SCHEMA_CODES | {"schema"}
                else "semantic",
                "path": issue.get("path", []) if safe_path(issue.get("path")) else [],
                **{
                    k: v
                    for k, v in issue.items()
                    if k in ("max_length", "min_length", "actual_length", "ge", "le")
                    and type(v) in (int, float)
                    and 0 <= v <= 10_000_000
                },
            }
        )
    return result


JOB_DIAGNOSTICS = ContextVar("generation_job_diagnostics", default=None)
RESPONSE_METADATA = ContextVar("generation_response_metadata", default=None)


def record_attempt(
    stage,
    started,
    attempt,
    *,
    outcome,
    errors=(),
    images=0,
    normalized=False,
    subject_id=None,
    error_code=None,
):
    target = JOB_DIAGNOSTICS.get()
    if not target:
        return
    db, job_id = target
    # Only known categories/counts: never persist prompts, source text or rejected values.
    data = {
        "attempt": attempt,
        "subject_id": subject_id,
        "error_code": error_code,
        "elapsed_ms": round((time.monotonic() - started) * 1000),
        "outcome": outcome,
        "validation_error_count": len(errors),
        "images": images,
        **((RESPONSE_METADATA.get() or {}) if attempt else {}),
        "normalized_citations": normalized,
        **safe_validation(errors),
    }
    with db.connect() as conn:
        conn.execute(
            "INSERT INTO generation_attempts(job_id,stage,metadata_json) VALUES (?,?,?)",
            (job_id, stage, json.dumps(safe_attempt(data))),
        )
