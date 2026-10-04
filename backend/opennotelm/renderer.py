"""Deterministic rendering of validated data; document/model HTML never reaches Chromium."""

import base64
import html
import json
import re
from io import BytesIO
from pathlib import Path

from PIL import Image
from playwright.async_api import Error as BrowserError
from playwright.async_api import async_playwright

from .errors import AppError
from .icons import ICONS
from .render_schemas import (
    BackgroundLayer,
    IconLayer,
    ImageLayer,
    PathLayer,
    ShapeLayer,
    TextLayer,
    luminance,
    validate_composition,
)

RENDERER_VERSION = "chromium-page-v6"


def painted_contrast_feedback(render, text_layer, background):
    """Check every text line against the painted page, including partial panels."""
    colors = {
        layer.content_ref: luminance(layer.color)
        for layer in render.layers
        if isinstance(layer, TextLayer)
    }
    feedback = []
    for item in text_layer:
        foreground = colors[item["content_ref"]]
        worst_fraction = 0
        for line in item["lines"]:
            left, top, right, bottom = line["bbox"]
            bad = 0
            for column in range(16):
                for row in range(4):
                    x = min(1919, max(0, int(left + (right - left) * (column + 0.5) / 16)))
                    y = min(1079, max(0, int(top + (bottom - top) * (row + 0.5) / 4)))
                    red, green, blue = background.getpixel((x, y))
                    behind = luminance(f"#{red:02x}{green:02x}{blue:02x}")
                    light, dark = sorted((foreground, behind), reverse=True)
                    bad += (light + 0.05) / (dark + 0.05) < 3
            worst_fraction = max(worst_fraction, bad / 64)
        if worst_fraction > 0.1:
            feedback.append(
                {
                    "content_ref": item["content_ref"],
                    "reason": "low_contrast_on_painted_background",
                    "low_contrast_fraction": round(worst_fraction, 2),
                    "correction": "Move text to a calm high-contrast area, move crossing "
                    "graphics, or add an opaque "
                    "reading panel behind the entire text region. At least 90% of sampled "
                    "background pixels per line must provide contrast of 3 or higher.",
                }
            )
    return feedback


def connector_feedback(crossings, painted, without_connectors):
    """Only flag geometry that is actually visible through the reading line."""
    feedback = []
    for crossing in crossings:
        for x, y in crossing["points"]:
            point = (min(1919, max(0, round(x))), min(1079, max(0, round(y))))
            before, after = painted.getpixel(point), without_connectors.getpixel(point)
            if max(abs(a - b) for a, b in zip(before, after, strict=True)) > 12:
                feedback.append(
                    {
                        "content_ref": crossing["content_ref"],
                        "reason": "connector_crosses_reading_text",
                        "path_index": crossing["path_index"],
                        "correction": "Reroute this connector around reading lines, "
                        "with clear space "
                        "beside the label. Preserve the relationship and its direction. An opaque "
                        "reading surface can hide an intentional background path.",
                    }
                )
                break
    return feedback


def font_stack(family):
    family = family if re.fullmatch(r"[A-Za-z0-9 _-]{1,100}", family) else "Noto Sans CJK SC"
    if "serif" in family.lower() and "sans" not in family.lower():
        return f'"{family}","Noto Serif CJK SC","Songti SC","STSong",serif'
    return f'"{family}","Noto Sans CJK SC","PingFang SC","Microsoft YaHei",sans-serif'


def rgba(color, opacity):
    rgb = [int(color[i : i + 2], 16) for i in (1, 3, 5)]
    return f"rgba({rgb[0]},{rgb[1]},{rgb[2]},{opacity})"


def gradient_css(gradient, fallback):
    if not gradient:
        return fallback or "transparent"
    stops = ",".join(f"{stop.color} {stop.offset * 100:.3f}%" for stop in gradient.stops)
    return f"linear-gradient({gradient.angle}deg,{stops})"


