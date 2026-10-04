"""Choose a visual language from communicative needs, without a topic/theme lookup."""

import re
from typing import Literal

from pydantic import Field

from .deck_content import GROUNDING
from .deck_schemas import DeckStyleManifest, Text
from .schemas import StrictModel

STYLE_VERSION = "content-adaptive-style-v1"


class VisualProfile(StrictModel):
    content_character: Text
    communication_task: Text
    audience_needs: Text
    tone: Text
    visual_requirements: list[Text] = Field(min_length=1, max_length=6)
    user_style_request: str = Field(max_length=1000)


class VisualCandidate(StrictModel):
    concept: Text
    primary_medium: Text
    spatial_language: Literal["flat", "dimensional", "mixed"]
    palette_logic: Text
    typography: Text
    composition_language: Text
    content_fit: Text
    tradeoff: Text


class VisualStrategy(StrictModel):
    profile: VisualProfile
    candidates: list[VisualCandidate] = Field(min_length=3, max_length=3)
    selected_index: int = Field(ge=1, le=3)
    selection_reason: Text


class AdaptiveDeckStyle(StrictModel):
    strategy: VisualStrategy
    style: DeckStyleManifest


def enabled(deck):
    return (deck.get("generation_metadata") or {}).get("visual_style_version") == STYLE_VERSION


def selected_direction(deck):
    strategy = (deck.get("generation_metadata") or {}).get("visual_strategy")
    if not enabled(deck) or not strategy:
        return None
    return strategy["candidates"][strategy["selected_index"] - 1]


def validate_style(value):
    # Distinct names cannot verify actual visual difference, but exact duplicate
    # media are an actionable planning error rather than three real alternatives.
    media = [
        re.sub(r"\s+", " ", c.primary_medium.strip().lower()) for c in value.strategy.candidates
    ]
    if len(set(media)) != 3:
        raise ValueError("Compare three materially different primary media, not renamed variants")


def style_data(deck, *, whole_page_images=True):
    return {
        "brief": deck["brief"],
        "user_instruction": deck["instruction"],
        "whole_page_images": whole_page_images,
        "content_context": (deck.get("understanding") or {}).get("content", "")[:16000],
        # Earlier storyboard scenery is provisional. Feeding only semantic needs
        # prevents a scenic planning suggestion from preselecting the art medium.
        "narrative": deck["plan"]["narrative"],
        "pages": [
            {
                key: page.get(key)
                for key in (
                    "index",
                    "title",
                    "role",
                    "purpose",
                    "key_message",
                    "teaching_points",
                    "visual_grammar",
                    "reading_budget",
                )
            }
            for page in deck["plan"]["slides"]
        ],
    }


STYLE_SYSTEM = (
    "Define a unique DeckStyleManifest. "
    + GROUNDING
    + "Choose the deck's visual language from the actual content, communication task, "
    "audience, tone and the user's explicit style requests. First write a short visual "
    "profile: what readers need to understand or feel, what requires precise evidence or "
    "spatial explanation, and what style the user actually requested (empty if none). "
    "Then compare THREE plausible, materially different visual directions for THIS content. "
    "Each candidate needs a distinct primary medium, palette logic, typography, spatial "
    "language, content-specific benefit and tradeoff. Alternatives should differ in visual "
    "method, not merely a new accent color or scenic subject. All must respect explicit "
    "user requests: within a requested medium compare different treatments of that medium. "
    "Choose the best candidate by communicative fit and produce its complete style manifest. "
    "Readability and factual integrity are requirements for EVERY candidate, not reasons to "
    "always select the least expressive vector diagram. Give equal consideration to the "
    "source's rhetorical character, emotional atmosphere and the user's intended reading "
    "experience. Dense Chinese text does not by itself select a medium. Poetic metaphor, "
    "documentary evidence, personal narrative and analytical classification call for "
    "different treatments even when each contains conceptual relationships. Photographic "
    "or painterly conceptual imagery is allowed without claiming to document actual events; "
    "do not reject those candidates simply because the source contains metaphors. "
    "Make the selection_reason explain the decisive content-specific tradeoff beyond "
    "generic clarity. Derive palette logic from the particular mood, subject associations "
    "and semantic emphasis, rather than a universal teal/coral or cream/earth palette. "
    "The final style must implement the selected medium and palette logic, with no default "
    "warm paper, vintage illustration, watercolor, earth-tone palette or scenic opening. "
    "Those are options only when justified by this content. Graphic/vector abstraction, "
    "photographic composition, documentary montage, scientific drawing, typographic design, "
    "painterly imagery, restrained dimensional models or other media are equally valid "
    "possibilities; this is an open vocabulary, not a preset theme list. No fixed mapping "
    "from topic to style: technology is not always neon, philosophy is not always antique "
    "paper, and business is not always a corporate chart. Neon, panels and flat grids can "
    "be useful when purposefully justified; avoid making them a universal default. "
    "Distinguish medium and art direction from explanatory form. A diagram can be drawn "
    "as vector geometry, a photographic annotation or ink; a page form must not silently "
    "switch the chosen medium to storybook illustration. Prior visual_grammar is context "
    "for explanatory relationships, not an obligation to paint scenery or objects. "
    "Design palette, typography, composition, image_style, selective motifs and consistency "
    "rules as one recognizable identity. Explain how those choices support THIS material. "
    "Keep foreground/background contrast and normal-width body text readable. Use installed "
    "Latin font family names such as Noto Sans CJK SC or Noto Serif CJK SC. "
    "Vary page composition and focal scale within the identity; do not require changing "
    "camera angles in an intentionally flat system. Allow negative space and text-led pages "
    "without an obligatory illustration. Lighting, depth and tactile textures are optional, "
    "not required invariants. The manifest must clearly state its primary medium and how "
    "other visual methods can complement it without homogenizing it. If whole_page_images "
    "is true, generation includes ALL typography; never request text-free art or later "
    "overlays. Otherwise illustration assets must leave quiet text-free regions for native "
    "typography; the same chosen visual identity still applies. "
    "Do not write slide copy or print this internal assessment on the pages. Keep profile, "
    "candidates and rationales concise, with one or two sentences per field."
)
