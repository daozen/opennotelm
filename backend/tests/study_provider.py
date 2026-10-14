"""Synthetic study replies for isolated tests; never a model-quality oracle."""

import json


def study_completion(payload):
    system = payload["messages"][0]["content"]
    if not isinstance(system, str) or not system.startswith(
        "Create source-grounded study material"
    ):
        return None
    data = json.loads(payload["messages"][-1]["content"])
    ref = data["registered_evidence"][0]["id"]
    quiz = "single-choice questions" in system
    items = []
    for local_index in range(data["requested_count"]):
        index = len(data.get("already_written_prompts", [])) + local_index
        common = {"id": f"Q{index + 1}", "evidence_ids": [ref]}
        if quiz:
            common.update(
                question=f"Practice question {index + 1}: what supports learning?",
                options=[
                    {"id": key, "text": text}
                    for key, text in zip(
                        "ABCD",
                        ["Practice", "Avoiding reflection", "Stopping", "Ignoring feedback"],
                        strict=True,
                    )
                ],
                correct_option_id="A",
                explanation=(
                    "Practice strengthens learning, while reflection improves the next attempt."
                ),
            )
        else:
            common.update(
                front=f"Recall {index + 1}: what supports learning?",
                back="Practice and reflection support learning.",
            )
        items.append(common)
    return json.dumps({"title": "Practice and reflection", "items": items})