def shadow_css(shadow):
    return f"{shadow.x}px {shadow.y}px {shadow.blur}px {rgba(shadow.color, shadow.opacity)}"


def path_data(layer, width, height):
    points = [(p.x * width, p.y * height) for p in layer.points]
    result = [f"M {points[0][0]:.3f} {points[0][1]:.3f}"]
    count = len(points)
    for index in range(count if layer.closed else count - 1):
        a, b = points[index], points[(index + 1) % count]
        if layer.smooth:
            previous = points[(index - 1) % count] if layer.closed else points[max(0, index - 1)]
            following = (
                points[(index + 2) % count] if layer.closed else points[min(count - 1, index + 2)]
            )
            controls = [
                (a[j] + (b[j] - previous[j]) / 6, b[j] - (following[j] - a[j]) / 6) for j in (0, 1)
            ]
            # Keep Bezier control points bounded too; model input is never SVG code.
            x1, x2 = [max(width * 0.02, min(width * 0.98, v)) for v in controls[0]]
            y1, y2 = [max(height * 0.02, min(height * 0.98, v)) for v in controls[1]]
            result.append(f"C {x1:.3f} {y1:.3f} {x2:.3f} {y2:.3f} {b[0]:.3f} {b[1]:.3f}")
        else:
            result.append(f"L {b[0]:.3f} {b[1]:.3f}")
    if layer.closed:
        result.append("Z")
    return " ".join(result)


