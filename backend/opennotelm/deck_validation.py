"""Diagnose independent page constraints together; never accept unvalidated JSON."""

import math
import re

from .output_repair import FieldValidationError


def diagnose_page(candidate, *, allowed, budget, dense=False, source_only=False):
    if not isinstance(candidate, dict):
        return []
    errors, fragments = [], []

    def visit(node, path, inherited="source", inherited_citations=()):
        if not isinstance(node, dict):
            return
        basis = node.get("basis") or inherited
        citations = node.get("citations", [])
        references = citations if isinstance(citations, list) else []
        effective = references or inherited_citations
        unknown = [r for r in references if isinstance(r, str) and r not in allowed]
        if unknown:
            errors.append(
                FieldValidationError(
                    "Use only supplied page evidence IDs: " + ", ".join(sorted(allowed)),
                    [path + ["citations"]],
                    reason="evidence",
                )
            )
        if basis in ("background", "analogy") and effective:
            errors.append(
                FieldValidationError(
                    "Model background and illustrative examples cannot "
                    "cite or inherit source evidence. Retain interpretation citations only for a "
                    "reading of actual supplied passages.",
                    [path],
                    reason="citation_basis",
                )
            )
        if source_only and basis in ("background", "analogy"):
            errors.append(
                FieldValidationError(
                    "The user requested source-only content; remove outside elaboration",
                    [path],
                    reason="source_only",
                )
            )
        required = (
            bool(node.get("text"))
            and node.get("type") in ("body", "statement", "quote", "number", "source_note")
            or "type" not in node
            and bool(node.get("text"))
        )
        if required and basis in ("source", "interpretation") and not effective:
            errors.append(
                FieldValidationError(
                    "Source claims and interpretations require supplied passage citations. "
                    "If this is general model knowledge rather than a reading of a supplied "
                    "passage, classify it as background without source citations; "
                    "never invent support.",
                    [path],
                    reason="citation_missing",
                )
            )
        if node.get("type") == "quote" and basis != "source":
            errors.append(
                FieldValidationError(
                    "A quotation must be actual source content, not model elaboration",
                    [path],
                    reason="quote_basis",
                )
            )
        for key in ("text", "label"):
            if isinstance(node.get(key), str) and node[key].strip():
                fragments.append(
                    {
                        "path": path + [key],
                        "units": len(re.findall(r"[\u3400-\u9fff]|[\w]+", node[key])),
                    }
                )
        items = node.get("items")
        if isinstance(items, list):
            for i, item in enumerate(items):
                visit(item, path + ["items", i], basis, effective)

    elements = candidate.get("content_elements")
    if isinstance(elements, list):
        for i, element in enumerate(elements):
            visit(element, ["content_elements", i])
    ids = (
        {
            element["id"]
            for element in elements or []
            if isinstance(element, dict) and isinstance(element.get("id"), str)
        }
        if isinstance(elements, list)
        else set()
    )
    direction = candidate.get("visual_direction")
    hierarchy = direction.get("hierarchy") if isinstance(direction, dict) else None
    if isinstance(hierarchy, list) and any(
        isinstance(ref, str) and ref not in ids for ref in hierarchy
    ):
        errors.append(
            FieldValidationError(
                "Visual hierarchy must reference current content element IDs only; "
                "update it when removing or renaming elements",
                [["visual_direction", "hierarchy"]],
                reason="hierarchy_reference",
            )
        )
    relationships = candidate.get("visual_relationships")
    if isinstance(relationships, list):
        for i, relationship in enumerate(relationships):
            if not isinstance(relationship, dict):
                continue
            basis = relationship.get("basis", "source")
            refs = relationship.get("citations")
            if basis in ("source", "interpretation") and not refs:
                errors.append(
                    FieldValidationError(
                        "A source or interpretation relationship needs passage citations; "
                        "general model reasoning is background and cannot claim source support",
                        [["visual_relationships", i]],
                        reason="citation_missing",
                    )
                )
            if any(
                isinstance(relationship.get(k), str) and relationship[k] not in ids
                for k in ("source_element", "target_element")
            ):
                errors.append(
                    FieldValidationError(
                        "Relationships must reference current content element IDs only",
                        [["visual_relationships", i]],
                        reason="relationship_reference",
                    )
                )
    units = sum(f["units"] for f in fragments)
    ceiling = min(900 if dense else 450, math.ceil(budget * 1.08))
    if budget and units > ceiling:
        errors.append(
            FieldValidationError(
                f"All visible copy has {units} display units; ceiling {ceiling}. "
                f"Target at most {int(budget * 0.75)} TOTAL. "
                "Count every title, label, item and quote. "
                "Keep the central message; do not repeat every teaching point on a closing page. "
                "Preserve element IDs or update hierarchy and relationship references together. "
                "Preserve source qualifications and quoted words; "
                "use shorter exact excerpts if needed.",
                [["content_elements"], ["visual_relationships"], ["visual_direction", "hierarchy"]],
                progress=units - ceiling,
                details={
                    "target_units": int(budget * 0.75),
                    "ceiling": ceiling,
                    "fragments": fragments,
                },
            )
        )
    return errors
