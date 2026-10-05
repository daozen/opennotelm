# Generate the complete page with the image model

> 2026-10-03 文档整理：后续扩展：本文的整页默认继续适用；当前新 Deck 版本/编排由 [009](009-deck-visual-repertoire.md) 扩展，内容解读与风格分别见 [015](015-user-directed-deck-interpretation.md)、[016](016-content-adaptive-deck-style.md)。旧版本 metadata 仍兼容。

On 2026-10-02 the user explicitly chose to replace separate composition, artwork
generation and native overlay rendering with image generation of a complete page,
including its text. This overrides the original design requirement that all new
pages use native editable typography. The source-understanding, narrative planning,
style and cited SlideSpec stages remain in place.

## New default and saved versions

New Decks use `deck-content-v4` and `render_mode=generated_page`. Each authored page
is submitted directly to the configured image provider once, regardless of whether
the storyboard calls for illustration, diagram or typography. There is no native
RenderSpec call, separate asset-prompt call, font preflight or text/arrow overlay in
this path. The model receives deck style, page purpose, visual grammar, subjects,
source-supported relationships and the exact saved display copy. Internal citation
and element IDs are omitted; copy-group positions identify relationship endpoints.
The prompt asks the model to paint all copy verbatim, without new facts or labels.

The provider-neutral Images boundary accepts an optional `size` parameter. Whole
pages request `2048x1152`, supported by the configured GPT Image 2 protocol per
[official image-generation documentation](https://developers.openai.com/api/docs/guides/image-generation).
Other compatible providers need to support widescreen output. Actual returned
dimensions are recorded and accepted at 1280x720 or greater with a small aspect
ratio tolerance; smaller/square outputs fail rather than cropping off text or
stretching a square page. Legacy asset requests do not send a size parameter.

V2/V3 Decks retain their native pipeline and exact reuse rules. The API can also
create native Decks explicitly with `render_mode=native`. The application offers
“Create whole-page copy” for saved native Decks. It creates new Deck/slide identities
and new original-source citations, reuses their saved understanding, plan, style
and exact authored copy, and generates complete images. It requires all page
content and available original evidence; it never replaces the original Deck.

## Recovery, revisions and export

One versioned `full_page` asset per page saves the exact prompt, actual dimensions,
provider model, content hash and bitmap. Signatures include semantic content,
style, page plan, language, visual/image revisions and instructions. Saving new
text, changing the visual or replacing the image regenerates the complete selected
page. Source mappings remain available in the application. Unchanged sibling pages
are not regenerated. Failed images cannot be skipped, because they contain the
whole page. A missing derived render can be rebuilt from the saved bitmap without
another model call. Writes check slide revisions and join unfinished file-writing
threads on cancellation before cleanup; normal durable job recovery applies.

The full-size application preview retains the validated provider bitmap without
native overlays or resampling. Only thumbnails are resized. PDF export embeds the
page image losslessly at a standard widescreen page size and adds title bookmarks.
Image pages have no selectable text layer: there are no verified word positions.
We do not place an invented transcript at unrelated coordinates or certify the
image text by finding our own hidden text. Native pages keep their existing measured
searchable layer. A same-origin inline PDF preview route shares the download's
current-version, file-integrity and owned-path checks.

## What is and is not checked

Source/citation validity and authored display-copy budgets are checked before
generation. File format, byte/pixel bounds, widescreen dimensions, hash integrity,
page count, bitmap preservation and durable retries are checked afterwards. These
are not OCR or a visual semantic review. The saved asset explicitly records
`text_verification=not_automated`; model-rendered characters, numbers, extra labels
and relationships still require checking against the saved draft and original
source. The UI explains image-page PDFs and text edits, and exposes the saved text
draft for this comparison. No OCR or vision verification claim is made.

## Validation

Protocol tests cover the new default, image-model requirements, one complete
image per page, no native composition calls, hidden internal IDs, direct PNG
preservation, lossless PDF pixels/bookmarks, raster-only extraction, restart,
failure/retry, no image-skipping, text/visual/image/content revisions, sibling
preservation, stale exports and rebuilding a missing render. A separate copy test
checks original Deck equality, exact content/style/plan and original evidence.
Existing native tests explicitly select the native path to retain regression
coverage. Browser tests cover default creation, copies, editing help, text drafts,
PDF previews, failures and refreshed deep links; Docker uses isolated fixture data.

Real visual acceptance must compare every rendered page and PDF with the saved
draft and source. Provider dimensions may differ from requested dimensions; the
export preserves actual pixels. Extra text and inaccurate chart details remain
possible. Fixture success does not establish visual parity or image-text accuracy.