def fragment_html(render, fragments, style, assets):
    validate_composition(render, fragments, assets)
    width, height = render.canvas.width, render.canvas.height
    texts = {fragment["id"]: fragment["text"] for fragment in fragments}
    layers = []
    for index, layer in enumerate(render.layers):
        if isinstance(layer, BackgroundLayer):
            layers.append(
                f'<div style="position:absolute;inset:0;'
                f'background:{gradient_css(layer.gradient, layer.fill)}"></div>'
            )
            continue
        if isinstance(layer, PathLayer):
            marker = (
                f'<defs><marker id="arrow-{index}" markerUnits="userSpaceOnUse" '
                'markerWidth="24" markerHeight="24" viewBox="0 0 10 10" '
                'refX="10" refY="5" orient="auto-start-reverse">'
                f'<path d="M0 0 L10 5 L0 10 Z" fill="{layer.stroke}"/>'
                "</marker></defs>"
                if layer.arrow_end or layer.arrow_start
                else ""
            )
            arrows = f' marker-end="url(#arrow-{index})"' if layer.arrow_end else ""
            if layer.arrow_start:
                arrows += f' marker-start="url(#arrow-{index})"'
            effect = f"filter:drop-shadow({shadow_css(layer.shadow)});" if layer.shadow else ""
            connector = f'data-connector="{index}" ' if not layer.fill else ""
            layers.append(
                f'<svg {connector}xmlns="http://www.w3.org/2000/svg" '
                f'viewBox="0 0 {width} {height}" '
                f'style="position:absolute;inset:0;width:{width}px;height:{height}px;{effect}" '
                f'opacity="{layer.opacity}">{marker}<path d="{path_data(layer, width, height)}" '
                f'fill="{layer.fill or "none"}" stroke="{layer.stroke}" '
                f'stroke-width="{layer.stroke_width}" '
                f'stroke-linecap="round" stroke-linejoin="round"{arrows}/></svg>'
            )
            continue
        region = layer.region
        position = (
            f"position:absolute;left:{region.left * width:.3f}px;top:{region.top * height:.3f}px;"
            f"width:{region.width * width:.3f}px;height:{region.height * height:.3f}px;"
        )
        if isinstance(layer, TextLayer):
            family = style["typography"][
                "title_family" if layer.font_role == "title" else "body_family"
            ]
            css = (
                position + f"font-family:{font_stack(family)};font-size:{layer.font_size}px;"
                f"font-weight:{layer.font_weight};color:{layer.color};text-align:{layer.align};"
                f"line-height:{layer.line_height};white-space:pre-wrap;overflow-wrap:anywhere;"
            )
            if layer.shadow:
                css += f"text-shadow:{shadow_css(layer.shadow)};"
            layers.append(
                f'<div data-text="{index}" data-ref="{html.escape(layer.content_ref, quote=True)}" '
                f'data-min-size="{layer.min_font_size}" style="{html.escape(css, quote=True)}">'
                f"<span>{html.escape(texts[layer.content_ref])}</span></div>"
            )
        elif isinstance(layer, IconLayer):
            effect = f"filter:drop-shadow({shadow_css(layer.shadow)});" if layer.shadow else ""
            layers.append(
                f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
                f'style="{position}{effect}" fill="none" stroke="{layer.color}" '
                f'stroke-width="{layer.stroke_width}" opacity="{layer.opacity}" '
                'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
                f"{ICONS[layer.icon]}</svg>"
            )
        elif isinstance(layer, ShapeLayer):
            radius = "50%" if layer.shape == "ellipse" else f"{layer.radius}px"
            css = (
                position
                + f"background:{gradient_css(layer.gradient, layer.fill)};"
                + f"opacity:{layer.opacity};border-radius:{radius};"
            )
            if layer.shadow:
                css += f"box-shadow:{shadow_css(layer.shadow)};"
            if layer.stroke:
                css += f"border:{layer.stroke_width}px solid {layer.stroke};"
            layers.append(f'<div style="{css}"></div>')
        elif isinstance(layer, ImageLayer):
            raw = assets[layer.asset_ref]
            encoded = base64.b64encode(raw).decode()
            mime = "image/png" if raw.startswith(b"\x89PNG") else "image/jpeg"
            mask = "clip-path:ellipse(50% 50% at 50% 50%);" if layer.mask == "ellipse" else ""
            layers.append(
                f'<img alt="" src="data:{mime};base64,{encoded}" style="{position}'
                f"object-fit:{layer.fit};"
                f"object-position:{layer.focus.x * 100}% {layer.focus.y * 100}%;"
                f"opacity:{layer.opacity};mix-blend-mode:{layer.blend_mode};"
                f'border-radius:{layer.radius}px;{mask}"/>'
            )
    return (
        '<!doctype html><html><head><meta charset="utf-8">'
        '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; '
        "style-src 'unsafe-inline'; img-src data:; font-src 'none'\">"
        f"<style>@page{{size:{width}px {height}px;margin:0}}"
        f"*{{box-sizing:border-box}}html,body{{margin:0;width:{width}px;height:{height}px;"
        "overflow:hidden;-webkit-print-color-adjust:exact;print-color-adjust:exact} "
        "body{position:relative}img{display:block}</style></head><body>"
        + "".join(layers)
        + "</body></html>"
    )


PATH_CROSSINGS = r"""(textLayer) => {
  const candidates = [];
  for (const svg of document.querySelectorAll('svg[data-connector]')) {
    const path = svg.querySelector(':scope > path');
    const length = path.getTotalLength(), step = Math.max(4, length/2048);
    const margin = Number(path.getAttribute('stroke-width'))/2;
    const points = [];
    for (let d=0; d<=length; d+=step) {
      const p = path.getPointAtLength(d); points.push([p.x,p.y]);
    }
    for (const text of textLayer) {
      const hits = points.filter(([x,y]) => text.lines.some(({bbox:b}) =>
        x>=b[0]-margin && x<=b[2]+margin && y>=b[1]-margin && y<=b[3]+margin));
      if (hits.length) candidates.push({path_index:Number(svg.dataset.connector),
        content_ref:text.content_ref,points:hits});
    }
  }
  return candidates;
}"""


