# Integrated page design before artwork

> 2026-10-03 文档整理：历史默认路径说明：本文描述的集成原生排版继续用于兼容 `native` Deck；后续用户明确选择 [008](008-whole-page-image-generation.md) 的整页生成作为新默认。

The two user-supplied NotebookLM PDFs were rendered locally for comparison. Their
visible output demonstrates large explanatory scenes, labels attached to subjects,
cycles, staged journeys, contrasts and changes of visual scale. This observation
does not establish NotebookLM's internal implementation. Reference artwork and
its claims are not source evidence and are never embedded in generated Decks.

The old pipeline authored prose, generated a separate illustration, and composed
the page afterwards. That encouraged generic rectangular pictures next to long
paragraphs. Increasing image size or changing palette did not resolve the missing
relationship between content, graphics and artwork.

## One persisted composition coordinates the page

New Decks use `deck-content-v3`. Each planned page has a source-specific
`visual_grammar` and a bounded `reading_budget` in display units (one CJK character
or Latin word), including titles, labels, notes and captions. Authoring replaces
redundant paragraphs with meaningful short labels while retaining essential
qualifiers and original-source citations. This is free-form planning, not a
catalog of mandatory templates or palettes.

A page design is generated and checked with actual font metrics before costly
image generation. Its normalized, validated RenderSpec is persisted in
`slide_designs`. Image prompts receive the planned frame aspect ratio and
intersecting reading zones expressed inside that frame, without copying page
words into the bitmap. Initial final rendering uses that same design, then checks
contrast against the actual painted background and repairs if necessary. Image
providers may return different aspect ratios; final rendering still fits/crops
assets within the saved frame. Exact adherence by an image model is not guaranteed.

The designer sees compact summaries of the previous four page designs: background,
image coverage, dominant frame and path count. These support changes of page rhythm
within one palette, typography and material language. They do not prove artistic
quality or enforce a fixed sequence.

## Explanatory graphics remain editable and grounded

SlideSpec can save visual relationships with endpoints referring to saved content
and original-source citations. Their meanings distinguish sequence, contrast,
association, cause and cycle. Every saved relationship must be represented by
exactly one native path with its relationship ID; missing, duplicate or invented
IDs fail validation. All relationship citations pass the same source-scope
validation and provenance storage as other claims. Identity and citation validity
do not automatically establish entailment; real-output review still checks what
an arrow implies and whether its geometry is understandable.

The renderer supports bounded data primitives: smooth and closed paths,
bidirectional arrows, gradient surfaces, restrained glow/shadow, outlined shapes,
image crop focus, masks and blending. Text remains native, searchable and editable.
No model HTML, CSS or SVG is executed. Numeric-looking decorative traces must not
be used to imply invented data. These primitives are not a typed statistical-chart
engine; measured charts require separately grounded values and labels.

The native renderer also offers a small trusted pictogram vocabulary from Lucide
(ISC license in THIRD_PARTY_NOTICES.md). Artwork prompts receive contained native
connector/icon geometry in image-local coordinates. Visible connector intersections
with measured reading lines are checked against painted pixels; opaque reading
panels can safely occlude a connector. This is a bounded sampling check, not a
proof about every possible path or an aesthetic review.

## Recovery and compatibility

Design signatures include semantic content, style, design version and layout
revision. Image-only revisions reuse geometry; text/layout revisions may replan
with bounded prior reading layout. Invalid designs are repaired with bounded
attempts before requesting images. Saved designs survive image/render failures and
retry. Existing unchanged pages and assets retain their established reuse paths.

V2 Decks keep their generation version, image prompt version and the exact legacy
asset signature shape. New optional fields default safely when reading old JSON.
The migration only adds a table; it does not rewrite sources, citations, settings,
old image files or saved exports. A failed-page retry never silently upgrades an
old Deck. New Deck creation is the explicit transition to the new pipeline.

## Acceptance

Regression checks cover design-before-image ordering, image-local reading zones,
failed-preflight repair, cached retries, relationship identities/citations,
copy budgets, V2 assets and browser-painted primitives/searchable PDF text. Full
browser and production-container tests verify end-to-end recovery and editing.

A real Deck generated from an already authorized source PDF is required for visual
acceptance. Compare every page against the previous output and the two references:
short enough copy, explanatory relationships, integrated artwork, varied scale,
consistent visual language, clear reading order and readable type. Inspect final
PDF pages as well as application previews. Passing fixture tests alone cannot
establish equivalence to NotebookLM or justify a claim of visual parity.

On 2026-10-02 the user chose whole-page image generation, including text, as the
next default. This native pipeline remains supported for saved Decks. Its real
15-page trial completed 14 renders with one design failure; the output exposed
empty-circle diagrams and a connector crossing body copy. It was not accepted as
equivalent to the references. See decision 008 for the new generation direction.
