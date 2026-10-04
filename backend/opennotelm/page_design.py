"""Persist a page composition before generating its raster artwork."""

import hashlib
import json
from uuid import uuid4

from .deck_schemas import SlideSpec
from .errors import AppError
from .model_service import now
from .render_schemas import (
    IconLayer,
    ImageLayer,
    PathLayer,
    RenderSpec,
    TextLayer,
    content_fragments,
    validate_composition,
    validate_relationships,
)
from .structured import structured_completion

DESIGN_VERSION = "page-design-v1"
GENERATION_VERSION = "deck-content-v3"


def reading_layout(render):
    """Keep repairs inside the configured context without losing relationship geometry."""
    return [
        layer.model_dump(exclude_defaults=True, exclude_none=True)
        for layer in render.layers
        if layer.type in ("background", "text", "image")
        or (layer.type == "path" and layer.relationship_ref)
    ]


def design_signature(deck, slide):
    # An image-only revision increments both counters and preserves the layout.
    data = {
        "spec": json.loads(slide["spec_json"]),
        "style": deck["style"],
        "version": DESIGN_VERSION,
        "layout_revision": slide["visual_revision"] - slide["image_revision"],
        "instruction": slide["visual_instruction"],
    }
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


def asset_frame(design, request_id):
    """Express reading zones in artwork-local coordinates, without page words."""
    image = next(
        (
            layer
            for layer in design.layers
            if isinstance(layer, ImageLayer) and layer.asset_ref == request_id
        ),
        None,
    )
    if not image:
        return None
    region = image.region
    zones = []
    for layer in design.layers:
        if not isinstance(layer, TextLayer):
            continue
        text = layer.region
        left, top = max(region.left, text.left), max(region.top, text.top)
        right = min(region.left + region.width, text.left + text.width)
        bottom = min(region.top + region.height, text.top + text.height)
        if right > left and bottom > top:
            zones.append(
                {
                    "left": round((left - region.left) / region.width, 4),
                    "top": round((top - region.top) / region.height, 4),
                    "width": round((right - left) / region.width, 4),
                    "height": round((bottom - top) / region.height, 4),
                    "text_color": layer.color,
                }
            )
    overlays = []
    for layer in design.layers:
        if isinstance(layer, PathLayer) and all(
            region.left <= point.x <= region.left + region.width
            and region.top <= point.y <= region.top + region.height
            for point in layer.points
        ):
            overlays.append(
                {
                    "kind": "connector",
                    "points": [
                        {
                            "x": round((point.x - region.left) / region.width, 4),
                            "y": round((point.y - region.top) / region.height, 4),
                        }
                        for point in layer.points
                    ],
                    "color": layer.stroke,
                    "smooth": layer.smooth,
                    "arrow_start": layer.arrow_start,
                    "arrow_end": layer.arrow_end,
                }
            )
        elif isinstance(layer, IconLayer):
            box = layer.region
            if (
                region.left <= box.left
                and region.top <= box.top
                and box.left + box.width <= region.left + region.width
                and box.top + box.height <= region.top + region.height
            ):
                overlays.append(
                    {
                        "kind": "pictogram",
                        "symbol": layer.icon,
                        "color": layer.color,
                        "region": {
                            "left": round((box.left - region.left) / region.width, 4),
                            "top": round((box.top - region.top) / region.height, 4),
                            "width": round(box.width / region.width, 4),
                            "height": round(box.height / region.height, 4),
                        },
                    }
                )
    return {
        "aspect_ratio": round(region.width * 1920 / (region.height * 1080), 4),
        "page_region": region.model_dump(),
        "fit": image.fit,
        "blend_mode": image.blend_mode,
        "page_background": design.layers[0].fill,
        "quiet_zones": zones,
        "native_overlays": overlays,
        "coordinate_system": "normalized 0-1 inside this artwork, NOT the whole page",
    }