MEASURE = r"""() => {
  const textLayer = [], errors = [];
  for (const element of document.querySelectorAll('[data-text]')) {
    let size = parseInt(getComputedStyle(element).fontSize);
    const minimum = Number(element.dataset.minSize);
    const range = document.createRange(); range.selectNodeContents(element.firstElementChild);
    const overflowing = () => {
      // CJK fallback fonts can extend above the CSS line box (negative half-leading).
      // Account for their measured ascent inside the assigned region before fitting.
      element.style.paddingTop = '0px';
      const region = element.getBoundingClientRect();
      let bounds = range.getBoundingClientRect();
      element.style.paddingTop = `${Math.ceil(Math.max(0,region.top-bounds.top))}px`;
      bounds = range.getBoundingClientRect();
      return element.scrollHeight > element.clientHeight + 1 ||
        element.scrollWidth > element.clientWidth + 1 || bounds.bottom > region.bottom + 1 ||
        bounds.left < region.left - 1 || bounds.right > region.right + 1;
    };
    while (overflowing() && size > minimum) {
      element.style.fontSize = `${--size}px`;
    }
    if (overflowing()) {
      const region = element.getBoundingClientRect(), bounds = range.getBoundingClientRect();
      const requiredHeight = Math.ceil(Math.max(element.scrollHeight,bounds.bottom-region.top));
      errors.push({content_ref:element.dataset.ref,reason:'text_overflow',
        font_size:size,available_height:Math.round(region.height),
        required_height_at_current_width:requiredHeight,
        required_height_fraction:Math.ceil(requiredHeight/1080*1000)/1000,
        correction:'Increase this region height at its current width, or allocate more width. '+
          'Preserve the text and its minimum font size.'}); continue;
    }
    const node = element.firstElementChild.firstChild;
    const bounds = range.getBoundingClientRect(), region = element.getBoundingClientRect();
    const lines = []; let offset = 0;
    for (const char of node.textContent) {
      range.setStart(node,offset); offset += char.length; range.setEnd(node,offset);
      const box = range.getBoundingClientRect();
      if (char === '\n' || !box.width || !box.height) continue;
      let line = lines.at(-1);
      if (!line || Math.abs(line.bbox[1]-box.top)>1) {
        line = {text:'',bbox:[box.left,box.top,box.right,box.bottom]};lines.push(line);
      }
      line.text += char;line.bbox[0]=Math.min(line.bbox[0],box.left);
      line.bbox[2]=Math.max(line.bbox[2],box.right);
    }
    if (bounds.left < -1 || bounds.top < -1 || bounds.right > 1921 || bounds.bottom > 1081) {
      errors.push({content_ref:element.dataset.ref,reason:'outside_canvas'});
    }
    if (bounds.left < region.left - 1 || bounds.top < region.top - 1 ||
        bounds.right > region.right + 1 || bounds.bottom > region.bottom + 1) {
      errors.push({content_ref:element.dataset.ref,reason:'text_exceeds_region'});
    }
    textLayer.push({content_ref:element.dataset.ref,text:node.textContent,
      bbox:[bounds.left,bounds.top,bounds.right,bounds.bottom],
      region:[region.left,region.top,region.right,region.bottom],
      font_size:size,font_family:getComputedStyle(element).fontFamily,
      font_weight:Number(getComputedStyle(element).fontWeight),lines});
  }
  return {text_layer:textLayer,errors};
}"""


