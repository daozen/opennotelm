"""Synthetic structured outputs for protocol tests, never used by the application."""

import json
import re


def deck_completion(payload):
    system = payload["messages"][0]["content"]
    data = json.loads(payload["messages"][-1]["content"])
    english = data.get("output_language", data.get("language")) == "en"
    if system.startswith("Resolve deck content preferences."):
        return {"source_only": False, "include_editorial_notes": False, "dense_text": False}
    if system.startswith("Art-direct the complete illustrated deck"):
        forms = [
            "immersive_scene",
            "object_annotation",
            "spatial_atlas",
            "cutaway_layers",
            "typographic_poster",
            "editorial_collage",
            "relationship_constellation",
            "synthesis_landscape",
        ]
        viewpoints = ["eye_level", "close_up", "overhead", "section", "flat", "isometric"]
        placements = [
            "corner_anchor",
            "distributed_labels",
            "wide_heading",
            "asymmetric_band",
            "central_statement",
            "integrated_panels",
        ]
        layouts = [
            "Let one expansive scene carry the idea, with the title in a quiet corner.",
            "Enlarge one object and distribute labels beside its features.",
            "Organize ideas as places on an overhead atlas under a wide title.",
            "Open a layered section with descriptions aligned beside the exposed parts.",
            "Make the saved statement dominant, balancing type with a restrained subject.",
            "Build an asymmetric collage of meaningful fragments around a central anchor.",
            "Arrange associated subjects around a focal idea with attached explanations.",
            "Connect current ideas in a broad overview with clear reading zones.",
        ]
        return {
            "visual_identity": "Coherent paper illustrations with crisp ink and specific objects.",
            "typography": "Bold normal-width headlines with clear body lettering.",
            "pages": [
                {
                    "index": page["index"],
                    "form": forms[i % len(forms)],
                    "surface": ["dark", "light", "mid_tone"][i % 3],
                    "viewpoint": viewpoints[i % len(viewpoints)],
                    "text_placement": placements[i % len(placements)],
                    "scene": "A conceptual subject specific to the saved message.",
                    "layout": layouts[i % len(layouts)],
                    "reading_path": "Read the headline then the existing explanations in order.",
                    "reason": "This framing explains the message and varies from its neighbor.",
                }
                for i, page in enumerate(data["pages"])
            ],
        }
    if system.startswith("Choose which layer of one slide"):
        instruction = data["instruction"]
        target = (
            "content" if "文字" in instruction else "image" if "图片" in instruction else "visual"
        )
        return {"target": target, "reason": "Synthetic routing decision for the requested layer."}
    if system.startswith("Write one image-generation prompt"):
        return {
            "prompt": "An abstract sedimentary form illustrating gradual accumulation. "
            + data["style"]["image_style"]
            + " Subject: "
            + data["asset_request"]["subject"]
            + " "
            + data.get("revision_instruction", ""),
            "negative_prompt": "No typography, numbers, charts or watermarks.",
        }
    if system.startswith("Design an original visual composition"):
        fragments = data["fragments"]
        palette = data["style"]["palette"]
        body = fragments[1:]
        rows = (len(body) + 1) // 2
        layers = [
            {"type": "background", "fill": palette["background"]},
            {
                "type": "shape",
                "shape": "rectangle",
                "region": {"left": 0.06, "top": 0.20, "width": 0.14, "height": 0.006},
                "fill": palette["accent"],
            },
            {
                "type": "text",
                "content_ref": fragments[0]["id"],
                "region": {"left": 0.06, "top": 0.06, "width": 0.88, "height": 0.12},
                "font_size": 72,
                "min_font_size": 64,
                "font_role": "title",
                "font_weight": 600,
                "color": palette["text"],
            },
        ]
        for index, fragment in enumerate(body):
            layers.append(
                {
                    "type": "text",
                    "content_ref": fragment["id"],
                    "region": {
                        "left": 0.06 + (index % 2) * 0.46,
                        "top": 0.27 + (index // 2) * (0.63 / rows),
                        "width": 0.4,
                        "height": 0.55 / rows,
                    },
                    "font_size": 36 if fragment["role"] != "label" else 28,
                    "min_font_size": fragment.get("min_font_size", 24),
                    "color": palette["text"],
                    "font_role": "body",
                }
            )
        if data["available_assets"]:
            layers.insert(
                2,
                {
                    "type": "image",
                    "asset_ref": data["available_assets"][0],
                    "fit": "contain",
                    "region": {"left": 0.61, "top": 0.27, "width": 0.33, "height": 0.61},
                },
            )
            for index, layer in enumerate(layers[4:]):
                layer["region"] = {
                    "left": 0.06,
                    "top": 0.26 + index * 0.65 / len(body),
                    "width": 0.49,
                    "height": 0.56 / len(body),
                }
                layer["font_size"] = max(34, layer["min_font_size"])
        return {"canvas": {"width": 1920, "height": 1080}, "layers": layers}
    if system.startswith("Create a DeckBrief."):
        return {
            "topic": "Time and learning" if english else "时间与学习",
            "goal": "Understand cumulative learning" if english else "理解长期学习如何积累",
            "audience": "Beginners" if english else "初学者",
            "language": data["language"],
            "slide_count": data["slide_count"],
            "content_principles": ["每页一个核心观点", "所有事实保留出处"],
        }
    if system.startswith("Plan the narrative"):
        refs = list(dict.fromkeys(re.findall(r"\[\[([^\]]+)\]\]", data["understanding"])))
        return {
            "narrative": "From time to practice and action."
            if english
            else "从时间的价值，到持续实践，再回到个人行动。",
            "slides": [
                {
                    "index": index,
                    "title": f"Step {index}: Understand and practice"
                    if english
                    else f"第 {index} 步：理解与实践",
                    "role": "opening" if index == 1 else "explanation",
                    "purpose": "Explain this concept" if english else "帮助读者理解这个概念",
                    "key_message": f"Perspective {index}: Small improvements accumulate."
                    if english
                    else f"第 {index} 个角度：小的进步会随时间积累。",
                    "evidence_ids": [refs[(index - 1) % len(refs)]],
                    "teaching_points": [
                        "Connect accumulation and practice" if english else "解释积累与实践的关系"
                    ],
                    "visual_mode": "illustration" if index == 2 else "diagram",
                    "visual_concept": "层积形态解释累积关系，左侧保留文字阅读区",
                    "visual_grammar": "层积形态展示逐步累积的机制",
                    "reading_budget": 450,
                }
                for index in range(1, data["brief"]["slide_count"] + 1)
            ],
        }
    if system.startswith("Define a unique DeckStyleManifest."):
        style = {
            "concept": "时间沉积的层次",
            "design_rationale": "通过逐层累积的形态解释持续学习。",
            "palette": {
                "background": "#F3EFE6",
                "text": "#233D31",
                "accent": "#9D6B39",
                "secondary": "#CCD5BF",
                "muted": "#667260",
            },
            "typography": {
                "title_family": "Noto Serif CJK SC",
                "body_family": "Noto Sans CJK SC",
                "direction": "清晰的标题与舒缓的阅读节奏",
            },
            "composition": {
                "density": "low",
                "whitespace": "保留宽阔边距",
                "rhythm": "在论点与概念图之间交替",
                "hierarchy": "核心观点优先",
            },
            "image_style": "纸张纹理与抽象的层积形态，不包含文字",
            "motifs": ["层积曲线"],
            "consistency_rules": ["保持色彩与文字层级一致"],
        }
        if "content_context" in data:
            return {
                "style": style,
                "strategy": {
                    "profile": {
                        "content_character": "Learning through cumulative practice.",
                        "communication_task": "Explain how small changes accumulate.",
                        "audience_needs": "A clear conceptual relationship for beginners.",
                        "tone": "Calm and reflective.",
                        "visual_requirements": ["Make accumulated layers understandable."],
                        "user_style_request": "",
                    },
                    "candidates": [
                        {
                            "concept": name,
                            "primary_medium": name,
                            "spatial_language": "mixed",
                            "palette_logic": "Connect color differences to conceptual layers.",
                            "typography": "Readable normal-width type.",
                            "composition_language": "Vary scale and arrange related explanations.",
                            "content_fit": "The visual method explains gradual accumulation.",
                            "tradeoff": "Simplified form may omit unnecessary detail.",
                        }
                        for name in (
                            "Layered drawing",
                            "Vector abstraction",
                            "Photographic montage",
                        )
                    ],
                    "selected_index": 1,
                    "selection_reason": "Layers make the central relationship easy to follow.",
                },
            }
        return style
    if system.startswith("Author one SlideSpec"):
        planned = data["slide_plan"]
        refs = [data["evidence"][0]["id"]]
        # This synthetic provider emits a short display excerpt, not an entire
        # multi-block evidence passage with its source paragraph breaks.
        quote = " ".join(data["evidence"][0]["text"].split())[:100]
        if data.get("previous_slide"):
            planned = {
                **planned,
                "title": planned["title"] + (" (revised)" if english else "（修订）"),
            }
        kind = ["statement", "quote", "comparison", "bullet_list"][planned["index"] % 4]
        element = {"id": "idea", "type": kind, "text": quote, "citations": refs}
        if kind in ("comparison", "bullet_list"):
            element["items"] = [
                {"label": "理解", "text": quote, "citations": refs},
                {"label": "回顾", "text": quote, "citations": refs},
            ]
        return {
            "key_message": planned["key_message"],
            "content_elements": [
                {"id": "heading", "type": "headline", "text": planned["title"]},
                element,
            ],
            "visual_direction": {
                "composition_intent": "以清晰的层次引导阅读",
                "hierarchy": ["heading", "idea"],
                "visual_balance": "文字与留白平衡",
                "image_role": "解释时间积累的隐喻",
                "background_direction": "温暖的浅色纸面",
                "emphasis": "核心观点",
                "density": "low",
                "mood": "沉静、可思考",
            },
            "asset_requests": [
                {
                    "id": "metaphor",
                    "type": "generated_image",
                    "role": "conceptual_illustration",
                    "purpose": "解释时间积累",
                    "subject": "抽象的时间沉积层",
                    "priority": "medium",
                }
            ]
            if planned["index"] == 2
            else [],
        }
    return None
