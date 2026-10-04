from math import hypot
from typing import Annotated, Literal

from pydantic import Field, model_validator

from .deck_schemas import Color
from .schemas import StrictModel


class Region(StrictModel):
    left: float = Field(ge=0, le=1, allow_inf_nan=False)
    top: float = Field(ge=0, le=1, allow_inf_nan=False)
    width: float = Field(gt=0, le=1, allow_inf_nan=False)
    height: float = Field(gt=0, le=1, allow_inf_nan=False)

    @model_validator(mode="after")
    def in_canvas(self):
        if self.left + self.width > 1.000001 or self.top + self.height > 1.000001:
            raise ValueError("Region extends beyond the canvas")
        return self


class Canvas(StrictModel):
    width: Literal[1920] = 1920
    height: Literal[1080] = 1080


class GradientStop(StrictModel):
    offset: float = Field(ge=0, le=1, allow_inf_nan=False)
    color: Color


class LinearGradient(StrictModel):
    angle: float = Field(default=135, ge=0, le=360, allow_inf_nan=False)
    stops: list[GradientStop] = Field(min_length=2, max_length=5)

    @model_validator(mode="after")
    def ordered(self):
        if [stop.offset for stop in self.stops] != sorted(stop.offset for stop in self.stops):
            raise ValueError("Gradient stops must be ordered")
        return self


class Shadow(StrictModel):
    color: Color
    blur: float = Field(default=12, ge=0, le=48, allow_inf_nan=False)
    x: float = Field(default=0, ge=-24, le=24, allow_inf_nan=False)
    y: float = Field(default=0, ge=-24, le=24, allow_inf_nan=False)
    opacity: float = Field(default=0.5, ge=0, le=1, allow_inf_nan=False)


class ImageFocus(StrictModel):
    x: float = Field(default=0.5, ge=0, le=1, allow_inf_nan=False)
    y: float = Field(default=0.5, ge=0, le=1, allow_inf_nan=False)


class BackgroundLayer(StrictModel):
    type: Literal["background"]
    fill: Color
    gradient: LinearGradient | None = None


class TextLayer(StrictModel):
    type: Literal["text"]
    content_ref: str = Field(min_length=1, max_length=100)
    region: Region
    font_size: int = Field(ge=24, le=240)
    min_font_size: int = Field(default=24, ge=20, le=240)
    font_role: Literal["title", "body"] = "body"
    font_weight: Literal[400, 500, 600, 700, 800, 900] = 400
    color: Color
    align: Literal["left", "center", "right"] = "left"
    shadow: Shadow | None = None
    line_height: float = Field(default=1.3, ge=1, le=2, allow_inf_nan=False)

    @model_validator(mode="after")
    def font_range(self):
        if self.min_font_size > self.font_size:
            raise ValueError("Minimum font size exceeds preferred size")
        return self


class ShapeLayer(StrictModel):
    type: Literal["shape"]
    shape: Literal["rectangle", "ellipse", "line"]
    region: Region
    fill: Color | None = None
    gradient: LinearGradient | None = None
    shadow: Shadow | None = None
    stroke: Color | None = None
    stroke_width: float = Field(default=0, ge=0, le=20, allow_inf_nan=False)
    radius: float = Field(default=0, ge=0, le=80, allow_inf_nan=False)
    opacity: float = Field(default=1, ge=0.05, le=1, allow_inf_nan=False)


class ImageLayer(StrictModel):
    type: Literal["image"]
    asset_ref: str = Field(min_length=1, max_length=100)
    region: Region
    fit: Literal["cover", "contain"] = "contain"
    radius: float = Field(default=0, ge=0, le=80, allow_inf_nan=False)
    focus: ImageFocus = Field(default_factory=ImageFocus)
    opacity: float = Field(default=1, ge=0.05, le=1, allow_inf_nan=False)
    blend_mode: Literal["normal", "multiply", "screen"] = "normal"
    mask: Literal["none", "ellipse"] = "none"


class IconLayer(StrictModel):
    type: Literal["icon"]
    icon: Literal[
        "person",
        "people",
        "gamepad",
        "message",
        "voice",
        "phone",
        "desktop",
        "bell",
        "shield",
        "key",
        "link",
        "alert",
        "document",
        "search",
    ]
    region: Region
    color: Color
    stroke_width: float = Field(default=2, ge=0.5, le=4, allow_inf_nan=False)
    opacity: float = Field(default=1, ge=0.05, le=1, allow_inf_nan=False)
    shadow: Shadow | None = None