class PageRenderer:
    def __init__(self, settings):
        self.settings = settings

    async def preflight(self, render, fragments, style):
        buffer = BytesIO()
        Image.new("RGBA", (8, 8), (0, 0, 0, 0)).save(buffer, format="PNG")
        placeholders = {
            layer.asset_ref: buffer.getvalue()
            for layer in render.layers
            if isinstance(layer, ImageLayer)
        }
        document = fragment_html(render, fragments, style, placeholders)
        try:
            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch(
                    executable_path=self.settings.render_browser_executable,
                    headless=True,
                    timeout=20000,
                )
                try:
                    context = await browser.new_context(
                        viewport={"width": 1920, "height": 1080},
                        java_script_enabled=False,
                        service_workers="block",
                    )
                    await context.route("**/*", lambda route: route.abort())
                    page = await context.new_page()
                    page.set_default_timeout(15000)
                    await page.set_content(document, wait_until="load")
                    await page.evaluate("document.fonts.ready")
                    return (await page.evaluate(MEASURE))["errors"]
                finally:
                    await browser.close()
        except BrowserError as exc:
            raise AppError(
                "RENDER_BROWSER_FAILED",
                "The design preflight could not complete. Check the page renderer.",
                502,
            ) from exc

    async def render(self, render, fragments, style, assets, directory: Path):
        document = fragment_html(render, fragments, style, assets)
        directory.mkdir(parents=True, exist_ok=True)
        try:
            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch(
                    executable_path=self.settings.render_browser_executable,
                    headless=True,
                    timeout=20000,
                )
                try:
                    context = await browser.new_context(
                        viewport={"width": 1920, "height": 1080},
                        device_scale_factor=1,
                        java_script_enabled=False,
                        service_workers="block",
                        locale="zh-CN",
                        timezone_id="UTC",
                        reduced_motion="reduce",
                    )
                    await context.route("**/*", lambda route: route.abort())
                    page = await context.new_page()
                    page.set_default_timeout(15000)
                    await page.set_content(document, wait_until="load")
                    await page.evaluate("document.fonts.ready")
                    measurement = await page.evaluate(MEASURE)
                    if not measurement["errors"]:
                        await page.evaluate(
                            "document.querySelectorAll('[data-text]').forEach(e => "
                            "e.style.visibility = 'hidden')"
                        )
                        try:
                            painted = await page.screenshot(animations="disabled")
                            crossings = await page.evaluate(
                                PATH_CROSSINGS, measurement["text_layer"]
                            )
                            without_connectors = None
                            if crossings:
                                await page.evaluate(
                                    "document.querySelectorAll('svg[data-connector]').forEach(e => "
                                    "e.style.visibility='hidden')"
                                )
                                try:
                                    without_connectors = await page.screenshot(
                                        animations="disabled"
                                    )
                                finally:
                                    await page.evaluate(
                                        "document.querySelectorAll('svg[data-connector]')"
                                        ".forEach(e => e.style.visibility='visible')"
                                    )
                        finally:
                            await page.evaluate(
                                "document.querySelectorAll('[data-text]').forEach(e => "
                                "e.style.visibility = 'visible')"
                            )
                        with Image.open(BytesIO(painted)) as image:
                            measurement["errors"].extend(
                                painted_contrast_feedback(
                                    render, measurement["text_layer"], image.convert("RGB")
                                )
                            )
                            if without_connectors:
                                with Image.open(BytesIO(without_connectors)) as plain:
                                    measurement["errors"].extend(
                                        connector_feedback(
                                            crossings, image.convert("RGB"), plain.convert("RGB")
                                        )
                                    )
                    if measurement["errors"]:
                        error = AppError(
                            "RENDER_LAYOUT_INVALID",
                            "Some text does not fit or is difficult to read. "
                            "Retry visual generation.",
                        )
                        error.layout_feedback = measurement["errors"]
                        raise error
                    await page.screenshot(path=directory / "page.png", animations="disabled")
                    # Native text PDF is an intermediate render, exported/merged in M10.
                    await page.pdf(
                        path=directory / "page.pdf",
                        width="1920px",
                        height="1080px",
                        print_background=True,
                        prefer_css_page_size=True,
                        margin={"top": "0", "bottom": "0", "left": "0", "right": "0"},
                    )
                    measurement["browser_version"] = browser.version
                finally:
                    await browser.close()
        except BrowserError as exc:
            raise AppError(
                "RENDER_BROWSER_FAILED",
                "The page renderer could not start or complete. "
                "Install Chromium or check the configured browser path.",
                502,
            ) from exc
        with Image.open(directory / "page.png") as page_image:
            page_image.resize((480, 270), Image.Resampling.LANCZOS).save(
                directory / "thumbnail.png"
            )
        (directory / "text-layer.json").write_text(
            json.dumps(measurement["text_layer"], ensure_ascii=False)
        )
        return measurement
