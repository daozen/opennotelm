"""Deterministic source-grounded podcast replies for isolated browser tests."""

import json


def podcast_completion(payload):
    system = payload["messages"][0]["content"]
    prompt = payload["messages"][-1]["content"]
    if not isinstance(system, str) or not system.startswith(
        (
            "Resolve only the explicit",
            "Create a useful, well-structured reading dossier",
            "Plan a coherent podcast",
            "Write one complete podcast",
        )
    ):
        return None
    data = json.loads(prompt)
    if system.startswith("Resolve only the explicit"):
        value = {"source_only": False, "chapter_only": False}
    elif system.startswith("Create a useful"):
        return "# Reading\n" + "\n".join(f"{e['text']}[[{e['id']}]]" for e in data["material"])
    elif system.startswith("Plan a coherent"):
        value = {
            "title": "Learning through practice",
            "sections": [
                {
                    "title": f"Part {i + 1}",
                    "focus": "Explain effective practice",
                    "evidence_ids": [data["registered_evidence"][0]["id"]],
                }
                for i in range(data["speaking_budget"]["section_count"])
            ],
        }
    else:
        value = {
            "turns": [
                {
                    "speaker": "A",
                    "text": f"Section {data['section_index'] + 1}: practice supports learning.",
                    "basis": "source",
                    "evidence_ids": [data["original_evidence"][0]["id"]],
                },
                {
                    "speaker": "B",
                    "text": "For example, a learner can review the work after a short break.",
                    "basis": "analogy",
                    "evidence_ids": [],
                },
            ]
        }
        if data["format"] == "solo":
            value["turns"] = value["turns"][:1]
    return json.dumps(value)