class PathPoint(StrictModel):
    x: float = Field(ge=0.02, le=0.98, allow_inf_nan=False)
    y: float = Field(ge=0.02, le=0.98, allow_inf_nan=False)


class PathLayer(StrictModel):
    """Data-only connectors; horizontal/vertical lines need no zero-area box."""

    type: Literal["path"]
    points: list[PathPoint] = Field(min_length=2, max_length=40)
    stroke: Color
    stroke_width: float = Field(default=3, ge=1, le=12, allow_inf_nan=False)
    opacity: float = Field(default=1, ge=0.05, le=1, allow_inf_nan=False)
    arrow_end: bool = False
    arrow_start: bool = False
    smooth: bool = False
    closed: bool = False
    fill: Color | None = None
    shadow: Shadow | None = None
    relationship_ref: str | None = Field(default=None, max_length=64)

    @model_validator(mode="after")
    def arrow_length(self):
        if self.closed and (self.arrow_end or self.arrow_start):
            raise ValueError("Closed paths cannot have arrowheads")
        for a, b in ([self.points[-2:]] if self.arrow_end else []) + (
            [self.points[:2]] if self.arrow_start else []
        ):
            if hypot((b.x - a.x) * 1920, (b.y - a.y) * 1080) < 24:
                raise ValueError("An arrow's final segment must be at least 24 canvas pixels")
        return self


Layer = Annotated[
    BackgroundLayer | TextLayer | ShapeLayer | ImageLayer | IconLayer | PathLayer,
    Field(discriminator="type"),
]


class RenderSpec(StrictModel):
    canvas: Canvas = Field(default_factory=Canvas)
    layers: list[Layer] = Field(min_length=2, max_length=80)

    @model_validator(mode="after")
    def page_structure(self):
        if not isinstance(self.layers[0], BackgroundLayer):
            raise ValueError("Start with one full-canvas background")
        if sum(isinstance(layer, BackgroundLayer) for layer in self.layers) != 1:
            raise ValueError("Use exactly one background")
        refs = [layer.content_ref for layer in self.layers if isinstance(layer, TextLayer)]
        if not refs or len(refs) != len(set(refs)):
            raise ValueError("Text must be present and each content reference unique")
        # Decorative layers must sit behind text, so they cannot silently obscure claims.
        seen_text = False
        for layer in self.layers:
            if isinstance(layer, TextLayer):
                seen_text = True
            elif seen_text:
                raise ValueError("Place all background, shape and image layers before text")
        return self


def content_fragments(spec):
    """Expose semantic text pieces; the composition model never authors page text."""
    fragments = []
    for element in spec.content_elements:
        if element.text.strip():
            fragments.append({"id": element.id, "text": element.text, "role": element.type})
        if element.label.strip():
            fragments.append({"id": element.id + ".label", "text": element.label, "role": "label"})
        for index, item in enumerate(element.items):
            if item.label:
                fragments.append(
                    {"id": f"{element.id}.item{index}.label", "text": item.label, "role": "label"}
                )
            fragments.append(
                {"id": f"{element.id}.item{index}.text", "text": item.text, "role": element.type}
            )
    for fragment in fragments:
        fragment["min_font_size"] = minimum_font_size(fragment)
    return fragments


def minimum_font_size(fragment):
    return {
        "headline": 64,
        "number": 48,
        "body": 32,
        "statement": 32,
        "quote": 32,
        "bullet_list": 32,
        "comparison": 32,
        "subheadline": 32,
        "label": 24,
        "caption": 24,
        "source_note": 24,
    }.get(fragment.get("role"), 20)


