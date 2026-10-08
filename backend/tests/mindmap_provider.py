"""Deterministic concept trees for isolated tests only."""

import json


def mindmap_completion(payload):
    system = payload["messages"][0]["content"]
    if not isinstance(system, str) or not system.startswith("Create a concept mind map"):
        return None
    data = json.loads(payload["messages"][-1]["content"])
    ref = data["registered_evidence"][0]["id"]
    nodes = [
        {
            "id": "root",
            "parent_id": None,
            "label": "Learning through practice",
            "detail": "",
            "basis": "structural",
            "evidence_ids": [],
        },
        {
            "id": "practice",
            "parent_id": "root",
            "label": "Practice",
            "detail": "Practice strengthens learning.",
            "basis": "source",
            "evidence_ids": [ref],
        },
        {
            "id": "reflect",
            "parent_id": "root",
            "label": "Reflection",
            "detail": "Reflection improves the next attempt.",
            "basis": "interpretation",
            "evidence_ids": [ref],
        },
        {
            "id": "review",
            "parent_id": "reflect",
            "label": "Review the attempt",
            "detail": "Compare the result with the intended goal.",
            "basis": "interpretation",
            "evidence_ids": [ref],
        },
    ]
    if not data["preferences"].get("source_only"):
        nodes.append(
            {
                "id": "analogy",
                "parent_id": "practice",
                "label": "Like learning a musical phrase",
                "detail": "For example, slow practice helps reveal small mistakes.",
                "basis": "analogy",
                "evidence_ids": [],
            }
        )
    return json.dumps({"title": "Learning through practice", "nodes": nodes})