class PageDesignService:
    def __init__(self, db, models, renderer, system, color_options):
        self.db, self.models, self.renderer = db, models, renderer
        self.system, self.color_options = system, color_options

    def current(self, deck, slide):
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT design_json FROM slide_designs WHERE slide_id=? AND input_hash=?",
                (slide["id"], design_signature(deck, slide)),
            ).fetchone()
        return RenderSpec.model_validate_json(row[0]) if row else None

    def enabled(self, deck, slide):
        if (deck.get("generation_metadata") or {}).get("generation_version") == GENERATION_VERSION:
            return True
        with self.db.connect() as conn:
            return bool(
                conn.execute(
                    "SELECT 1 FROM slide_designs WHERE slide_id=? LIMIT 1", (slide["id"],)
                ).fetchone()
            )

    async def prepare(self, deck, slide):
        if not self.enabled(deck, slide):
            return None
        cached = self.current(deck, slide)
        if cached:
            return cached
        spec = SlideSpec.model_validate_json(slide["spec_json"])
        fragments = content_fragments(spec)
        requests = {request.id: request for request in spec.asset_requests}
        with self.db.connect() as conn:
            previous = conn.execute(
                "SELECT design_json FROM slide_designs WHERE slide_id=? "
                "ORDER BY rowid DESC LIMIT 1",
                (slide["id"],),
            ).fetchone()
            neighbors = conn.execute(
                "SELECT x.design_json FROM slide_designs x JOIN slides s ON s.id=x.slide_id "
                "WHERE s.deck_id=? AND s.ordinal<? ORDER BY s.ordinal DESC,x.rowid DESC LIMIT 4",
                (deck["id"], slide["ordinal"]),
            ).fetchall()
        data = {
            "style": deck["style"],
            "text_color_options": self.color_options(deck["style"]),
            "visual_direction": spec.visual_direction.model_dump(),
            "key_message": spec.key_message,
            "storyboard": json.loads(slide["plan_json"]),
            "fragments": fragments,
            "visual_relationships": [
                relationship.model_dump() for relationship in spec.visual_relationships
            ],
            "available_assets": list(requests),
            "asset_descriptions": [request.model_dump() for request in requests.values()],
            "revision_instruction": slide["visual_instruction"],
            "design_stage": "before artwork generation: asset IDs refer to planned image frames",
            "previous_reading_layout": reading_layout(RenderSpec.model_validate_json(previous[0]))
            if previous
            else None,
            "recent_page_rhythm": [
                self.rhythm(RenderSpec.model_validate_json(row[0])) for row in neighbors
            ],
        }

        def validate(render):
            validate_composition(render, fragments, requests)
            validate_relationships(render, spec.visual_relationships)
            refs = [layer.asset_ref for layer in render.layers if isinstance(layer, ImageLayer)]
            if set(refs) != set(requests) or len(refs) != len(set(refs)):
                raise ValueError(
                    "Give every requested artwork exactly one image frame before generation"
                )

        system = (
            self.system
            + """
This is PAGE ART DIRECTION BEFORE image generation, not arranging an existing stock image.
Design an integrated explanatory page: text labels, native curved arrows, cycles, contrasts
and artwork should work together. Execute visual_grammar and the core explanatory relation.
Images will be generated for the exact frames you choose. The image generator will receive
their aspect ratios and quiet reading zones. This removes the need for a text column next to
an unrelated picture. Use large artwork where the concept calls for it; native graphics can
provide precise structure over or beside that artwork. No screenshots, logos or benchmark art.
When visual_relationships are supplied, draw each exactly once with a path relationship_ref.
Keep their meaning and direction. Other paths are decoration only, never invented data traces.
Use smooth paths, closed filled paths, gradient backgrounds, restrained shadows/glow, image
focus/mask/blend where they support this page's visual world. These are drawing primitives,
not a mandated style. Avoid gratuitous effects and avoid a row of generic cards.
Use recent_page_rhythm to avoid consecutive pages with the same dominant picture location,
reading surface and visual scale. Coordinate typography, materials and symbolic language.
For a text edit, preserve the previous geometry where it still fits. A visual-only revision
keeps existing artwork; respect its original content rather than assuming it can be repainted.
Do not use font shrinking to compensate for too much content. Allocate generous label zones.
"""
        )
        for attempt in range(2):
            render = await structured_completion(
                self.models, system, data, RenderSpec, validate=validate, output_limit=8000
            )
            feedback = (
                await self.renderer.preflight(render, fragments, deck["style"])
                if hasattr(self.renderer, "preflight")
                else []
            )
            if not feedback:
                break
            if attempt:
                error = AppError(
                    "RENDER_LAYOUT_INVALID",
                    "The page design does not fit its text. Retry visual generation.",
                    502,
                )
                error.layout_feedback = feedback
                raise error
            data["previous_reading_layout"] = reading_layout(render)
            data["layout_feedback"] = feedback
        with self.db.connect() as conn:
            current = conn.execute(
                "SELECT revision FROM slides WHERE id=?", (slide["id"],)
            ).fetchone()
            if not current or current[0] != slide["revision"]:
                raise AppError(
                    "SLIDE_CHANGED", "The slide changed during page design. Retry its visual.", 409
                )
            conn.execute(
                "INSERT OR IGNORE INTO slide_designs VALUES (?,?,?,?,?,?)",
                (
                    uuid4().hex,
                    slide["id"],
                    design_signature(deck, slide),
                    render.model_dump_json(),
                    DESIGN_VERSION,
                    now(),
                ),
            )
        return render

    @staticmethod
    def rhythm(render):
        images = [layer for layer in render.layers if isinstance(layer, ImageLayer)]
        largest = max(
            images, key=lambda layer: layer.region.width * layer.region.height, default=None
        )
        return {
            "background": render.layers[0].fill,
            "image_area": round(
                sum(layer.region.width * layer.region.height for layer in images), 2
            ),
            "dominant_image_region": largest.region.model_dump() if largest else None,
            "native_paths": sum(layer.type == "path" for layer in render.layers),
        }
