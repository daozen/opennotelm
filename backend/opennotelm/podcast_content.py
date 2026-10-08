"""Spoken editorial contracts and language-aware, approximate duration budgets."""

import math
import re

from .deck_content import GROUNDING
from .languages import LANGUAGE_NAMES

PODCAST_POLICY = GROUNDING + (
    "This is a podcast, not a slide deck. Speak in natural, substantive sentences. "
    "Do not read citation IDs, Markdown, stage directions or speaker labels aloud. "
    "For dialogue, A develops explanations and B contributes meaningful questions, examples "
    "or challenges; both can reason. Avoid constant agreement, repetitive summaries, "
    "fictional credentials, fabricated personal experiences and forced disagreement. "
    "Explain why and how using actual details, rather than merely rephrasing the source. "
    "Integrate relevant background naturally without 'author views' or 'reading boundary' "
    "headings. Explicit user requirements override these style defaults. "
    "Source-derived statements/interpretations need supplied evidence_ids, while background "
    "and illustrative analogies must have no source evidence_ids. Use basis=conversation "
    "for greetings, genuine questions and transitions that make no factual claim; no evidence_ids "
    "are needed for these. Set basis explicitly on every turn. Split mixed turns when their "
    "evidential basis changes. Quotes must be faithful. "
    "Only introduce the episode once, and only conclude it in the final section. "
    "Do not pad with empty banter to reach the time target. If material is thin, explain "
    "mechanisms and useful examples within the user's scope instead of inventing facts. "
)


def language_instruction(language):
    return (
        f"Write ALL generated titles and ALL spoken dialogue in {LANGUAGE_NAMES[language]} "
        f"({language}), regardless of source language. Translate source meaning for listeners; "
        "do not insert long original-language quotations unless the user explicitly requests "
        "bilingual/original-language reading. A translation is not a verbatim quotation. "
        "JSON keys and speaker IDs A/B stay unchanged."
    )


def speaking_budget(minutes, language):
    rate = {"zh-CN": 240, "zh-TW": 240, "ja": 270, "ko": 220, "ru": 130, "ar": 135, "hi": 135}.get(
        language, 145
    )
    count = max(3, min(30, math.ceil(minutes / 2)))
    total = minutes * rate
    return {
        "section_count": count,
        "target_units": total,
        "units_per_section": round(total / count),
        "unit": "characters" if language in ("zh-CN", "zh-TW", "ja", "ko") else "words",
    }


def spoken_units(text, language):
    return (
        len(re.sub(r"\s|[^\w]", "", text))
        if language in ("zh-CN", "zh-TW", "ja", "ko")
        else len(re.findall(r"\S+", text))
    )


def speech_chunks(segments, protocol):
    """Stable semantic groups. Native dialogue can jointly voice several short turns."""
    result = []
    for segment in segments:
        pending, size = [], 0
        for turn_index, turn in enumerate(segment["script"]["turns"]):
            # Unicode-safe sentence splitting keeps every original spoken character.
            remaining, pieces = turn["text"], []
            # Limit spoken time as well as HTTP text size; long CJK turns need smaller chunks.
            maximum = (
                600 if re.search(r"[\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af]", remaining) else 1200
            )
            while remaining:
                end = min(len(remaining), maximum)
                if end < len(remaining):
                    boundaries = list(re.finditer(r"[.!?。！？]\s*", remaining[:end]))
                    if boundaries and boundaries[-1].end() >= maximum // 2:
                        end = boundaries[-1].end()
                pieces.append(remaining[:end])
                remaining = remaining[end:]
            for piece in pieces:
                if pending and (protocol == "openai" or size + len(piece) > maximum):
                    result.append({"segment_id": segment["id"], "turns": pending})
                    pending, size = [], 0
                pending.append(
                    {"speaker": turn["speaker"], "text": piece, "turn_index": turn_index}
                )
                size += len(piece)
        if pending:
            result.append({"segment_id": segment["id"], "turns": pending})
    return result