def validate_composition(render, fragments, assets):
    issues = []
    by_id = {fragment["id"]: fragment for fragment in fragments}
    try:
        validate_contrast(render, set(by_id))
    except ValueError as error:
        issues.append(str(error))
    text_layers = [layer for layer in render.layers if isinstance(layer, TextLayer)]
    refs = {layer.content_ref for layer in text_layers}
    if refs != set(by_id):
        issues.append(
            "Render every supplied text fragment exactly once; missing supplied refs: "
            f"{sorted(set(by_id) - refs)[:16]}; unknown reference count: {len(refs - set(by_id))}."
        )
    floors = []
    for layer in text_layers:
        if layer.content_ref not in by_id:
            continue
        minimum = minimum_font_size(by_id[layer.content_ref])
        if layer.min_font_size < minimum or layer.font_size < minimum:
            floors.append(f"{layer.content_ref!r} >= {minimum}")
    if floors:
        issues.append(
            "font_size AND min_font_size must obey each fragment's floor: "
            + ", ".join(floors[:12])
            + ". Apply these floors to all text; allocate more reading space."
        )
    if any(
        layer.asset_ref not in assets for layer in render.layers if isinstance(layer, ImageLayer)
    ):
        issues.append("Only use available image asset references")
    overlaps = []
    for index, layer in enumerate(text_layers):
        for other in text_layers[index + 1 :]:
            a, b = layer.region, other.region
            width = min(a.left + a.width, b.left + b.width) - max(a.left, b.left)
            height = min(a.top + a.height, b.top + b.height) - max(a.top, b.top)
            if width > 0.001 and height > 0.001:
                # Never reflect an unknown model-authored reference into system repair
                # instructions. Known references come from the saved semantic schema.
                a_ref = layer.content_ref if layer.content_ref in by_id else "unknown text"
                b_ref = other.content_ref if other.content_ref in by_id else "unknown text"
                overlaps.append(f"{a_ref!r} / {b_ref!r}")
    if overlaps:
        issues.append(
            f"Text regions overlap ({len(overlaps)} pairs): "
            + ", ".join(overlaps[:12])
            + ". Allocate separate non-overlapping regions, including labels."
        )
    if issues:
        raise ValueError("\n".join(issues))


def luminance(color):
    channels = [int(color[index : index + 2], 16) / 255 for index in (1, 3, 5)]
    linear = [
        value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4
        for value in channels
    ]
    return sum(
        value * weight for value, weight in zip(linear, (0.2126, 0.7152, 0.0722), strict=True)
    )


def validate_contrast(render, references=None):
    failures = []
    for index, layer in enumerate(render.layers):
        if not isinstance(layer, TextLayer):
            continue
        region = layer.region
        background = render.layers[0].fill
        image_behind = render.layers[0].gradient is not None
        for visual in render.layers:
            if isinstance(visual, ImageLayer):
                box = visual.region
                if min(box.left + box.width, region.left + region.width) > max(
                    box.left, region.left
                ) and min(box.top + box.height, region.top + region.height) > max(
                    box.top, region.top
                ):
                    image_behind = True
            if (
                isinstance(visual, ShapeLayer)
                and visual.shape == "rectangle"
                and visual.opacity == 1
                and visual.gradient is None
                and visual.fill is not None
            ):
                box = visual.region
                if (
                    box.left <= region.left
                    and box.top <= region.top
                    and box.left + box.width >= region.left + region.width
                    and box.top + box.height >= region.top + region.height
                ):
                    background = visual.fill
                    image_behind = False
        if not image_behind:
            light, dark = sorted((luminance(layer.color), luminance(background)), reverse=True)
            ratio = (light + 0.05) / (dark + 0.05)
            if ratio < 3:
                ref = (
                    layer.content_ref
                    if references and layer.content_ref in references
                    else f"text layer {index}"
                )
                failures.append(f"{ref!r}: {layer.color} on {background} gives {ratio:.2f}")
    if failures:
        raise ValueError(
            "Text has insufficient contrast (requires at least 3): "
            + "; ".join(failures[:12])
            + ". Fix all low-contrast text, using dark ink on light surfaces or light text on dark "
            "surfaces. Reserve low-contrast accents for graphics."
        )


def validate_relationships(render, relationships):
    known = {relationship.id for relationship in relationships}
    refs = [
        layer.relationship_ref
        for layer in render.layers
        if isinstance(layer, PathLayer) and layer.relationship_ref
    ]
    if set(refs) != known or len(refs) != len(set(refs)):
        raise ValueError(
            "Represent each supplied visual relationship exactly once with a path "
            "relationship_ref; do not invent relationships"
        )
