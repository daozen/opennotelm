"""Safe exact-ID normalization and bounded field updates; no invented references."""

import copy
import json
import re


class FieldValidationError(ValueError):
    def __init__(self, message, paths, *, progress=None, details=None, reason="field_constraint"):
        self.paths = paths
        self.progress = progress
        self.details = details or {}
        self.reason = reason
        super().__init__(message)


class EvidenceValidationError(ValueError):
    def __init__(self, paths, unknown, allowed):
        self.paths = paths
        super().__init__(
            "Unsupported evidence at "
            + json.dumps(paths)
            + "; replace these IDs: "
            + json.dumps(sorted(unknown))
            + "; allowed registered IDs: "
            + json.dumps(sorted(allowed))
        )


def normalize_citations(text, allowed):
    # Recognize only bracketed exact catalog IDs and harmless empty/# link targets.
    # Never guess a numeric reference, edit quotation text, or erase unknown markers.
    for identity in sorted(allowed, key=len, reverse=True):
        token = re.escape(identity)
        pattern = r"\[\s*\[\s*" + token + r"\s*\](?:\((?:#)?\))?\s*\](?:\((?:#)?\))?"
        text = re.sub(pattern, "[[" + identity + "]]", text)
        pattern = r"\[\s*" + token + r"\s*\]\(#\)"
        text = re.sub(pattern, "[[" + identity + "]]", text)
        pattern = r"(?<!\[)\[\s*" + token + r"\s*\](?![\]\(])"
        text = re.sub(pattern, "[[" + identity + "]]", text)
    return text


def json_candidate(output):
    if output.strip().startswith("```"):
        match = re.fullmatch(r"```(?:json)?\s*([\s\S]*?)\s*```", output.strip())
        if match:
            output = match[1]
    return json.loads(output)


def apply_updates(candidate, response, paths=()):
    # A full-schema response remains compatible with gateways that ignore patch mode.
    if not isinstance(response, dict) or set(response) != {"updates"}:
        if not paths or not isinstance(candidate, dict):
            return response
        updates = []
        for path in paths:
            value = response
            for key in path:
                value = value[key]
            updates.append({"path": list(path), "value": value})
        response = {"updates": updates}
    updates = response["updates"]
    if not isinstance(updates, list) or not 1 <= len(updates) <= 64:
        raise ValueError("Return 1-64 field updates")
    result = copy.deepcopy(candidate)
    for update in updates:
        if not isinstance(update, dict) or set(update) != {"path", "value"}:
            raise ValueError("Each update requires path and value")
        path = update["path"]
        if not isinstance(path, list) or not 1 <= len(path) <= 12:
            raise ValueError("Invalid update path")
        if paths and not any(path[: len(p)] == list(p) for p in paths):
            raise ValueError("Update only the diagnosed fields")
        parent = result
        for key in path[:-1]:
            parent = parent[key]
        key = path[-1]
        if isinstance(parent, list):
            if type(key) is not int or not 0 <= key < len(parent):
                raise ValueError("Invalid list update")
        elif not isinstance(parent, dict) or not isinstance(key, str):
            raise ValueError("Invalid field update")
        parent[key] = update["value"]
    return result
