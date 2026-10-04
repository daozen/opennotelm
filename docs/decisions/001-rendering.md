# Deterministic visual rendering and text fidelity

> 2026-10-03 文档整理：当前适用范围：本文保留原生 `native` 渲染的安全和文字保真契约。新 Deck 默认渲染已由 [008](008-whole-page-image-generation.md) 改为整页生图；不能据本文要求新默认 PDF 具备文字层。

The model emits only validated RenderSpec data. Text is resolved from the saved
SlideSpec's content fragments; every fragment must appear exactly once. Regions use
normalized 0–1 coordinates on a 1920×1080 canvas. Runtime checks reject out-of-bounds
regions, overlapping text regions, unknown assets, low contrast on uniform backgrounds,
and text that still overflows after bounded font fitting. Main explanation/quote/list
text cannot fit below 32 px; headlines require 64 px, numbers 48 px and small labels
or notes 24 px. The composition model receives these semantic fragment floors and
usable foreground/background pairs derived from its own palette. Layout feedback permits
one additional composition attempt. Model output never becomes arbitrary HTML/CSS.

An isolated headless Chromium context renders escaped text and fixed markup, with
page JavaScript disabled and network requests blocked. Only local system fonts and
validated image bytes are used. Docker installs Noto CJK fonts. Font fallback and
browser version are recorded; deterministic pixel tests apply to the same runtime.
Data-only polyline paths and arrowheads are painted with renderer-owned SVG markup;
the model supplies only bounded numeric points, colors and stroke properties. It
cannot submit SVG, HTML, scripts or external references. Horizontal/vertical paths
do not need invalid zero-area shape regions.

For every text line, the renderer temporarily hides text and captures the
actual painted background in memory. It samples 16×4 positions per measured text
line and requires contrast of at least 3 at 90% of those positions. This accounts
for image cropping, partial reading panels, crossing graphics and their opacity.
Uniform schema checks alone can miss a dark panel covering only part of a paragraph.
It is a legibility heuristic, not a substitute for full-page visual inspection.
Rejected pages receive content-free
feedback identifying affected fragments and the need for a calm reading area or
opaque panel. Repair context retains text/image placement without duplicating all
decorative geometry or dropping any source text. Overflow feedback includes the measured height needed at the
current width and minimum font size, so repairs can allocate space instead of
blindly shrinking text. Graph-like decorative traces must not imply invented data.
See the [Playwright Page API](https://playwright.dev/python/docs/api/class-page) and
[browser installation reference](https://playwright.dev/python/docs/browsers).

Each successful render stores:

- A 1920×1080 page PNG and a 480×270 thumbnail.
- The validated RenderSpec and exact text/line bounding boxes in pixel coordinates.
- An intermediate native page PDF printed from the same DOM and fonts.
- A hash covering semantic content, style, image bytes and renderer version.

The native PDF is an implementation extension to SlideRenderOutput. It carries the
same visual scene with selectable text already placed by Chromium. Final export uses
the page PNG as a lossless full-page visual layer and changes native text operations
to invisible rendering mode 3, retaining Chromium's embedded fonts and text positions.
Native shape/image painting is removed from this overlay, including inside form
objects. This implements the specified image-plus-aligned-text output without a second
font layout engine. [pypdf page merging](https://pypdf.readthedocs.io/en/stable/user/merging-pdfs.html)
preserves the original text transforms. Every expected text fragment and the final
page count are verified before the export is published.

Exports are keyed by title and ordered slide/revision/render identities. Unchanged
exports reuse intact files; outdated exports cannot be downloaded as current. The PDF
contains page bookmarks. Exporting runs in the durable queue; each failed export is
retryable and never replaces the completed page previews. M11 connects slide edits,
reordering and deletion to this invalidation boundary.

The export also restores the exact original Unicode from measured text fragments.
Some system fonts map a shared glyph to a CJK radical or a typographic ligature
instead of the source characters. A per-run cloned ToUnicode map corrects those
aliases without changing glyph advances, font metrics or text transforms. It retains
both forms when the source intentionally contains them (for example `页⻚` or `fiﬁ`).
Missing characters fail export explicitly. The lossless PNG remains the visual layer.

Generated files are published only after rendering succeeds and the slide revision
still matches. Retry reuses intact files with the same input hash. Partial Decks keep
completed pages, while a failed page can be retried without re-authoring other pages.
