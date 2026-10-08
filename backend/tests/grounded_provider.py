"""Deterministic provider with real evidence IDs, used only in tests."""

import json

from deck_provider import deck_completion
from mindmap_provider import mindmap_completion
from podcast_provider import podcast_completion
from vision_factory import vision_completion


def embedding(text: str) -> list[float]:
    return [
        1.0 if any(word in text for word in ("时间", "复利")) else 0.1,
        1.0 if any(word in text for word in ("耐心", "回顾")) else 0.1,
        0.2,
    ]


def completion(payload: dict) -> str:
    mindmap = mindmap_completion(payload)
    if mindmap is not None:
        return mindmap
    podcast = podcast_completion(payload)
    if podcast is not None:
        return podcast
    visual = vision_completion(payload)
    if visual:
        return visual
    messages = payload["messages"]
    prompt = messages[-1]["content"]
    if messages[0]["content"].startswith(
        (
            "Resolve deck content preferences.",
            "Create a DeckBrief.",
            "Plan the narrative",
            "Define a unique DeckStyleManifest.",
            "Author one SlideSpec",
            "Design an original visual composition",
            "Write one image-generation prompt",
            "Choose which layer of one slide",
            "Art-direct the complete illustrated deck",
        )
    ):
        return json.dumps(deck_completion(payload), ensure_ascii=False)
    if messages[0]["content"].startswith("Create a useful, well-structured knowledge page"):
        data = json.loads(prompt)
        material = data["material"]
        chosen = material if len(material) <= 2 else [material[0], material[-1]]
        compound = next((item for item in material if "长期复利最大的优势" in item["text"]), None)
        if compound and compound not in chosen:
            chosen.insert(1, compound)
        lines = []
        for item in chosen:
            if "id" in item:
                lines.append(f"{item['text'][:80]}[[{item['id']}]]")
            else:
                lines.append(f"Summarized insight [[{item['evidence_ids'][0]}]]")
        return "# 资料中的关键理解\n\n" + "\n\n".join(lines)
    if messages[0]["content"].startswith("Update the existing knowledge page"):
        data = json.loads(prompt)
        return json.dumps({"additions_markdown": data["new_source_synthesis"], "replacements": []})
    if "EVIDENCE_JSON\n" in prompt:
        data = json.loads(prompt.split("EVIDENCE_JSON\n", 1)[1].rsplit("\nEND_EVIDENCE_JSON", 1)[0])
        evidence = data["evidence"]
        item = next((e for e in evidence if "长期复利最大的优势" in e["text"]), None)
        item = item or next(
            (e for e in evidence if "耐心意味着" in e["text"]),
            max(evidence, key=lambda e: len(e["text"])),
        )
        return f"{item['text']}[[{item['id']}]]"
    if messages[0]["content"].startswith("Fix citation markers"):
        data = json.loads(prompt)
        return data["answer"] + f"[[{data['evidence'][0]['id']}]]"
    return '{"ok":true}'
