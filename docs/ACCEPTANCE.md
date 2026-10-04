> Public documentation: machine-specific paths, private example names and addresses have been removed. Historical results retain their original scope; private operational copies are not included. / 公开文档已去除本机路径、私有示例名称与地址；保留历史验证范围，私有操作记录不随仓库发布。

# Acceptance record

## Content-rewrite copies must reassess style — 2026-10-03

The user's newest completed “Great Longing” Deck was a content-rewrite copy of an
older Deck. Its style manifest was exactly identical to its parent, with no
`visual_style_version` or `restyled` flag and with `deck-art-v1`. The inspected
cover retained warm paper and painterly scenes. This was a missed copy entry:
the earlier change opted the visual-copy button into adaptive styling but left
the content-copy button on the style-preserving default. Switching from the LAN
URL to 127.0.0.1 did not change the running app or cause the inheritance.

The UI now explicitly requests restyling for content rewrites. The backend also
defaults to restyling when `rewrite_content=true`, including legacy parents;
an explicit `restyle=false` preserves style deliberately. Plain API copies retain
their earlier style-preserving default. Copy metadata now reports the current
operation's restyling choice rather than inheriting an ancestor's flag.

Checks: 40 affected backend cases, 40 frontend tests, production build, lint and
formatting passed; the final content-copy assertion was rerun successfully. The
isolated browser copy/edit/retry flow passed and checks adaptive-style and art
versions after clicking “重写内容副本”. New legacy-parent cases return a deliberately
different provider palette so accidental style reuse is observable; default,
explicit restyle and explicit preservation cases also verify original protection,
source scope, valid citations and fresh dossier input. No raster images were
automatically regenerated in existing Decks by this fix.

During validation the user started a new visual copy. Its live record already
selected contemporary poetic digital painting through adaptive styling and
`deck-art-v2`. It completed all 15 pages and exported a ready PDF. The inspected
cover used dark digital painting rather than the inherited warm-paper illustration;
this is a cover-level visual check, not a claim that every page was manually reviewed.
The service restart waited for this task and the subsequent Knowledge task to finish.
After updating the local app at http://127.0.0.1:3000/, all 64,226 persistent records
and 1,083 data files matched the pre-restart snapshot. New frontend assets and the
backend default were confirmed loaded, and the latest Deck page and PDFs remained
accessible. No active task was interrupted.

## Content-adaptive Deck style — 2026-10-03

The user's cross-topic homogeneity report was confirmed against existing philosophy,
Discord social-research and business covers and stored style/art manifests. The old
style instructions repeatedly preferred editorial illustration, tactile materials,
warm paper and drawing vocabulary. The original style call did not receive the user
instruction or research dossier directly; visual copies retained their global style.

New Decks compare three content-specific directions within the existing style call,
using source character, communication task, tone, audience and actual user requests.
The selected medium reaches art planning and image generation; reading surfaces are
medium-neutral and flat identities need no forced perspective. The UI visual-copy
action now resets global style as well as page art, preserving exact saved content,
ordered pages, source scope, citations and the original Deck. See decision 016.

Checks: all 272 backend cases passed with the native browser enabled; 40 frontend
tests, TypeScript/production build, formatting and lint passed. Three isolated browser
flows passed, including native-to-image conversion, the restyle flag, citations,
PDF/deep links, text edits and failed-image retry. After adding actual user instructions
and selected directions to the new image signatures, the affected 37 backend cases
passed again. Existing signature/version and style-preserving API-copy cases remained
compatible. Regression checks also found and fixed fresh research not entering the
in-memory style context and public asset reads before a restyled copy has a style.

Real-provider sampling used private copies of the existing authorized data and secret
store with the configured localhost:8317 gateway, `gpt-6-luna` and `gpt-image-2`.
No live notebook, Deck, source, model configuration or job was changed by sampling.
The first three-topic trial selected vector directions for all subjects; its two
actual covers differed visibly from the old paper aesthetic, but the preference for
generic clarity was still too strong. The final selection prompt therefore requires
content-specific rhetorical/emotional fit as well as readable explanation.

The final trial selected expressive conceptual oil painting for the Nietzsche chapter,
vector spatial mapping for social research, and typographic/abstract editorial design
for the business essay, with different palettes and reasoned tradeoffs. Its Nietzsche
cover was generated and visually inspected. Both trials also tested the same social
research content with an explicit black/white/bright-orange, flat-vector instruction;
the final manifest preserved that requested palette and excluded paper/watercolor/depth.
Three actual covers were inspected in total across the two trials; the final social
research and business styles were reviewed as plans, not complete generated Decks.
Temporary secret-store copies were removed when each check finished.

After confirming no queued/running user jobs, the native LAN service was updated and
verified healthy at http://192.0.2.10:3000/. All 62,170 persistent records and 961
data files matched the pre-update snapshot; existing 15-page PDFs remained accessible.
No dependency or container setup changed; fresh Docker acceptance was not repeated for
this phase. Exact raster text, full-deck aesthetic consistency and user approval of
the resulting design remain separate from schema/protocol checks and cover sampling.

## Readable PDF source preview — 2026-10-02

The user reported single-character rows in imported document previews. The existing
Chinese PDF had 4,049 immutable blocks, almost all one glyph; the English paper had
6,610 word/phrase fragments. A PDF text drawing operation is not a paragraph.

Added a read-only [reading projection](decisions/003-readable-source-projection.md)
that reconstructs physical lines and paragraph flow while retaining inline original
block anchors. It supports previously imported PDFs without re-uploading, rewriting
facts or regenerating their saved Knowledge/Deck artifacts. Native outlines and pages
remain navigable; false fragment headings no longer fill the reader's directory.
Citation jumps open the containing page and highlight the original inline block.
Body size is adjustable (16/18/20px), and expanded reading uses document scrolling.
The immutable fact API and non-PDF semantic block boundaries remain unchanged.

Verified against the existing local instance: the Chinese PDF now has 139 readable
paragraphs/headings across twelve pages, and the paper has 508 across thirty-four.
Every original block ID and every normalized visible character remains represented;
there are no one-character reading paragraphs. Forty saved Deck citations still
resolve to available original spans, and the previously delivered PDF hash is unchanged.
No model calls or source re-indexing were needed.

Checks: 146 backend tests, five frontend unit tests, production build and lint/format
passed. All eleven isolated browser flows passed; the new reading flow was repeated
after the final expanded-scrolling adjustment. Final desktop and 390px-wide screenshots
were visually inspected. Regression cases cover separately drawn Chinese glyphs and
Latin words, multi-line callbacks, paragraph gaps, exact fact/citation preservation,
page scope, legacy citation navigation, inline anchors, HTML escaping, type size and
expanded width/scrolling. Existing EPUB/Markdown/TXT reader flows still pass.

Manual path: refresh the application, open an already imported PDF, change page/chapter,
adjust body size and choose “展开阅读”. Open a citation from Chat/Knowledge/Deck and
verify its inline text remains highlighted within the complete containing page.
Complex columns/tables/rotated text remain heuristic reflow rather than exact original
layout. The existing in-app browser tab is still blocked by its error-page URL policy;
this record separates real-source API validation from isolated browser visual checks.
Docker release verification remains pending.

## Content and design quality correction — 2026-10-01

The user rejected the previous real-provider PDF for both content and visual quality.
Its successful generation/export checks below are protocol and fidelity evidence,
not approval of editorial or design quality. Milestone 13 is in progress.

The supplied 14-page NotebookLM reference was inspected locally at page and overview
scale. It teaches through source-specific interpretation, quotations, a sustained
visual metaphor, large explanatory illustrations, comparisons and synthesis, with
variation in lighting, background and composition. It has no extractable text layer;
our output must retain searchable text while improving the illustrated presentation.
The attachment and its extracted content are not committed to this repository.

An important upstream defect was identified: the existing paper's immutable text
blocks yielded thousands of word/half-sentence evidence packets. Slide authoring
received fragments lacking enough context to support a detailed explanation. The new
synthesis groups adjacent blocks into bounded, coherent passages, retaining every
original block span and respecting source, node and page boundaries. A deck-specific
research dossier preserves concrete mechanisms, examples, quotations and distinctions.
New plans carry teaching points and a visual storyboard, propagated to slide authoring
and composition; prior saved plans remain readable. Fresh plans reject repeated exact
messages and missing storyboards. Design/image instructions now support substantial
illustrations and calm reading areas rather than small decorative icons.

The compatible provider completed the source dossier and fifteen semantic pages,
with thirteen illustrated storyboards. Real composition exposed invalid zero-area
line shapes, low-contrast palette accents, undersized reading text, image/text contrast
and insufficiently sized text regions. Bounded data-only paths, semantic font floors,
palette contrast options, aggregated repair feedback and measured overflow height now
address those failures. Painted-background checks cover every text line, including
partial panels, rather than assuming that all non-image backgrounds are uniform.

Checks after these fixes: 143 backend tests and ten isolated browser flows passed.
Renderer tests exercise actual Chromium painting, partial-panel and image contrast
rejection, readable font floors, bounded arrows and preservation of searchable PDF
text. Tests of citations now check actual original paragraphs across multi-block
passages. These checks still do not substitute for real-provider editorial review.

## Replacement real-provider PDF reviewed — 2026-10-02

The replacement deck completed with fifteen pages and illustrations on thirteen pages.
Its coherent source passages supported specific mechanisms, participant examples and
short quotations. The original source, translation convention, source findings,
author interpretations and untested design recommendations are distinguished.
One author paraphrase initially presented as a quotation was corrected to an explicitly
labelled paraphrase through the product's content revision action.

Natural-language revisions reduced opening and closing density, removed graph-like
decoration from the methods page, enlarged a small illustration, separated text from
an image boundary, and introduced dark and teal reading surfaces within the common
visual vocabulary. Each revision checked that the other fourteen saved semantic specs,
revision numbers and render IDs stayed unchanged. Visual-only revisions also checked
that all target-page semantic content stayed identical.

Final checks against the live app and actual downloaded PDF:

- Fifteen current page renders use the updated renderer and satisfy semantic font
  floors and painted-background checks. Every final page and the complete PDF overview
  were inspected after Poppler rendering; a detected image-edge reading issue was
  corrected before the final export.
- All 142 saved text fragments are searchable in their corresponding PDF pages.
  All forty current citations resolve to exact available original-source block spans
  within the chosen PDF scope (3,938 span occurrences across citations).
- Every PDF page's embedded full-size image matches its saved preview pixel-for-pixel.
  The downloadable PDF matches the persisted export bytes. No claim of zero viewer
  interpolation differences is made.
- 143 backend tests and ten isolated browser flows passed; backend lint/format and
  whitespace checks passed. Implementation and acceptance records are committed.

This result combines fresh generation with targeted editorial and layout revisions.
Several first-pass compositions still needed bounded repairs and explicit art direction;
it does not establish that every new deck reaches this quality without review.
User evaluation of the replacement remains open. Docker and live in-app browser
release constraints recorded below remain unchanged.

## Local real-provider flow verified — 2026-10-01

The local instance now has three successfully probed model roles and two indexed
native-text PDFs. Existing failing jobs are being retried with the user's permission.
No private document contents or credentials belong in this repository record.

Reproduced and corrected:

- DeckBrief language codes were expanded into human-readable labels. Generation
  now requires the exact supplied code; bounded structured repair receives specific
  schema and semantic validation feedback rather than a generic retry instruction.
- The compatible language endpoint ignored both tested output-token limit fields.
  Citation-heavy synthesis reductions exceeded the old fixed output reserve despite
  fitting the total context. Reductions now receive a larger context-bounded reserve,
  and bounded repair receives the concrete UTF-8 byte limit and citation failure reason.
- The local renderer's installed Chromium cache belonged to an older Playwright
  version. Installing the matching browser resolved the missing-runtime failure.

Checks: 129 backend tests, four frontend unit tests, ten isolated browser flows,
production build and formatting/lint passed. Thirteen renderer/PDF checks also
passed using the newly installed matching browser. Unsaved Knowledge navigation
is covered by a browser test and a unit test.

Verified against the live local application:

- Both original native-text PDFs are indexed. A focused question about the paper's
  qualitative analysis received a source-grounded answer; citation APIs returned
  exact, available original block spans. A broader question with insufficient
  retrieved evidence correctly reported that limitation rather than inventing results.
- The previously failing PDF-scope Knowledge job completed with 139 original-source
  citations. Public complete EPUBs were imported and indexed. The native chapter
  structure of [Alice's Adventures in Wonderland](https://www.gutenberg.org/ebooks/11)
  was checked, including its twelve named story chapters. Chapter I generated a
  saved cited Knowledge page; editing and updating it with Chapter II preserved
  the manual note and resulted in 48 citations.
- The original 15-page deck completed with a model-authored narrative, common style,
  fifteen rendered pages and one generated image. Partial retries reused completed
  content/images/previews. A natural-language visual revision changed one preview;
  all fourteen other preview IDs and every saved semantic text element stayed unchanged.
- The final 15-page PDF can be downloaded. All saved text fragments were found in
  the extracted searchable text. Its embedded page images matched previews exactly
  pixel-for-pixel. Poppler rasterization and the complete thumbnail sheet were reviewed;
  viewer interpolation produces small edge differences, so this record does not claim
  zero differences between viewer-rendered pixels and original PNG pixels.
- A graceful stop and new server process preserved seven complete API snapshots:
  model configuration, preferences, notebooks, sources, Knowledge, chat and Deck.
  The final PDF remained downloadable. No tasks were active at shutdown.

Docker build/start and the container-host real-provider setup remain unverified:
this host has no Docker/Podman/Colima runtime. The live in-app browser could not be
inspected because its browser tool rejected the existing error-page protocol;
automated browser acceptance above used the isolated protocol-test environment.
This local-flow result does not claim that every release gate has passed.

## Milestone 1 — skeleton and setup

Implementation: Notebook create/read/rename/delete, three-role model setup, optional
model discovery, actual capability probes, encrypted/environment keys, SQLite migrations,
same-origin checks, responsive browser shell, Docker Compose and CI.

Automated checks (2026-09-30): 14 backend tests, 2 frontend tests, one real-browser
setup/CRUD/reload flow passed; backend lint/format passed. Notebook home screenshot
visually inspected. Dependency audit: zero known npm vulnerabilities. TypeScript and production build passed.

Manual path:
1. Start the app; open the setup dialog on first visit.
2. Configure Language, Embedding and Image endpoints, keys and model IDs.
3. Run each capability test. Failed tests show a safe error and allow retry.
4. Continue to notebook list; create a notebook, open, return, rename and delete.
5. Restart the backend; notebook and model configuration must persist.

Pending release checks: actual user-owned AI models, Docker build/start, and all
subsequent milestones. No claim of V0.1 release readiness is made at this stage.


## Milestone 2 — EPUB reader and durable parsing

Implemented upload/raw-file persistence, checksum deduplication with explicit reuse,
EPUB 3 TOC/EPUB 2 NCX and spine order, normalized hierarchy and semantic blocks,
exact block locations, async durable jobs, error/retry/progress, notebook selection,
unlink and permanent deletion, and a chapter reader. Archive bounds are configurable.

Checks (2026-09-30): 31 backend tests, frontend tests/build, lint and format passed.
Two real-browser acceptance flows passed. EPUB reader screenshot inspected. Tests
cover hostile ZIP paths, compression limits, entity expansion, script removal,
semantic extraction, stable block IDs, retry idempotency, and restart recovery.

Manual path: create/open a notebook, import `frontend/e2e/fixtures/book.epub`, wait
for readable status, open both chapters, toggle selection, reload, import again
and explicitly reuse the existing source. Remove only from the notebook, then
reattach if desired. A corrupt `.epub` must display a safe error and a retry action.

Source parsing is available without AI. Embedding and grounded chat follow in M3.

## Milestones 3–4 — grounded chat and citations

Implemented paragraph chunks with original block offsets, local cosine retrieval,
model/dimension/chunker signatures, source/chapter scopes, short follow-up queries,
context budgets, durable chat jobs, exact block-span citations, one constrained
citation repair, citation previews and reader highlights. Reader remains available
when embedding fails. Queued requests preserve their chosen scope.

Checks (2026-09-30): backend regression tests cover exact quotes, index rebuilds,
source deletion, restart, scope isolation, concurrent sends, chunk coverage, embedding
failures and citation repair rejection. All three browser flows passed, including
citation preview/open-original and chapter questions. Production build, frontend
tests, lint and format passed; citation screenshot visually inspected.

Manual path: configure Language and Embedding, import EPUB and wait for indexing;
ask a source question, open a citation, then open the original highlighted block.
Use chapter Ask, return to selected sources, and verify unchecked sources are excluded.
A failed model call can be retried from its question.

Provider tests are deterministic protocol tests. Semantic groundedness and answer
quality against actual user-configured models remain part of final release acceptance.

## Milestone 5 — text PDF, Markdown and TXT

Implemented format-specific upload limits, PDF native outlines/page nodes/font and
numbered heading fallback, page-located blocks, low-text/scanned and encrypted PDF
errors, Markdown heading hierarchy and semantic blocks, and UTF-8/UTF-16 text
paragraphs. Raw files are retained; all formats use the same embedding and exact
block-span citation pipeline. HTML is sanitized without executing or fetching resources.

Checks (2026-09-30): 53 backend tests, 2 frontend tests and all four browser flows
passed. TypeScript/production build and backend lint passed. Tests cover native PDF
outlines, page locations, missing text, encryption, corruption, page and file limits,
Markdown code/table/quote/list semantics, inline script sanitization, encoding errors,
retry persistence and exact citations in all new formats. PDF reader screenshot inspected.

Manual path: import `frontend/e2e/fixtures/text.pdf`, `notes.md` and `notes.txt`;
open their structured reader, choose PDF page/chapter and ask with that scope. Click
a citation to inspect original text and page. Import `scanned.pdf`; an explicit
no-OCR error and retry action must appear. Sparse/partially readable PDFs show a
warning for pages with no extracted text. OCR and exact PDF layout reconstruction
are outside V0.1; the reader presents normalized extracted text.

## Milestone 6 — Knowledge pages

Implemented chapter/source/selected-source generation from the full normalized scope,
context-budgeted hierarchical synthesis, persisted intermediate summaries, original
block-span citations, Markdown display/edit, revision checks, explicit Update with
Source, and Save as Knowledge from a completed chat answer. Model updates append
new material; replacements require an exact passage within one paragraph, an explicit
conflict reason and valid new evidence IDs. Unrelated paragraphs are retained by the
application. Invalid output never replaces a saved page. Source deletion retains
knowledge and citation identity while marking unavailable originals.

Checks (2026-09-30): 60 backend tests and 3 frontend tests passed; focused Knowledge
checks were repeated after tightening replacement validation. Tests verify every
character of the long input enters synthesis, scope isolation and frozen selection,
checkpoint reuse after failure, exact original quotes, persistence, revision conflicts,
unknown citation rejection, retained user notes/old knowledge and copied chat citations.
The Knowledge browser flow passed generation, citation preview, editing, explicit
update, saved chat and reload. The four earlier browser flows also passed. Production
build, lint/format and npm audit passed (zero known vulnerabilities). Knowledge page
screenshot visually inspected.

Manual path: open a source chapter and choose “从本章节生成知识”; open its citations.
Edit the resulting page, add a personal note, and save. Select new sources and use
“用所选资料更新”; verify the note and prior supported information remain. Return to
Chat, save a cited answer as a knowledge page, then reload and reopen it from the
Knowledge tab. A failed synthesis offers retry. Editing during generation causes a
revision conflict rather than overwriting the saved user edit.

Model quality, semantic accuracy of proposed conflict corrections and completeness
of natural-language summaries still require real-model release acceptance. Automated
checks prove full input coverage, citation identity, bounds and persistence; they do
not prove the quality of the model's interpretation. Visual Deck from Knowledge
continues in M7–11. Temporary Summary/Outline transformations (PRD §19) are completed in the follow-up below.

### M6 completion — temporary Summary / Outline

The chapter reader now offers temporary summaries and outlines, using full-scope
synthesis and original-source citation previews. Only an explicit save creates a
Knowledge page; saving twice is idempotent. Dismissal clears temporary output.
Abandoned outputs expire after 24 hours and are cleaned on use/startup; this is job
cache, not a library artifact. A dismissed queued task skips model calls. Invalid
or failed output offers retry, and temporary citations become durable on save.

Validation: 9 focused Knowledge/transformation tests and both browser flows passed;
production build and lint passed. The temporary preview screenshot was inspected.
Tests cover no implicit Knowledge creation, summary/outline prompt distinction,
original quotes, explicit/idempotent save, discard, expiry and queued dismissal.

## Milestone 7 — Visual Deck content pipeline

Implemented durable DeckBrief → DeckPlan → DeckStyleManifest → SlideSpec stages,
selected-source/source/chapter/Knowledge scopes, a frozen Knowledge revision,
10/15/20 total-page validation, model-authored design concept/palette/typography/
composition/image direction, rich semantic elements and per-slide original citations.
The creation dialog has only scope, length, language and optional instruction.
Studio lists decks and the content preview exposes completed plans before authoring
finishes. It is explicitly labelled a content draft until visual rendering is added.

Each slide is saved independently. A provider/citation error produces a partial deck;
retry only authors missing/failed slides and preserves completed IDs/specs/citations,
plan and style. Fatal-stage retries reuse persisted successful stages and synthesis
checkpoints. Original-source deletion retains existing deck content and marks citations
unavailable. Input budgets fail explicitly rather than silently omitting material.

Checks (2026-10-01): 10/15/20-page tests, rich elements, exact source ownership,
unselected-source isolation, invalid-plan/citation rejection, partial retry call counts,
frozen Knowledge input and backend restart passed. Seven browser flows passed,
including four-control Deck creation, 10-page content navigation, comparison elements,
source preview, reload and switching back to the reader. Frontend unit tests,
TypeScript/production build and lint/format passed; content-draft screenshot inspected.

Manual path: select source documents and choose Studio → Generate Visual Deck;
choose 10/15/20 pages, language and optional guidance. Inspect saved slide plans as
generation progresses, select a completed page and open its sources. Alternatively,
start from a source chapter or Knowledge page. On partial failure, retry and verify
completed pages remain unchanged. Reload and open the deck from Studio.

No fixed slide templates or preset style list is used by production code. Tests use
synthetic structured outputs to verify the pipeline, not narrative/visual quality.
Page images, image generation, PDF output and editing/revisions follow in M8–11;
real-model design quality and full release acceptance remain pending.

## Milestone 8 — visual composition and deterministic rendering

The model supplies validated geometric RenderSpec data; production code has no slide
templates. Saved semantic text is resolved by exact fragment IDs, escaped and rendered
in isolated Chromium. Shapes/images sit below text. Bounds, fragment coverage,
overlap, contrast and real font metrics are checked. CJK fallback font ascent is
measured before fitting. Failed layouts receive one bounded repair attempt.

Each successful page stores a 1920×1080 PNG, thumbnail, measured text/line positions
and a native single-page PDF from the same DOM. The latter is the intermediate for
M10, described in [the renderer decision](decisions/001-rendering.md). Input hashes
reuse unchanged pages. Failed slides retain successful siblings; retry renders only
missing output. The browser shows thumbnails, full-page images and expandable text.

Checks (2026-10-01): 75 backend tests and all seven browser flows passed. After the
final CJK metric adjustment, three renderer tests and the real ten-page browser flow
passed again; TypeScript/production build and three frontend tests passed. Checks
include identical pixel hashes for repeated input, Chinese/English PDF extraction,
overflow rejection, hostile markup escaping, cache reuse, partial retry and recovery.
Deck screenshot inspected. Browser/font provisioning is included in Docker and CI;
the Docker runtime itself still requires release acceptance on a Docker host.

Manual path: generate a deck, wait for page previews, navigate thumbnails, open a
high-resolution page and expand its saved text/citations. Reload and reopen it.
Image generation, complete PDF export and slide editing remain M9–11; real-provider
visual quality remains an explicit release check.

## Milestone 9 — generated image assets and partial recovery

Image prompts combine the saved deck style, visual intent and asset purpose. Prompts,
negative guidance, image dimensions, provider model, pixel hash and status persist in
SQLite. An ImageGenerationAdapter protocol isolates the compatible Images endpoint.
Both base64 and URL responses are supported, without model-specific optional request
parameters. The adapter follows the [official Images API reference](https://developers.openai.com/api/reference/cli/resources/images/methods/generate).

Images must decode as bounded PNG/JPEG/WebP pixels; animations and invalid/oversized
data fail. Re-encoding removes ancillary metadata and preserves transparency. Download
requests never forward provider credentials/cookies, validate each redirect, and pin
public DNS addresses. Same-origin configured local image providers are supported.
Model setup now verifies real image data, not just the presence of a response field.

Each image has durable success/failure/skipped state. Retry reuses saved prompts and
intact successful assets. A per-slide retry leaves other pages alone; “continue without
image” skips only failed assets and preserves successful ones on that page. The
composer receives local asset bytes, and the UI exposes image progress and recovery.

Checks (2026-10-01): 84 backend tests, three frontend unit tests, production build,
lint/format and eight browser flows passed. Tests cover real pixel decoding, alpha,
invalid payloads, download credential isolation, DNS pinning, response limits,
two-image partial success, prompt reuse, unchanged siblings, ownership checks,
restart and skipped persistence. Browser tests render a real raster fixture into a
page and exercise failed-image retry followed by no-image continuation. Preview and
failure screenshots inspected. Providers remain synthetic; real-provider image quality
and deployment acceptance remain pending.

Manual path: create a deck whose model requests an image. Open its page to see image
progress. On image failure use “重试本页” or “不使用失败的图片继续”; confirm all other
pages retain their previews. Reload to verify the saved result.

## Milestone 10 — downloadable, searchable PDF

Completed decks automatically export PDF; the viewer offers download and re-export.
Export runs in the durable queue, stores status/size/page count/hash, and reuses intact
output for identical ordered slide revisions. Stale exports are rejected, corrupt
files can be rebuilt, and failed exports preserve all page previews. The exporter
joins its background work before cancellation can hand the same path to a resumed job.

Each PDF page contains the lossless high-resolution page image and an invisible text
layer retaining Chromium's fonts and original text transforms. It also has a page
bookmark. Before publication, every expected text fragment and page count are checked.
Native forms preserve searchable text without painting over the visual layer.

Checks (2026-10-01): full backend regression passed 90 tests; the final seven focused
PDF tests additionally verified pixel fidelity and exact text transforms. Tests cover
10/15/20 pages, Chinese/English text, image dimensions, invisible rendering mode,
encoded forms, missing-text rejection, cached export reuse, restart/download,
corrupt-file rebuilding and stale-version rejection. All eight browser flows passed,
including real ten-page automatic export/download and no-image recovery to a ready PDF.
Frontend build and three unit tests passed; lint/format passed.

The downloaded ten-page browser artifact was rendered at 96 DPI with Poppler and
compared against all original 1920×1080 previews. Mean absolute channel differences
were 0.10–0.34 on a 0–255 scale (minor rasterizer interpolation); every page remained
searchable. All ten pages were visually inspected as a contact sheet. A repeatable
Poppler pixel test is included; CI installs Poppler and CJK fonts. These fixtures
validate export fidelity, not real-provider design/narrative quality.

Manual path: generate a deck and wait for “下载 PDF”; open the file in a PDF reader,
search/copy Chinese and English text, check page count/order and compare the image
page with its in-app preview. Use re-export if a local export file has been removed.

## Milestone 11 — individual slide revisions

Implemented text editing, independent content/visual/image regeneration, natural-language
revision routing, reorder and delete. All actions use optimistic revision checks and
respect active deck jobs. Content changes retain the deck plan/style and original
source provenance. Unchanged image requests are reused. Old previews remain visible
with an explicit stale label until the revised page succeeds; failed work resumes
from its saved stage without re-authoring committed content. Historical citation
identities remain valid. Reordering/deletion rebuild only the PDF, not page renders.

Checks (2026-10-01): the full backend regression passed 104 tests, then all ten focused
PDF tests passed after additional Unicode/ligature cases. All nine browser flows,
three frontend unit tests, production build and lint/format passed. The new browser
flow covers every editing action, unchanged sibling identities, stale PDF rejection,
image/citation reuse, nine-page export after deletion and reload. Tests cover failed
revision retries, no-image continuation, unavailable originals, stale retries,
fabricated citations, busy/conflicting edits and deletion down to an empty deck.
The editing screenshot was visually inspected.

Real-browser acceptance exposed system-font mappings of `页` to `⻚` and `fi` to `ﬁ`.
The export now restores exact source Unicode, with regression cases containing both
the alias and original characters. Existing text-transform and PDF pixel checks pass.

Manual path: open a finished deck, select a page, edit its text, try each regeneration
action and “用 AI 修改”. Confirm other pages retain their previews. Move the page,
delete another, download the updated PDF and verify its order/count. On a failed
revision, retry the page and confirm the saved revision is resumed. Model-directed
revision quality remains part of real-provider release acceptance.

## Milestone 12 — recovery and lifecycle checkpoint

The app exclusively owns its data directory before migration and recovery. A second
server process is rejected; OS locks release after an abrupt process exit. Interrupted
jobs resume and processing traces distinguish interruption from success. Retrying a
job cannot interleave with another operation on the same deck. Restart tests now stop
the original app before creating a new instance.

Migration 011 attaches jobs to their owning notebook/source and removes pre-existing
orphan job records. Database deletion schedules owned files for durable cleanup;
startup also reclaims uncommitted render/upload files. Cleanup never follows symlinks
outside owned directories. Deleting a notebook retains shared source files. Deleting
a source removes copied evidence and synthesis caches while keeping derived artifacts
and unavailable citation identities. Deletion waits for affected active tasks.

Checks (2026-10-01): 117 backend tests and all nine browser flows passed. A subsequent
fix moved source-attachment existence checks inside the write transaction; all six
source tests and the EPUB browser flow passed, including concurrent attach/delete.
Lint, formatting and diff checks passed. Tests additionally cover upgrading a saved
M10 PDF database to M12, refusing newer schemas, recovering an applied slide revision
without re-authoring, and deletion recovery after interruption.

Diagnostics, optional anonymous event delivery, final privacy/UI review and release
acceptance remain in progress. This host still has no Docker/Podman/Colima executable;
Docker and real-provider acceptance are not yet verified.

### M12 privacy and diagnostics checkpoint

Settings now offers anonymous statistics consent and a downloadable diagnostic report.
The report selects operational fields explicitly: versions, source types/counts, model
IDs, bounded job traces and aggregate retrieval scores. It excludes user text, filenames,
prompts/responses, endpoint URLs, secrets, raw logs and the anonymous install ID.

Optional telemetry uses typed events and a strict property allowlist, a bounded SQLite
queue, independent HTTP transport and background PostHog batches. It defaults off;
disabling clears unsent events and prevents future transmissions. The installation
UUID is random. Retries retain event UUIDs, reject redirects and do not affect jobs.
Framework automatic telemetry is explicitly disabled. Structured local job logs omit
payloads and exception text. Deployment configuration and exact fields/retention are
documented in [PRIVACY.md](PRIVACY.md).

Checks (2026-10-01): all 126 backend tests and ten browser flows passed, along with
production build, three frontend tests and backend lint/format. Eight privacy-specific
tests verify opt-in silence, property rejection, anonymous batch shape, persisted IDs,
retry, age/size bounds, tampered queue entries, redirect isolation, disable/send races,
diagnostic/log redaction and failure isolation. The browser flow verifies consent
persistence, disabling, downloading a report and absence of private sentinels. The
settings screenshot was visually inspected. No real telemetry project received data.

Manual path: open Settings → 隐私与诊断, download and inspect a diagnostic report.
On a deployment with an operator-configured receiver, enable anonymous statistics,
perform an action, then disable them; queued events must be cleared. Without receiver
configuration, the UI explicitly reports that statistics will not be sent.

Final requirement review, Docker execution and real-model release acceptance remain
pending; protocol fixtures do not establish narrative/design quality.

## Docker production-image acceptance — 2026-10-02

Resolved the missing runtime on this Apple Silicon Mac by installing Colima 0.10.3,
Lima 2.2.0, Docker CLI 29.8.2, Compose 5.5.1 and Buildx 0.37.2. Docker Engine 29.5.2
runs in a native Linux ARM64 VM with four CPUs, 6 GiB memory and a 40 GiB data disk.
The production image includes its frontend, Python environment, Chromium and CJK
fonts; it runs as UID 10001. The verified image ID was
`sha256:f6928e6ab6b95b3f40dd4da27d31563d9cdc2461196e94e7214717d2873cebfb`.

`bash tools/docker_acceptance.sh` completed successfully against a clean, isolated
data directory on port 4303. First setup passed separately on the empty database;
all 11 browser flows then passed against the production image (2.4 minutes).
They cover source formats, readable PDF preview, citations, Knowledge, temporary
transformations, Deck images/export, per-page revision, partial recovery and privacy.
The fresh-instance chat fixture now configures all three model roles so reload does
not reopen incomplete setup. The telemetry fixture stays on container loopback and
does not forward or persist events.

The persistence check imported five sources, generated grounded chat/Knowledge and
a 15-page illustrated Markdown-source deck, and revised only the chosen page's
visuals. After both a process restart and complete container recreation, all 40 API
snapshots, 79 saved source/asset/render/export/secret file hashes and 16 PDF/preview
download hashes matched. All three saved encrypted keys could still be decrypted
and used for provider discovery. No queued/running jobs remained. The test stack
was stopped automatically; it never mounted the user's live `data/`.

The downloaded container PDF has 15 pages and all 62 saved text fragments are
searchable on their matching pages. SHA-256:
`c7b326eb92f9ffbbd0dcd6362d413371e85366d5b0135104353d174b4f380d9b`.
This is a protocol fixture, not the separately reviewed real-provider replacement
deck. Docker browser screenshots and all exported fixture pages were inspected.

An additional production-image probe used a temporary, read-only copy containing
only existing encrypted model configuration. Through `host.docker.internal`, actual
`gpt-6-luna` text/JSON generation, `gpt-image-2` image generation and
`qwen3-embedding-0.6b` 1024-dimensional embedding all passed. No original documents
were sent by these capability probes, and the temporary key bundle was removed.
The existing model URLs/configuration were not changed. Container deployments must
replace host-local `localhost` model URLs with a reachable host address.

Full regression: 146 backend tests, five frontend unit tests, production build,
lint/format and shell syntax checks passed. The backend suite retains one existing
Starlette test-client deprecation warning. The user's live source/asset/render/
export/secret files retained their original hashes; the reviewed real PDF retained
its exact hash and the LAN application remained available on port 3000.

CI now runs the same container acceptance script and preserves its artifacts.
The workflow has not run remotely on this checkout; AMD64 and other host runtimes
are not claimed as locally verified. Reproduction instructions and artifact paths
are in [DOCKER_ACCEPTANCE.md](DOCKER_ACCEPTANCE.md). The earlier Docker-pending
statements above are historical checkpoints. Final release evaluation still needs
the complete PRD audit and the user's real-model output evaluation.


## Simplified Chinese / English interface — 2026-10-02

The application previously had a Chinese-only interface and a separate Deck
content-language selector. The header and setup dialog now expose a persisted
Simplified Chinese / English interface choice. Notebook management, model setup,
privacy/diagnostics, Reader, Chat, citation preview, Knowledge, transformations,
Deck creation/edit/export, statuses, API/job errors and PDF extraction warnings
use bundled local translations. Document language/title and dates follow the choice.
Counts use complete messages. Source titles/text, questions/answers, generated
content and saved PDFs stay unchanged. New Deck content-language defaults to the
current interface language and remains independently selectable.

Preferences support validated partial updates with transactional merging. Locale
changes preserve telemetry consent, and telemetry updates preserve locale. Existing
preference records default to Chinese without changing consent. Failed saves retain
the previous choice. Only the language is cached in browser storage. Language
changes retain open views, selections and unsaved model, Knowledge and slide edits.
Known error codes receive friendly messages in both languages; unknown failures
get a localized fallback. Provider exception text is not displayed.

Validation: all 153 backend tests, 12 frontend tests, production build and
lint/format checks passed. Translation checks cover referenced interface keys,
matching catalogs and interpolation parameters. Tests exercise partial updates,
old records, rejected languages/nulls, consent preservation and restart persistence;
they also check save failure, disabled browser storage, translated existing errors
and preserved drafts. One pre-existing Starlette test-client deprecation warning
remains; Vite reports the bundled entry over its 500 kB advisory threshold.

All 12 browser flows passed in development (1.1 minutes), then on the newly built
production Docker image (2.7 minutes), with fresh setup checked separately. The
English flow covers settings, EPUB reading, original Chinese content, Knowledge
draft switching/edit/save, citations, Chat, translated scanned-PDF errors, Deck
language choice/generation/download/text editor and reload persistence. Mobile
header controls fit their container; English desktop/mobile screenshots were
visually inspected. Older reader assertions now target the page marker explicitly
and select the localized page label.

The verified Docker image was
`sha256:93d77d3ad95e5ee0fad86fcf38b739d97f5a1114b7eef61b82f6547c865eb695`.
The existing Docker persistence driver also passed process restart and complete
container recreation: all 40 API snapshots, 79 saved files and 16 download hashes
matched, and three encrypted model keys remained usable. Preferences, source/
knowledge/deck state and exported files were intact. These fixture tests did not mount live data.
The native application was updated at the same LAN address; application and
original PDF URLs both returned 200. The reviewed real 15-page PDF retained its
original SHA-256. No live model configuration or telemetry consent was changed.

Manual path: refresh the application, choose English in the header, open a source
and edit a Knowledge page; switch to Chinese and back, then save. Reload to verify
the preference. Deck output language remains a separate choice. See
[INTERNATIONALIZATION.md](INTERNATIONALIZATION.md) for maintenance and persistence.
The overall V0.1 release/PRD audit and real-output evaluation remain open.

## Paragraph evidence and citation context — 2026-10-02

Some PDF text operations contain a single glyph. Retrieval and citation previews
previously used these raw operations directly, even though the Reader already
displayed readable paragraphs. Questions now receive bounded paragraph evidence
with exact raw source coordinates; duplicate hits in the same paragraph merge.
Expansion respects source/page/node selection and the frozen question scope.
Paragraphs over 1000 estimated tokens split at sentence boundaries when available.
The existing question context budget still applies.

Citation previews show the paragraph containing the referenced text and keep the
original anchor for opening the Reader. Saved one-glyph citations acquire readable
context without modifying their exact quotes, saved answers or provenance. Short
wrapped sentence endings are rejoined on the same page, while headings, new list
items, completed sentences and page boundaries remain separate. Deleted sources
retain an unavailable citation; failed projection falls back to the precise quote.
See [the design decision](decisions/004-paragraph-citation-context.md).

Validation: all 158 backend tests, 14 frontend unit tests, production build,
lint/format and diff checks passed. Tests cover complete paragraph evidence and
provider prompts, exact glyph offsets, scope isolation, duplicate hits, compatibility
characters/ligatures/whitespace, bounded long passages, old citation/restart support,
deleted sources and guarded short-tail joining. All 13 development browser flows
passed; the three affected flows also passed again after the short-tail and location
label adjustments. Desktop/mobile citation screenshots were visually inspected.
The existing Starlette test-client deprecation and Vite entry-size advisory remain.

The final production Docker image was
`sha256:2e26db34baba8156d0fc8ac6c2768c5fc84de086c6d0f1fee16caf1afcbd5e78`.
Fresh setup and all 13 container browser flows passed (2.7 minutes). The persistence
driver generated a 15-page fixture deck and verified both process restart and
complete container recreation: all 40 API snapshots, 79 saved file hashes and 16
download hashes matched; three encrypted model keys remained usable. The isolated
test stack was stopped and never mounted the user's live data.

Read-only checks against the user's existing PDF citations confirmed six old
single-glyph references now return paragraph context. An actual list paragraph's
split sentence ending was repaired to a complete 49-character passage while its
original one-glyph quote and anchor remained exact. After the native application
restart, all 16 saved conversation messages, 5586 citation coordinates, preferences
and hashes of 299 existing source/asset/export/secret files matched the baseline.
The LAN application returned the updated paragraph. No documents were reimported,
indexes rebuilt or existing PDFs regenerated; no real-model request was made for
this correction.

Manual path: refresh the LAN application, open an existing answer and click its
source citation. Confirm readable paragraph context, use Open original to reach
the same page/anchor, then ask a new scoped question and inspect its source. Reimport
and regenerating saved answers are unnecessary. Complex PDF layouts remain subject
to the projection limits described in the design decision.

## Addressable navigation — 2026-10-02

Opening a notebook now changes its address to `/notebooks/{id}`. Refresh and direct
links restore the notebook rather than the homepage. Source addresses retain the
chapter/page and optional exact citation anchor; saved knowledge pages and Decks
have their own paths. Deck page addresses use slide identity rather than ordinal,
so reordering does not change which page a link refers to. Sidebar selection and
explicit source/chapter question scope also survive reload and history navigation.
Notebook cards expose real links, and the document title identifies the notebook.

Browser Back/Forward follows the same draft protection as in-app navigation.
Cancelling navigation preserves the mounted editor and restores the same address.
Accepted slide changes close the old slide editor. Unsent questions and slide
text/revision drafts now participate in leave/reload protection, alongside existing
knowledge drafts. Sidebar-only tab changes keep the same editor and do not ask to
discard it. Identical addresses do not add redundant history entries; initial
chapter/slide resolution replaces the current entry. Late async results cannot
reopen a view after the user has moved elsewhere.
Opening/cancelling Deck creation preserves the existing knowledge draft without an
early discard prompt; actual view changes retain their protection.

Missing/unknown notebook links give a recovery link to the list. Missing sources
and failed/unparsed imports have an explicit error/pending state with a return to
conversation; empty chapter lists finish loading. Stale chapter/slide IDs fall back
to an available location. Initial request failures keep retry controls and the
requested URL. Returning to the notebook list through history refreshes counts.
See [the navigation decision](decisions/005-addressable-navigation.md) for paths
and transient-dialog boundaries. Source text, questions and secrets never enter URLs.

Validation: all 159 backend tests, 20 frontend tests, production build and
lint/format/diff checks passed. The frontend route tests cover path round trips,
malformed paths/parameters, initial deep links, deduplicated pushes, popstate,
rejected-history restoration, sidebar draft preservation and restored/empty
chapters. The backend verifies nested addresses serve the application while missing
API routes remain JSON 404s. All 15 development browser flows passed (1.7 minutes),
including new-tab PDF chapter links, scoped Chat refresh, saved knowledge/Deck
refresh, exact citation anchors and both rejected/accepted knowledge/slide history
transitions. Existing reload flows now assert restored views instead of manually
reopening them. The latest failed-import-link check is also included in the final
production browser suite. Mobile navigation output was visually inspected.

The native app serves the newly built interface without a backend restart. Two
nested LAN URLs returned the new application bundle with HTTP 200, and an existing
49-character paragraph citation remained intact. Read-only verification confirmed
all 16 conversation messages, 5586 citation coordinates, preferences and hashes
of 299 existing source/asset/export/secret files matched the previous baseline.
No real-model requests or live-data migrations were required.

The final production image was
`sha256:523de376b3ad57ab792ca12169c85aab8d5440282b837dffb65924a60277b39f`.
Fresh setup and all 15 container browser flows passed, including the final
Deck-dialog draft check. Both process restart and full container recreation
preserved all 40 API snapshots, 79 saved file hashes, 16 download hashes and three
usable encrypted model keys. The isolated acceptance stack was stopped afterwards.

Manual path: refresh the LAN app, open a notebook and note its address. Open a
source and select another chapter; reload or open that address in a new tab.
Try Back/Forward, a saved knowledge page and a Deck's second page. Edit a knowledge
page or slide, press Back and cancel: both the URL and draft should remain. Accept
leaving to discard the unsaved draft. The native browser also protects reloads
while a registered draft is dirty.

## Reader continuation and genuine directory — 2026-10-02

Readers now offer previous/next chapter controls above the text and at its footer.
Moving from the footer scrolls and focuses the next text. EPUB inline headings do
not duplicate chapter stops. Markdown uses authored headings when no chapter nodes
exist. A PDF directory contains only actual outline chapters, with pages kept in
independent page controls. A PDF without an outline has no invented directory;
previous/next page and a bounded page-number jump remain available. Plain TXT has
no fabricated chapter selector. Boundary buttons are disabled.

Page jumps and citation links highlight the containing chapter when one exists.
Chapter/page identities remain in the source URL, preserving refresh and history
behavior. Resolving another citation on the same page finishes without a spinner.
Canonicalizing a locally selected node into the URL preserves the mounted article,
scroll and keyboard focus. Question/generation actions now describe the selected
page, chapter or whole source and use the matching scope. Both interface languages
cover all new controls; source content remains unchanged.
See [the reading-navigation decision](decisions/006-reading-navigation.md).

Validation: all 25 frontend tests, typecheck, production build and format/diff
checks passed. All 15 development browser flows passed; after the final focus
correction, all six affected reading/citation/navigation flows passed again.
The PDF outline flow also passed a viewport screenshot check after page jumping.
Desktop and mobile screenshots were visually inspected. Coverage includes footer
continuation, duplicated EPUB headings, real PDF outline-only options, empty/plain
sources, no-outline page navigation, URL reload/history, exact scopes, same-page
citation changes and canonicalization without unmounting a focused article.
The existing Vite bundle-size advisory remains.

The native LAN application returned HTTP 200 with the new reader bundle. A saved
34-page PDF has no outline and now uses page navigation without a directory.
Read-only checks confirmed all 16 messages, 5586 citation coordinates, preferences
and hashes of 299 existing files matched the previous baseline. No reimport,
reindexing, real-model requests or saved-PDF regeneration were required.

The final production image was
`sha256:9a21786c7d7f4d68549dbf92e2805087d7484358d90dd2e6763277761420a6c6`.
Fresh setup and all 15 container browser flows passed (2.9 minutes), including the
final focus/viewport assertions. Both process restart and complete container
recreation preserved all 40 API snapshots, 79 file hashes, 16 download hashes and
three usable encrypted model keys. A 15-page fixture Deck was generated for the
persistence check. The isolated test stack was stopped and never mounted live data.
A stale Colima VM was recovered using its existing disks/configuration before this
final run; see [Docker acceptance](DOCKER_ACCEPTANCE.md).

Manual path: refresh the LAN app, open an EPUB or PDF with an outline and use Next
chapter at the footer. Confirm the new text starts in view and the address changes.
Reload the address. Open a PDF without an outline: there should be no chapter
selector; use next/previous page and enter a page number. Check the first/last
boundary buttons, a source citation and page-specific question controls.

## Integrated explanatory page scenes — 2026-10-02

Both user reference PDFs (15 and 14 pages) and the previous real 15-page output
were rendered for local visual comparison. Reference pages show relationships as
primary visual content: staged journeys, contrasts, cycles, spatial boundaries and
labels beside their subjects. Their artwork and factual claims are not reused as
source evidence. See [the page-design decision](decisions/007-integrated-page-design.md).

New Decks persist a validated composition before image generation. The model plans
free-form visual grammar and a display-copy budget per page. Art prompts receive
image-local reading zones from that composition; final rendering checks actual
painted contrast. Compact summaries of prior designs guide page rhythm. Native
curves, closed paths, two-ended arrows, gradients, restrained shadows/glow and image
crop focus/masks/blending extend the drawing vocabulary. Original-source citations
also cover saved visual relationships, each represented once by its native path.
Words remain editable and searchable. Old Deck versions and their exact V2 asset
signature shape remain compatible; retry cannot silently promote a saved Deck.

Validation: the full backend suite passed 168 tests; a subsequently added forged
relationship-citation regression passed with all seven plan-quality cases. All 25
frontend tests, production build, format/lint and diff checks passed. All 15 native
browser flows passed (2.4 minutes). Real Chromium tests paint gradients, curved and
filled paths, masked/blended artwork and verify searchable Chinese text; preflight
rejects overflow before any image request. Other new checks cover design-before-art
ordering, local coordinates, copy budgets, citation identities, retry caching and
legacy asset visibility/reuse.

Production image `sha256:ba6c31d75a8ffc6d68794e04675cab8985ed648adc62b9cf48beb0e30a779ee7`
passed fresh setup and all 15 Docker browser flows (3.3 minutes). An initial run
encountered a socket reset while deleting a test-only notebook after all reader
assertions had passed; server logs showed no exception. A complete rerun from an
empty data directory passed unchanged. Process restart and full container recreation
both preserved 40 API snapshots, 79 file hashes, 16 download hashes and three usable
encrypted model keys. The persistence sample includes a newly generated 15-page
fixture Deck. The isolated acceptance stack was stopped without mounting live data.

The native application was restarted with the new migration and renderer. A separate
real 15-page Deck is being generated from the previously authorized paper PDF with
the user's configured language/image services; both older Decks are retained. The
first actual scenes have been inspected, but full real-output review remains in
progress. Fixture success is not evidence of NotebookLM visual parity. Original
16 messages, 5586 citation-span rows, preferences and hashes of 299 baseline files
were unchanged during generation.

## Complete image-generated Deck pages — 2026-10-02

The user chose to merge composition, artwork and final rendering into one image
model output containing the entire page: text, illustrations and diagrams. New
Decks now default to this mode, while saved native Decks retain their previous
pipeline. A saved native Deck can create an independent whole-page copy using its
exact grounded content, plan and style. No native RenderSpec request or text/arrow
overlay runs for image pages. See [the whole-page decision](decisions/008-whole-page-image-generation.md).

Each page saves its exact prompt, model identity, actual bitmap dimensions and
versioned content signature. Text, visual and image revisions regenerate the
complete selected page and preserve unchanged siblings. Failed pages retry without
repeating successful images; they cannot skip their required complete-page image.
Missing derived renders rebuild from the saved asset. The UI explains text edits,
exposes the authored draft and original-source citations, and provides inline PDF
preview. Raster PDFs preserve the image losslessly with title bookmarks. They have
no selectable text layer because character positions have not been measured; saved
native Decks retain their measured searchable text.

Validation: all 181 backend tests passed. After the final revision-prompt and
semantic-render-signature changes, all 10 affected whole-page tests passed again.
All 25 frontend tests, production build, lint/format/diff checks and all 16 native
browser flows passed. Coverage includes image-model requirements, one complete
image request per authored page, absence of native composition calls, omission of
internal evidence IDs, single-page revisions, unchanged siblings, failed-image
retry, original Deck preservation, original-source citation identity, stale
exports, lossless PDF pixels, bookmarks, raster-only extraction and restart.

Final production image
`sha256:a517a013f63c551a2f3d6234a254c5cc83431ebfa176b7afc04b76739de06f7c`
passed fresh setup and all 16 Docker browser flows (3.2 minutes). An earlier run
passed 15 flows but exposed a race in the new test: an absent pending PDF was
incorrectly accepted as a different completed export. The test now waits for a
ready Deck, completed job and ready new export before inspecting the saved asset.
A complete fresh production run passed. Process restart and full container
recreation each preserved 40 API snapshots, 79 saved file hashes, 16 download hashes
and three decryptable model keys. A new 15-page whole-image fixture Deck participates
in persistence verification. The isolated stack was stopped and never mounted live
application data.

Real-provider acceptance used an independent 15-page copy of the previously
authorized research-paper Deck with the configured local language/image services.
All 15 complete pages finished in 856118 ms (approximately 14.3 minutes). The
provider returned 1672x941 pixels for each requested 2048x1152 page; those actual
dimensions passed the widescreen validation and were retained without cropping,
stretching or native overlays. Every full-size page was inspected against its saved
copy, and all exported PDF pages were rendered for visual review. Core authored
content and source qualifiers remained readable; no obvious broken glyphs, clipping
or overlap were observed.

This does not certify exact image-text compliance. Some generated pages added
diagram labels outside the saved text draft, such as topic/process labels; several
included platform logos despite the prompt. The asset records
`text_verification=not_automated`. Original-source citations remain available for
review, but checking those citations is not OCR or verification of every visible
word. Automated image-text checking is not implemented, and user evaluation of
visual quality against the NotebookLM references remains open.

The final real PDF has 15 pages, 15 title bookmarks and 53928492 bytes. Its SHA-256 is
`42f85a9e12f193797bdecfe6c05b9509175c07aef598ee42e2cbea019def5f1a`.
Every embedded page image matched its saved PNG pixel-for-pixel; text extraction
confirmed the expected raster-only output. The final application was restarted
with the completed implementation. Read-only LAN checks confirmed the Deck deep
link and health endpoint, an inline byte-range PDF preview, all 36 saved-page source
citations (2853 exact original spans) and authored copy preservation. All original
16 messages, 5586 citation-coordinate rows, preferences and hashes of 299 baseline files were
unchanged after restart; no jobs remained queued or running.

Manual path: open the new real Deck through its notebook address, inspect each
page and compare “View page text draft” with the image. Open an original-source
citation and preview the PDF. On a saved native Deck, choose “Create whole-page
copy” to retain the original. Edit a page's text or request a visual change: only
that complete page regenerates, and the current PDF is rebuilt. Failed pages offer
retry while preserving other saved pages. Reload the Deck address to restore it.

## Whole-deck visual expression — 2026-10-02

Phase 22 reviews eight public projects and the original PPTAgent paper, including
baoyu-skills, SlideSpeak, Nano Banana PPT, Banana Slides, Presentation Skill,
Presenton and Anthropic's PPTX guidance. Sources are pinned and compared in
[the visual-expression research](research/deck-visual-expression.md). External
skills were research material; no third-party skill, code or runtime was installed.

New V5 Decks coordinate a visual repertoire after all page content is saved. A
13-form explanatory vocabulary separates shared drawing/typography identity from
page subjects, reading surfaces, viewpoints, text placement and spatial composition.
Source prerequisites prevent unsupported quotations, numbers, comparisons and
branches. Whole-deck guards reject repeated adjacent forms, excessive form use,
uniform framing and identical layout descriptions. Planning failure preserves
authored copy and retries before images. The bilingual UI exposes the initial
visual plan with an explicit distinction between planning statistics and actual
bitmap verification. Existing native and V4 image Decks keep their original paths
and signatures. An independent visual copy retains current ordered content and
citations, including after page deletion, and receives a fresh plan for its new IDs.

All 193 backend tests passed; all 22 affected whole-page/art-direction tests passed
again after the final palette wording adjustment. All 25 frontend tests and the
production build passed, as did lint, formatting and diff checks. Coverage includes
source eligibility, plan repetition, incomplete content, invalid-plan repair,
retry without reauthoring saved text, copy-of-copy identity, shortened Decks,
per-page caching, unchanged siblings, V4 signature compatibility and priority
composition instructions. The expanded browser flow exercises visual-plan viewing,
whole-page editing, failure retry and a second visual copy while preserving both
original versions. Native browser regression exercised all existing flows, with
affected flows rerun after fixing the standalone mock provider's new-stage routing.

Final production image
`sha256:bf79d86569b34820e47a2aae2df5efcbf86276c303071015be719f51eedf0c60`
passed first setup and all 16 Docker browser flows in 3.4 minutes. Process restart
and full container recreation each preserved 40 API snapshots, 79 saved file
hashes, 16 download hashes and three decryptable model keys. The V5 15-page fixture
participates in persistence verification. The isolated stack was stopped and did
not mount live application data.

Real-provider acceptance used an independent copy of the authorized 15-page paper
Deck, with the same saved content, palette and original sources. Initial planning
exposed an overly narrow typography-description length bound and a form lacking
its source prerequisite. The reasonable description bound and repair feedback were
adjusted; source eligibility was retained. First image review then showed that late
JSON art metadata still allowed generic scenery to override some intended forms.
The final `whole-page-v3` prompt puts the concrete subject, view, reading surface,
spatial arrangement and reading path first. The acceptance task resumed through the
normal queue after restart and regenerated its own initial images. Original Decks
and the previously running user task were preserved; that user task completed before
the service was first switched.

The final saved plan has ten forms, six viewpoints, six text placements and
dark/light/mid-tone counts of 6/5/4, with no consecutive identical forms. These are
**plan measurements**, not automatic image ratings. Actual full-size review covered
all 15 pages against their saved text, plus all exported PDF pages. Examples include
a conceptual section on page 2, a central interview folio on page 3, material-analysis
frames on page 4, a quotation object on page 7, paired participant accounts on page
8, a governance section on page 9 and case frames on page 10. The imagery retains a
shared illustrated palette while varying the focal structure and reading surface.
No obvious broken glyphs, clipped content or overlapping body text were observed.

This does not certify every visible word or every initial composition choice.
Some pages still add platform symbols despite the instruction, repeat participant
illustrations or stylize list numbering and quotation punctuation. Page 13 resolves
its abstract evidence object as a landscape rather than a literal close-up object.
Automated OCR, semantic image scoring and reference-image conditioning are not
implemented. The application records `text_verification=not_automated`; saved copy
and original-source references remain available for human comparison. Evaluation
against the user's NotebookLM references remains a user judgment.

All 15 final renders use `whole-page-v3`. The model returned 1672x940 or 1672x941
images for the requested 2048x1152 size; actual dimensions were retained. The final
resumed image-generation run completed in approximately 12.8 minutes, excluding
the earlier planning and image iterations. The final PDF has 15 pages, 15 title
bookmarks and 49377481 bytes, SHA-256
`baafe4d5159fd41208eb6434d73e99dcb9e5f35eeef5cc490e669b306bab1f32`.
Every embedded image matched its saved PNG pixel-for-pixel. Raster-only extraction
is expected. All 15 PDF pages were rendered with Poppler and visually reviewed.
LAN checks verified the Deck deep link and all 36 available citations with 2853
identical original-source spans. All 23 baseline messages, 13054 original citation
coordinate rows, other baseline records, preferences and hashes of 509 existing
files were preserved.

Manual path: open a saved Deck and create a visual copy; inspect “View visual plan”
and the actual pages together. Compare page text drafts and original-source citations,
then preview the PDF. Editing or retrying a page preserves other saved pages. To
replan the whole visual sequence, create another independent visually refined copy.

## Direct source content, concurrent images and stable Deck navigation (phase 23)

Accepted on 2026-10-02. The root cause of unsolicited commentary was the narrative
and author prompts: they requested interpretation, caveats and source notes, which
were saved as visible copy and then painted by the image model. New brief, plan and
author prompts present source content directly. Added author-opinion headings,
boundary/disclaimer notes and external descriptions of the author's metaphors
receive structured repair feedback. Actual original quotations and factual scope
remain available. New content uses `source-content-v1` / `whole-page-v4`; legacy
prompt versions and image signatures remain unchanged.

The bilingual “重写内容副本” / “Rewrite content as a copy” action preserves the
original Deck and reauthors all pages from the same original evidence, ordered
plan and style, then creates fresh coordinated art, images and PDF. A visual-only
copy still preserves its saved text. Existing baked-in text is removed by reauthoring
and regenerating images, not by hiding metadata in the viewer.

Whole-page rendering now uses bounded concurrent workers, default 2 with the
`IMAGE_GENERATION_CONCURRENCY=1–4` configuration available locally and in Compose.
Tests verified limits 1 and 2, completion out of order with correct PDF bookmark
order, monotonic progress, per-page failures/retry, and shutdown cancelling all
inflight requests before queued work resumes. Original native rendering stays
serial and the one-heavy-job application queue is unchanged.

Real-provider sampling used pages 2 and 15 of the user's existing authorized
20-page Deck. Four image calls with identical page prompts compared serial
82.403 seconds to two concurrent requests taking 45.893 seconds: 44.3% lower
elapsed time in this single comparison. Both concurrent requests started within
1 ms and every result was a valid 1672×941 PNG. An initially added author/metaphor
caption was caught during visual QA; after strengthening the author check, a
final rewritten pair completed in parallel in 54.294 seconds, and both images
were manually checked against saved copy. The unwanted commentary was absent.
Reports and images are in `<private-verification-path>` and
`<private-verification-path>`. This is a two-page capability
and quality check, not a full 20-page regeneration or a throughput guarantee.

The viewer has independent thumbnail and preview scrolling, selected-page
visibility without ancestor scrolling, right-pane reset on page selection,
complete-image fitting, collapsed narrative/style details and a horizontal rail
on narrow screens. Native browser acceptance checked the last thumbnail and
entire image inside the visible preview, editable text, source citations, new
content-copy flow, deep links, history and language persistence. Viewport screenshots
avoid full-page screenshot capture changing the scroll position of nested scrollers.

Final verification: 205 backend tests; 25 frontend tests; Ruff and Prettier;
production frontend build; generated-pages native browser flow and three bilingual/
navigation browser flows; all 16 Docker browser flows, followed by container
restart and recreate integrity checks. Native and Docker traces used separate
output directories after an earlier overlap removed each other's trace files.
Final Docker log: `<private-verification-path>`;
isolated data: `.docker-acceptance-data.9RPgCX`.

The LAN application was restarted only after active jobs finished, and its health,
existing 20-page Deck and direct URL were checked read-only. All database records
and 611 file hashes captured immediately before deployment were preserved after
restart, including the user's separately completed single-page revision during
acceptance. Original sources, model configurations and secrets remain intact.
Automatic semantic/OCR verification of arbitrary generated images remains open.

Manual path: refresh the LAN application, open a saved Deck, scroll to the last
thumbnail and select it while keeping the image visible. To remove commentary
already painted into old images, choose “重写内容副本”, then compare its saved
text, images and original citations with the unchanged original Deck.

## Persisted image concurrency in model settings (phase 24)

Accepted on 2026-10-02. “模型设置 → 图片模型 → 图片生成并发数” now supports
1–20, with a separate “保存并发设置” action. The default remains 2; 1 is serial.
Saving does not run provider capability tests or generate test images. The same
controls, help, confirmation and retry errors are available in English. Loading
failure prevents an accidental overwrite; saving failure preserves the draft.

`GET/PUT /api/settings/models/image-generation` validates strict integers and
persists them separately from model credentials, language and telemetry. Saved
settings override `IMAGE_GENERATION_CONCURRENCY`, whose range is also 1–20.
No database migration is needed. Each Deck run snapshots the limit before its
first model request and records it in completion metadata. Queued jobs and retries
use the setting when they start; an active run keeps its original limit.

Delayed mock-provider tests observed actual image-request peaks of 1, 2 and 20,
with monotonic progress and the original PDF bookmark order. Changing to 20 during
authoring kept the active run at 2. API tests verified strict bounds, no provider
calls on save, settings precedence across an actual restart, and unchanged model
configurations, encrypted secret files and language/telemetry preferences.
This verifies application scheduling, not the capacity of every real provider.

Checks: 218 backend tests, 28 frontend tests, Ruff, Prettier and production build
passed. The isolated native browser flow verified saving 20 without a model test,
refresh/reopen persistence, draft preservation across language changes, and a
usable desktop/mobile layout. Screenshots are in
`frontend/test-results/image-concurrency-settings{,-mobile}.png`.

All 17 Docker browser flows passed on the production image, after first setup on
an empty isolated database. A saved concurrency of 20 then survived both process
restart and complete container recreation. All 41 API snapshots, 16 download
hashes and 79 persisted file hashes matched; all three saved model keys decrypted.
Docker manifest list: `sha256:8b63a8abb4ecd7a61247a40175a2f5ada5ba37db4bfb669cf374cb2e4c859bc4`.
Log: `<private-verification-path>`; isolated retained data:
`.docker-acceptance-data.7jfucu`. The test stack was stopped after acceptance.

The LAN application was updated after verifying no queued/running jobs. Read-only
checks confirmed its health, the new 1–20 API and the existing 20-page Deck. All
42,020 database records and hashes of 612 persisted files captured immediately
before deployment were identical afterwards. The user's current limit remains 2.

Manual path: refresh the LAN application, open model settings, choose an image
concurrency between 1 and 20, save, then close/reopen settings or refresh. The value
remains saved; subsequent Deck runs use it without restarting the application.

## Word, source images and chapter selection (phases 25–27)

Accepted and deployed to the LAN application on 2026-10-02. Upload accepts `.docx`
alongside EPUB, PDF, Markdown and TXT. Word body paragraphs, headings, lists,
tables and embedded raster images are normalized without executing fields or
fetching external images. Legacy `.doc` conversion and exact Word page layout
are deferred as agreed. Hostile archives and image relationships are rejected.

The saved language model reads embedded images and rendered scanned PDF pages.
Model settings offer an independent image-input capability test. Reading and
citations retain original PNG previews, label recognized content as AI-derived,
and expose uncertain/failed results. Successful transcripts survive retry and
model changes; partial failures can be retried without replacing successful facts.
Changed content invalidates stale retrieval chunks. Existing imported documents
are not automatically sent to a model during upgrade; their reader provides an
explicit recognition action. An open reader refreshes completed recognition while
retaining its current chapter. Source OCR is sequential and independent of the
saved 1–20 Deck image-generation concurrency setting.

Deck creation supports selecting, selecting all and clearing real PDF bookmark
chapters, EPUB directory entries and Word headings. Multiple selections combine
into one Deck, in original order, including descendant sections and deduplicating
overlap. Empty selections cannot generate. The frozen scope survives retry and
reload. Source/block checks exclude unselected content even where a retrieval
chunk spans chapters. Legacy EPUB directory anchors on non-heading elements get
derived navigation without rewriting existing block identities: read-only checks
on the existing 16-entry book mapped all 16 entries, including 12 derived sections.
PDF bookmark boundaries are page-level; PDFs without a directory do not invent
one chapter per page.

Automated checks passed: 237 backend tests, 32 frontend tests, Ruff, Prettier,
TypeScript and the production build. Targeted backend checks covered the final
legacy-directory projection changes after the full suite. Browser acceptance
covered all 18 flows across the full runs and targeted reruns after fixes. A
production-image run passed 17 existing flows; the new Word/scanned-PDF/chapter
flow passed on the final image, including original images, a scoped 10-page Deck,
citations, refresh and mobile checkbox layout. Screenshots are in
`frontend/test-results/{illustrated.docx-reader,scan-with-toc.pdf-reader,chapter-selection-mobile}.png`.

The final Docker check imported seven formats, generated a 15-page PDF, and
verified 54 API snapshots, 19 download hashes and 154 persisted file hashes after
both process restart and full container recreation. All three saved encrypted
model keys decrypted. The isolated test stack was stopped. Final manifest list:
`sha256:2cad1333747d2857c156ff9adc46263b28b16f92873a46037ca85dc3292c638c`.
Log: `<private-verification-path>`; retained isolated data:
`.docker-acceptance-data.7Sz2FO`.

Real recognition used `gpt-6-luna` through the previously authorized
`localhost:8317/v1` endpoint, with one page from each of the two authorized PDFs
and a Word file embedding the first page. The image-input probe, two-page scanned
PDF, Word image, cached retry, chapter-scoped synthesis and original-image citation
all passed. Transcripts were checked against extracted source text and original
images. Text similarity in this small sample was 0.9693–0.9706; this is not a
general OCR accuracy estimate. Report:
`<private-verification-path>`.
Automatic approval rejected a proposed real test that also invoked the embedding
service on localhost:8080 because that endpoint was outside the prior transfer
authorization. The completed real test was restricted to 8317; 8080 was neither
configured nor called. Retrieval/index integration was verified with the isolated
synthetic provider instead.

Before deployment, an SQLite backup and migration rehearsal preserved all
53,731 existing records across 28 application tables, excluding migration history.
After startup, every captured record and all 614 persisted file hashes matched,
foreign-key integrity passed, and migration 014 was recorded. Model configuration,
saved concurrency 2, original sources, prior Decks and credentials were unchanged.
Read-only HTTP checks confirmed the LAN frontend, new interfaces and the existing
20-page Deck/PDF download. Backup and comparison state:
`<private-verification-path>`.

Manual path: refresh `http://192.0.2.10:3000/`, open model settings and test the
language model's image recognition. Upload a `.docx` or scan and open its reader
to compare recognized paragraphs with the original image. For existing files,
choose “识别文档图片”. Open “生成 Visual Deck”, choose a source, enable “只使用所选章节”,
select chapters and generate. Poor scans and complex figures still need comparison
with their original image; capability depends on the configured language model.

## Separate Decks and chapter directory tree (phase 28)

Accepted and deployed on 2026-10-03. The creation dialog defaults to merged
generation and offers separate generation by participating source or selected
chapter. Source subsets can be chosen inside the dialog. It displays the Deck
count, pages per Deck and total pages before submission. Each independent Deck
retains its scope, source label, queue/progress, citations, images, PDF and retry.
The library displays source/chapter labels after generated titles replace initial
labels. An unsuccessful sibling does not rewrite completed Decks.

The directory is a tree with expand/collapse, mixed parent checkboxes, keyboard
navigation and selection by relative directory level. Selecting a parent covers
its descendants and creates one Deck in separate mode. Selecting level two creates
one Deck per selected second-level subtree. Excluding a child removes its ancestor
scope so excluded content is not silently reintroduced. Empty selections block
generation; linked multi-chapter scopes restore their choices. Mobile checks found
and fixed intrinsic fieldset width and unwrapped actions causing horizontal
overflow. Radio labels and chapter checkboxes align with their text.

Batch creation preflights all choices and publishes every Deck/job plus its receipt
in one transaction. Failed insertion rolls back all work. Repeating the same key
and body reuses the original identities, including after restart and selection
changes; a changed body conflicts. Browser network retry preserves the key and
draft, including across interface language changes. Each batch supports at most
100 Decks. Jobs use insertion order to break equal creation timestamps. Full details
are in [decision 013](decisions/013-separate-decks-and-chapter-tree.md).

245 backend tests, 37 frontend tests, Ruff, Prettier, TypeScript and production
build passed. New backend tests generated separately scoped EPUB/PDF/Word Decks,
checked exact citations, source order, queued restart, repeated requests, rollback,
bounds, invalid/empty selections and independent failure/retry. Native browser
checks passed the new separate-generation flow and the existing document/merged
chapter flow. The new flow produced two source Decks plus two chapter Decks and
checked their independent exports and exclusion of parent-only/other-chapter text.

The production-image browser suite passed 18 of 19 flows. The remaining old test
counted all radio inputs and assumed only three page-count radios; it was updated
to check the page-count group and default merged mode, then passed on the same
image. Thus all 19 flows passed across the full run and targeted rerun, including
English, navigation, image concurrency and mobile directory selection.
Logs: `<private-verification-path>`.
Reviewed desktop/mobile screenshots are retained in
`<private-verification-path>` and copied back to
`frontend/test-results/deck-batch-tree{,-mobile}.png` after the final targeted run.

Docker acceptance retained eight sources, the revised 15-page main Deck and two
separate 10-page chapter Decks. Both process restart and full recreation preserved
81 API snapshots, 41 download hashes and 172 persisted file hashes. Three saved
keys decrypted, and repeating the batch request returned the same batch/Deck IDs.
Manifest list: `sha256:917d69637b8482bcfe92a06718a2b9bc9c9db870089c3f292b35989f22ee070e`.
Retained isolated data: `.docker-acceptance-data.a0cItY`; the test stack was stopped.
All new model calls used the isolated synthetic provider, with no user material
transferred to a real provider.

An SQLite backup and migration rehearsal preceded the LAN upgrade. After migration
015, every one of the 53,731 existing records and 614 persisted file hashes matched
the captured baseline. The new batch table was empty and foreign-key integrity
passed. Read-only checks verified the new frontend/API, saved concurrency 2 and
the existing 20-page Deck/PDF. Backup/comparison state:
`<private-verification-path>`. The native server was started
in its own process session with detached standard input/output so it can continue
serving the LAN independently of the tool terminal; local log:
`<private-verification-path>`.

Manual path: refresh the LAN application, open “生成 Visual Deck” and choose
“每份资料 / 章节分别生成”. Use the selected-source subset for one Deck per source,
or choose a source and enable “只使用所选章节”. Expand its directory or choose a
level, check the displayed Deck/page totals and generate. View each Deck in the
library. To combine the same selections, choose “合并生成一份 Deck”.

## Phase 29 — Deck lifecycle controls and spacious preview (2026-10-03)

The viewer now gives the preview its own dynamic-viewport height instead of the
space left after the heading and controls. It has a 520px minimum in the normal
workspace, independent thumbnail/content scrolling and fitted images. Tablets
use the full workspace width with library panels below. Focus preview covers the
viewport, provides previous/next page controls, contains keyboard focus and restores
scrolling/focus on Escape. Editors and original-source citation dialogs remain
operable above the focus layer. Desktop (1440×900), iPad landscape (1024×768), iPad
portrait (768×1024) and phone (390×844) browser checks passed without horizontal
overflow. Reviewed fixture screenshots: `<private-verification-path>`.

The viewer and Studio offer stop/resume for queued or running Deck work and confirmed
deletion for every Deck. Stop persists cancellation before interrupting and joining
work, including parallel page workers and image/PDF writing threads. It preserves
saved output and does not automatically restart. Resume uses the original job and
payload and reuses completed content/images. A stopped page revision resumes without
applying its text change twice. Other Decks keep running after a stop or deletion.
Deletion removes the Deck's jobs, citations, page designs, assets, render/export
versions and queued file cleanup, while retaining original sources and sibling PDFs.
Batch receipts reject replay after a member was deleted. Superseded library refreshes
cannot bring deleted cards back. Mechanisms and provider cancellation limitations
are described in [decision 014](decisions/014-deck-controls-and-preview.md).

Validation passed 254 distinct backend cases: 253 in the full regression run and
one subsequently added stopped-page-revision case. All 40 frontend tests, TypeScript,
production build, Ruff, Prettier and whitespace checks passed. Four native browser
flows covered Deck batches, lifecycle, generated-page edits and revisions; a final
lifecycle rerun additionally exercised editors and citations inside focus preview.
All model acceptance used isolated synthetic providers, with no user material
transferred to a real provider.

The complete production-image browser run passed all 20 flows. A prior run exposed
an asynchronous library refresh after deletion; the refresh was fixed before that
complete successful run. A final image additionally corrected focus/dialog layering
and passed the enhanced lifecycle flow. The acceptance host initially selected an
older system Python for the persistence driver; the script now prefers the project's
Python and checks its version. The final persistence driver passed both application
restart and full container recreation: 83 API snapshots, 41 download hashes and
240 persisted file hashes matched; all three saved keys decrypted, batch identities
were reused, and a retained stopped Deck remained stopped. Final manifest list:
`sha256:2ec81763357e3212026006b0be6973377b876af5649e02d1e6c47f88ba888e46`.
Retained isolated data: `.docker-acceptance-data.B6NXoR`; the acceptance stack is stopped.
Logs: `<private-verification-path>`.

The existing user-started 15-page Deck completed before deployment. The LAN update
was performed with no running/queued jobs. An SQLite backup and comparison captured
54,879 records and 797 persisted files; all old records and file hashes matched
after startup. No schema migration was required. Backup/comparison state:
`<private-verification-path>`. Read-only LAN checks verified
HTTP 200, the final frontend, new lifecycle endpoints and the existing completed
Deck/PDF. The application continues in its detached process session; log:
`<private-verification-path>`.

Manual path: refresh the LAN application and open a Deck. Scroll to its larger
preview or choose “专注预览”; use page controls and Escape/“退出专注预览” to return.
Use “停止生成” for a running/queued Deck, then “继续生成” to resume saved progress.
Use “删除 Deck” in the viewer or the deletion action on its Studio card and confirm
the named Deck. Deletion returns an open Deck to the notebook conversation.

## Phase 30 — User-directed interpretation without rigid labels (2026-10-03)

Deck generation now allows relevant model-knowledge explanations, conceptual
reasoning and illustrative examples. Explicit supplemental and page-revision
requests override presentation defaults while authentic source facts, quotations,
IDs and technical limits remain required. Preferences are resolved before source
reading and persisted once per Deck. Source-only requests still allow close reading
but exclude outside background and invented examples. The original source-grounded
Chat, Knowledge and transformation policies are unchanged.

The supplemental instruction and selected-source/chapter titles reach every Deck
synthesis level. Authors receive the complete dossier. Internal source/interpretation/
background/analogy provenance distinguishes passage anchors from model elaboration;
background and examples cannot carry source IDs, including inherited list citations.
These fields never become visible headings. Default editorial labels and boilerplate
are repaired, while explicit requests may override that style default. Detailed
reasoning keeps ordinary page density; explicitly requested dense copy can use a
larger bounded budget. See [decision 015](decisions/015-user-directed-deck-interpretation.md).

Content-rewritten copies refresh their research and planning at standard lengths,
retaining original Decks, actual page counts and shared style. A manually shortened
nonstandard Deck instead retains its dossier/evidence IDs and page sequence while
refreshing its brief and text. This prevents both stale evidence IDs and resurrection
of deleted pages. Visual-only copies and stopped-task resume retain saved content.
No database migration is required.

The full backend regression passed 265 cases using installed Chrome for rendering.
After the final source-only refinement and shortened-copy safeguard, 34 targeted
cases passed, including two additional page-precedence/shortened-copy scenarios:
267 distinct backend cases in total. All 40 frontend tests, TypeScript/production
build, Ruff/format, Prettier and whitespace checks passed. Two isolated native browser
flows verified full-page generation, citations, PDF download, deep-link refresh,
visual/content copies, page text changes and image failure recovery. An earlier
sandboxed backend run could not launch Chromium; rerunning with Chrome outside that
sandbox passed. A call-count assertion was updated for the new page preference step.

Real textual sampling used the currently configured `gpt-6-luna` through the local
localhost:8317 gateway with private-example-A's original chapter material, in private isolated
SQLite snapshots. “求救的叫声” produced an overview, close reading and an authored
page interpreting the tension between sympathy and action. A specific revision
request for “另一曲舞蹈之歌” additionally produced model-background explanation and
a clearly illustrative everyday analogy; both had empty source citations, while
actual quotes and readings retained their original passage IDs. The three resolved
preferences remained false, correctly treating deeper interpretation and explicit
label negation as requests without editorial scaffolding or dense text. Private
review files: `<private-verification-path>` and
`<private-verification-path>`. No real page images
were generated, and existing Decks were not rewritten during this sampling. These
samples show the mechanism working; they do not establish comprehensive philosophical
accuracy, which still depends on the model and review of the generated content.

The LAN upgrade waited for the user's running 20-page task to finish. An SQLite
backup and complete record/file hash baseline preceded the graceful restart. All
61,849 records and 900 persisted file hashes matched afterward. Health, both sampled
original 15-page Decks and their existing PDF downloads passed read-only checks;
there were no active jobs at upgrade. Backup/comparison state:
`<private-verification-path>`. The detached native
server continues at `http://192.0.2.10:3000/`. Existing complete output is preserved;
new generation or an explicit content-rewritten copy applies the new mechanism.

## Phase 32 — Automatic parent-work context for chapter Decks (2026-10-03)

Chapter/node Deck generation now reads the entire uploaded parent work, hierarchically
for long inputs, and supplies a source-grounded reading map beside the selected chapter.
The map is reusable across chapters and invalidates on source, structural, model or
prompt changes. It retains original block spans and uses short dossier-local work IDs
separate from primary chapter IDs. Explicit chapter-only instructions skip wider context;
source-only instructions exclude external model knowledge while allowing uploaded book
material. Whole-source generation avoids this extra pass. Chat, Knowledge, existing
snapshots, visual-only copies and stopped-task resume keep their previous contracts.
See [decision 017](decisions/017-automatic-parent-work-context.md).

The full backend regression passed 284 cases with installed Chrome. After the real-model
TOC/provenance refinements, 41 affected backend cases passed; the new EPUB ancestry case
brings the distinct covered total to 285. All 40 frontend tests, Ruff, formatting and
whitespace checks passed. The initial sandboxed full run could not launch Chromium;
23 renderer/PDF cases then passed with installed Chrome before the successful full run.
Migration count expectations were updated for the new disposable work-context table.
Later short-ID refinement passed the 10 context cases and the synthesis repair case.
After page-specific citation context and the visible-marker regression were added,
42 affected backend cases passed, bringing distinct covered cases to 286.

Real textual acceptance used private-example-A’s “伟大的渴望” with the configured `gpt-6-luna`
through the authorized localhost:8317 gateway in a private SQLite snapshot. All 5,098
source blocks were read in five segments; the final map retained 79 original evidence
packets. The dossier correctly used the book TOC path “第三部 → 伟大的渴望”, connected
the chapter’s negation/affirmation to “三段变化”, and linked its song imagery to the
chapter’s position after “康复者”. Two authored pages passed schema, provenance,
per-page citation and reading-budget checks, with no images generated. Review:
`<private-verification-path>`. This sampling confirms
context integration, not exhaustive philosophical accuracy. Existing Decks were unchanged.

Real validation exposed three issues that were addressed before completion: flattened
EPUB reading nodes hid actual book-part ancestry; long hexadecimal work markers suffered
transcription errors; page authors reused work IDs not present in their page’s evidence.
The final flow preserves TOC ancestry, short dossier-local work IDs and full explanatory
prose with only the page’s permitted markers. Added visible internal markers receive
actionable repair feedback. Invalid outputs are never cached as successful reading maps.

The local application at `http://127.0.0.1:3000/` was upgraded with no queued/running
jobs. The pre-migration backup is
`<private-verification-path>`; existing table rows and
all 1,454 file hashes matched, with only migration 016 and its empty cache table added.
The final page-author update used a second independent baseline,
`<private-verification-path>`. All 71,545 current
records and the same file hashes matched after restart. Health and four existing
15-page Deck/PDF downloads passed, including the currently viewed “伟大的渴望” Deck.
No existing Deck was rewritten. New chapter generation or a standard-length
content-rewritten copy uses the new context; visual-only copies preserve saved content.
No new Docker or UI browser flow was run for this backend-only context enhancement.
# Original source pixels in Deck interpretation — 2026-10-03

Deck dossier synthesis and automatic whole-work reading now send registered source images
alongside the corresponding evidence text. Page authors re-read originals belonging to
their own evidence. Source figures retain separate evidence packets; empty image transcripts
can use an available original image as a citation, with empty quotes and zero text offsets.
Ordinary zero-width text spans remain invalid. No source text is fabricated or overwritten.
Images and visible document instructions remain untrusted data.

The first reading covers every eligible image in groups bounded by image count and context.
Page attachment counts adapt to remaining context, and additional originals are listed as
not reattached. Checkpoint/work-map hashes include original-image checksums and visual
policy/version. Missing media or unsupported image input fails explicitly; retry retains
the originals. Visual guidance reaches art direction and the final page prompt, and the
whole-page PDF export regression still passes.

Validation: the full native-Chrome backend run passed 298 tests, recorded at
`<private-verification-path>`. Thirteen dedicated original-image
cases additionally cover scope boundaries, incomplete transcripts, complete batched image
reading, context-aware page review, pixel changes, repair/retry, missing media, captionless
citations, mixed image/text citation projection, rejection of zero-width ordinary text,
and art/final-page/PDF flow. Subsequent targeted regression passed 41 cases covering the final
context-budget and citation changes; the preceding generated-page/lifecycle/passage/chat
run passed 54 cases. Frontend code and the existing deployed bundle are unchanged.

Two real checks used the existing Discord PDF through the already authorized
`localhost:8317` gateway with the configured `gpt-6-luna`, in private database/source copies:

- `<private-verification-path>`
- `<private-verification-path>`

Both dossier and page authors received an actual source image. The second check deliberately
removed its recognition transcript only in the isolated copy. The model still described
navigation/search, the four-column server-card grid, its discovery mechanism and truncated
lower content; citation/spec/content-basis/reading-budget validation passed. The sampled
layout was visually checked against the saved original. Temporary secret copies were
removed. These checks did not generate real image-model pages or create a live Studio Deck.

Current limit: final artwork still uses a text-to-image generation prompt containing observed
visual guidance. This does not attach original bitmaps to the image generator or embed them
unchanged; exact documentary image preservation requires an additional composition path.
Transfers are bounded to 1600px, so illegible fine detail can remain unavailable. Existing
Decks retain saved content; new Decks or standard-length content rewrites use the new reading
path. Sources still need the existing ingestion workflow to complete before selection.

The local service at `http://127.0.0.1:3000/` was updated after verifying zero active jobs.
All 71,545 existing rows and 1,454 data files matched their pre-upgrade hashes. Four existing
15-page Deck PDF downloads remained HTTP 200/ready; foreign-key checks were clean. The backup
and record/file baseline are `<private-verification-path>` and
`<private-verification-path>`.

## Phase 34 — Controlled document image recognition concurrency (2026-10-03)

Implemented an independent recognition setting under Model settings → Language model,
with default 4 and strict range 1–20. The setting persists across restarts, takes precedence
over `IMAGE_RECOGNITION_CONCURRENCY`, and is separate from Deck image generation.
New ingestion/recognition-retry tasks snapshot the limit. A fixed worker pool bounds image
preparation and model calls, preserves original block/image order, and reports monotonic
completion progress. Per-checksum coordination deduplicates simultaneous successful
recognition and shared checkpoint writes. Retry reuses successful transcripts; failures
remain isolated to their image. Cancellation joins network workers and native decoding;
PDFium retains its existing render lock.

Validation:

- All 318 backend tests passed with native Chrome rendering enabled, including six
  concurrency/ordering/deduplication/retry/cancellation cases and 13 settings cases.
- All 43 frontend tests passed. Production build, Ruff and formatting checks passed.
- Three isolated browser flows passed: generation/recognition setting placement,
  1–20 persistence, Chinese/English draft preservation, reload and mobile layout,
  and illustrated Word/scanned PDF reading, citations and chapter Deck generation.
- Browser testing exposed an existing initialization race that could close an already
  opened model dialog. Initial model loading now preserves the open dialog. The test
  provider also distinguishes faithful OCR from Deck requests carrying original images;
  the previous mock returned OCR JSON for both, causing the older document-Deck flow
  to fail. The final browser rerun passed in 10.7 seconds.
- The configured local `gpt-6-luna` endpoint recognized four existing PDF images with
  observed peak concurrency 4. All four returned valid recognition in 16.4 seconds,
  retained source order, and retry made zero additional model requests. Private report:
  `<private-verification-path>`.
  This verifies that endpoint at 4, not a timing benchmark against serial recognition
  or a guarantee that a provider can service 20 simultaneous requests.

Local service update used the existing graceful interruption/checkpoint recovery rather
than deleting or explicitly stopping Decks. Two outstanding Deck jobs resumed in the
original FIFO queue (one running, one queued). Before and after the update, 44,971
protected records and all 242 source/secret files had identical hashes; active Deck/job
records were allowed to advance. Four existing completed 15-page Deck PDF downloads
returned HTTP 200 and remained ready. GET of the live recognition setting returned
`{concurrency: 4, min_concurrency: 1, max_concurrency: 20}` and the current frontend bundle
was served at `http://127.0.0.1:3000/`. Native server PID is 67817.

Backups and integrity inventory:
`<private-verification-path>`,
`<private-verification-path>`, and
`<private-verification-path>`.


## Deck generation reliability — 2026-10-03

Repair scope: preserve original images and whole-book context while addressing failures
reported on the Zarathustra chapters in private-example-A and the illustrated PDF in 测试4.

Confirmed failure mechanisms:

- The chapter planner received registered whole-book evidence that its validator excluded
  when those IDs were absent from the chapter dossier prose. Both example chapters contain
  no original images; their planning failure was independent of image reading.
- Image readings cited exact valid IDs through Markdown anchors or single brackets. These
  were rejected by the required double-bracket matcher; known-ID normalization now handles
  equivalent bracket syntax without guessing or approving unknown references.
- A complete Chinese synthesis reported 8,173 output tokens within its 8,192-token reserve,
  but the conservative UTF-8 estimate counted 9,073 and rejected it. Use valid provider
  usage where available, keep a separate byte limit, and reject truncated outputs.
- Short closing pages exposed structure, provenance, copy-budget and dependent hierarchy
  errors successively. Preflight now reports independent detectable constraints together.
  Single-page repairs return complete JSON and merge diagnosed fields only; this also
  avoids model-generated malformed nested patch instructions. Unknown citations, source
  availability and original quotation requirements remain checked.
- An unfinished page prevented art direction and masked the original page error with
  DECK_CONTENT_REQUIRED. Keep the Deck partial and its successfully authored siblings;
  bulk retry authors missing pages before continuing images/export.

Speed changes: configurable Deck content workers in Model settings → Language model,
strict 1–20/default 2, fixed for each running task. Independent image-reading segments and
page authors overlap while source order, progress and cancellation cleanup remain stable.
Source-owned validated visual readings are cached by source/checksum/model/prompt/context
and remapped to the current job's evidence IDs. Page authors still see relevant originals.
Detailed safe per-attempt diagnostics record stage, time, validation category/field paths
and token/finish metadata; they omit prompts, source text and credentials.

Real-model verification used existing authorized source files and the configured local
endpoint. Private database snapshots were used for development tests:

- The failed private-example-A twenty-page plan now passed in one 106.4-second request with the explicit
  registered-evidence catalog; its original failing pair took 232 seconds and rejected
  valid whole-work references. This is one-case evidence, not an aggregate benchmark.
- Six sampled opening/body/closing pages across “另一曲舞蹈之歌” and “七个印” passed with
  original citations (five requests per three-page sample, including local repairs).
- The failed image-reading group passed in one 27.5-second request; full-scope understanding
  covered the PDF's 69 original images across 18 groups. The actual 8,173-token final output
  was also replayed through the full checkpoint pipeline with understanding reset, proving
  that the corrected token validator accepts it rather than returning an already-saved result.
- The troublesome final private-example-B page required three requests in a private final run and
  passed. In the upgraded live app it passed with two requests (32.2 + 20.3 seconds),
  preserving the other nine page specs before art direction.

Local service upgrades backed up the database and verified 45,010 protected records and
all 242 original-source/secret files unchanged. Disposable source visual-reading caches
are excluded from the immutable-file inventory. Four existing completed 15-page Deck PDFs
still downloaded with HTTP 200. Preflight-upgrade backup and inventory:
`<private-verification-path>` and
`<private-verification-path>`.

Provider performance still depends on document size and endpoint capacity; automated
concurrency-20 checks do not establish real-provider capacity at 20. Real-model samples
cannot establish a general production failure rate.


Final live private-example-B recovery completed in 184.6 seconds from queued retry through export.
The job and Deck are completed/ready with zero failed slides. All original nine page specs
were compared and preserved in full; only the missing page was authored. PDF
export `dff912a90bb54f7ab6a61729d84a806d` downloaded successfully (24,533,149 bytes),
with ten pages, ten bookmarks and exactly one full-page image per page. Existing private-example-A
“另一曲舞蹈之歌” and “七个印” Decks are also ready.

Validation results:

- 46 frontend tests passed, production TypeScript/Vite build passed, and Prettier passed.
- Six isolated browser flows passed before the last page-validation adjustment; the two
  affected generated-page and lifecycle flows passed again afterward (39.6 seconds).
- Ruff, formatting and Git diff checks passed. Backend tests cover concurrency at 1/2/20,
  cancellation and joined native operations, full-page repair path preservation and
  unchanged siblings, unknown citations, checkpoint/cache validation and diagnostic privacy.
- All 348 backend tests passed with native Chrome rendering (230.21 seconds), including
  preserving a partial Deck's original page error and retrying only missing content.
  Final log: `<private-verification-path>`.

Local application is serving the updated production bundle at `http://127.0.0.1:3000/`.
Native server PID at acceptance is 1463. No source files or model credentials were removed.

## Current requirements and coding-agent handoff — 2026-10-03

Documentation-only reconciliation against implementation `5981113` and all twenty decision
records. The original user PRD and system design are archived under `docs/archive/v0.1/`
with exact SHA-256 matches to the two supplied files. The previous milestone 1–32 plan
is retained as a historical snapshot; its deployment link was adjusted for the archive path.

Current PRD/system design now distinguish whole-page image defaults from native compatibility,
DOCX/scanned PDF/vision support, paragraph citations, addressable reading, bilingual UI,
merged/separate directory scopes, lifecycle controls, user-directed interpretation,
content-adaptive style, whole-work context, original pixels, all three concurrency controls,
cache/repair/diagnostic behavior and remaining quality/release limitations.

New documentation entry, requirement-change matrix, HANDOFF and root AGENTS provide read
order, real module/test entry points, isolated start/test commands, troubleshooting,
cache/version compatibility and full-data upgrade/rollback guidance. README/CONTRIBUTING
link to the current contract, privacy documents reflect attempt diagnostics, and older
ADRs explicitly identify superseded wording instead of deleting their history.

Validation: local Markdown links, referenced backend test filenames and source paths checked;
original archive hashes verified; nine concrete API routes, three concurrency defaults,
Deck mode/preferences and seventeen migrations checked against code; Git diff whitespace
checks passed. Final link/file counts are reported in the task completion, not fixed here.
No application code, runtime data, model configuration or production service was changed.
No new real-model requests or product regression/containers were run for this documentation
edit. Earlier test and Docker evidence is labeled by its own version/date, with the latest
full Docker release rerun explicitly pending.

## Deck art repair and failure details — 2026-10-03

Stage 37 / decision 021 implements simultaneous art-rule preflight, actionable diagnosed
field patches, full JSON when a failure has no field path, and author auto repair based on
the scope of the change. Initial author copy allocation aligns with the existing reading
budget. Evidence, authored facts, original-image inputs and whole-work context remain enforced.

Deck failure details and generation history load on demand, refresh and download a bounded
report belonging to that Deck. Safe reasons, known paths, page identities, timestamps,
numeric limits/counts, request outcomes, durations, token/finish metadata and available HTTP
status are allowlisted at write/export. Old records explicitly lack details that were never
saved. Structured/synthesis request errors and whole-page image attempts are now recorded;
this is not a raw exception/network trace. No new migration is needed beyond 017.

Validation: **354 backend tests passed** with native Chrome, **47 frontend tests passed**,
TypeScript/Vite build, Ruff, formatting and whitespace checks passed. Final isolated browser
flows `deck-lifecycle` and `generated-pages` both passed (43.9 seconds), including failure
details/download and single-page retry. The first sandboxed backend run could not launch the
browser; the complete run was repeated with browser permissions and passed (232.34 seconds).
Current full Docker release acceptance was not rerun; earlier results retain their own scope.

Real-model private snapshots reproduced the old art failure: an invalid viewpoint was
repaired, then unsupported branching forms on two pages exhausted the old two-call limit.
After preflight, a 20-page art plan passed with one initial call and one local repair in
75.4 seconds. Three body-page samples passed in four calls / 45.6 seconds (another run:
47.3 seconds). These samples do not establish a population failure rate or speed percentage.

Live upgrade: no queued/running jobs; complete APFS-cloned data backup plus previous committed
backend and frontend retained. **75,613 database records** and **242 original-source/secret
files** had identical hashes after startup. Four saved 15-page PDF downloads remained usable.
The local service at `127.0.0.1:3000` serves the verified frontend and Deck diagnostics route.

The previously failed 20-page Deck `79e96cd71d494044b205e491659dcb90` was retried via its API.
All **20 authored specifications remained byte-equivalent after canonical JSON hashing**.
Art completed in two calls (63.624 + 6.541 seconds); all 20 image requests succeeded using the
existing configured concurrency of 10. The remaining pipeline completed in **185.6 seconds**,
Deck/job/PDF ready, no failed pages. This timing reuses completed research/plan/style/copy;
it is not a fresh end-to-end 20-page benchmark.

Downloaded export `15c7c17ad057411f817a7d38682851d7`: **20 pages, 20 bookmarks, 20 full-page
images, 70,835,048 bytes**. Per-image diagnostics carry correct subject identities; report
download has attachment and no-store headers. PDF structure/download were verified; this
does not assert automated semantic or image-text accuracy. PRD/design/change matrix/HANDOFF,
privacy, phase status and decision index are updated together.

## Stage 38 — systematic UI review and twelve interface languages (2026-10-03)

Implementation: decision 022 on the `f7d3a48` base. Findings and user impact are recorded
in UI_REVIEW.md. Small screens use three explicit workspace sections without unmounting
content/drafts; new route objects return to the content section. Source/readiness copy,
queued/failed states, modal-local errors, destructive button treatment, touch sizes,
contrast, long text and Deck copy/export hierarchy were improved. Shared Modal handles
focus, inert backgrounds, nested dialogs, Escape, busy operations and scroll restoration.
Chat follows its own message container without pulling the document to its bottom.
A delayed/superseded model-settings load can no longer overwrite a new concurrency choice.

Twelve bundled language catalogs contain **621 matching keys each**, with matching
interpolation variables: zh-CN, en, zh-TW, ja, ko, es, fr, de, pt-BR, ru, ar and hi.
Arabic switches document direction to RTL; source content retains its own direction.
The output-language selector also lists all twelve languages. Backend preference updates
remain independent of telemetry consent and need no database migration. Translation
checking found untranslated Russian/Hindi batches; those batches were regenerated and
checked for accidental Chinese values. No runtime translation service is added.

Verification on final source: **52 frontend tests passed**, **19 preference backend tests
passed**, **all 25 browser acceptance tests passed in one complete run (2.9 minutes)**.
TypeScript/Vite production build, Prettier, Ruff check/format and Git whitespace checks passed.
Browser checks cover existing upload/read/chat/citation/knowledge/Deck lifecycle and revision
flows, plus keyboard deletion/error handling, section drafts, 320/390/768/1024/1440px layouts,
all twelve locale selections and reloads, model drafts and Arabic RTL. Earlier review runs
exposed focus, duplicate-fixture and settings-load issues, repaired before the final run.

Screenshots were inspected in the isolated local test app. These are Chromium viewport
checks, not physical iPad/mobile Safari or full screen-reader certification. Translations
are model-assisted with structural and selected phrase checks, not a human native-speaker
review of every string. The production bundle has Vite's pre-existing large-chunk warning;
all locale resources are local and loaded with the application. Full backend generation
and current Docker packaging were not rerun for this UI/preference change; previous stage
354-backend results retain their historical scope. Current full Docker release verification
is still pending.

Live application updated at `127.0.0.1:3000` after confirming no queued/running jobs and saving
full data/old backend/frontend rollback material. **75,683 protected database records** and
**242 original-source/secret files** had identical hashes before/after startup. Four saved
15-page PDFs remained downloadable; OpenAPI accepts all twelve locale codes. The verified
frontend entry matches the served bundle. Backup in this environment:
`<private-verification-path>`; upgrade-result.json records integrity and PID.
No existing sources, generated pages or PDFs were rewritten for the interface change.

## Batch source imports — 2026-10-03

基线9354631，decision023增量；migration018。文件多选、单项失败重传、重复确认队列；Word父样式/循环继承修复；URL逐项登记、受限公网下载、正文快照/目录/表格、统一阅读与后续生成；12语言文案对齐。

- 后端最终完整回归：**400 passed**（含SSRF地址/混合DNS/重定向、连接IP固定与Host/SNI、下载大小/总超时、fake-IP DoH兼容与禁用、正文结构与稳定出处、失败重试/不可变快照、重复/跨本复用、容量与重启/删除、迁移与旧原生渲染/PDF）。
- 前端：**57 tests / 16 files passed**；包含上传成功不被单项失败覆盖、全部重复项确认、URL行去重/错误保留、限制与关闭弹窗时背景恢复；全部12语言键/插值校验。TypeScript、生产build、Prettier及Ruff通过。
- 完整browser suite：**27 passed**，同时覆盖全部既有Chat/Knowledge/Deck/导航/原图/格式/语言路径及新增多文件/手机URL入口。
- 真实公网HTML验证：Python官方教程提取185个blocks/24个标题，介绍页8个blocks。独立临时实例、390px浏览器完成**两项URL提交→后台解析→阅读→打开来源链接→刷新恢复**；无用户数据/凭据。首次模型弹窗在刷新后关闭，再确认可见阅读界面。
- 真实失败Word：此前安全解析复现basedOn路径的AttributeError；修复后509 blocks、2 nodes、0 images。生产源解析/索引重试结果在本节后续记录。

初轮完整回归遇到系统沙盒无法启动Chromium，切到授权的本机Chrome/隔离数据后验证。migration数断言按018更新。首轮browser发现资料重复确认在异步列表刷新前仍可能使背景处于inert，已调整关闭时序并补回归；最终完整27条通过，不把中途失败算作最终成功。

本地升级前在线数据库+正常停机完整APFS数据备份，保留旧9354631代码/锁文件/前端。migration018后**75,666个原业务记录与242个资料/密钥文件**逐项一致；外键检查通过，四份原有15页PDF仍可下载，LAN与本地健康。schema_migrations增加一项，不纳入“未改变”的业务记录集合。
临时备份路径只用于本环境恢复，接手仍遵守HANDOFF完整流程，不以此替代正式部署工具。

边界：当时仅公开HTML正文，不携带浏览器登录态/执行JS/绕过验证码，不下载远程图片；没有新增Chrome扩展/自动爬取/Web Search。该阶段未完成Docker复验；后续网页图片与完整容器验收见下文。生产bundle仍有既有大包提示。

## Optional web images — 2026-10-04

范围：`5802fa5` 基础加 [decision024](decisions/024-optional-web-image-archive.md)。
“导入网页”默认勾选“保存正文图片”，可取消并在请求失败/重开弹窗后保留选择。
旧API缺省仍只导入正文。正文先发布，再单独排队下载原图、识别并建立图片出处；
旧网页可从阅读器补图。成功下载保留原始字节与本地预览，图片失败逐项显示原因，
重试复用已保存图片和已成功识别文字。正文、引用身份与成功图片事实不被重写。
12语言同步，模型设置的图片识别并发继续适用，没有新增迁移。

验证：

- 完整后端415项通过（含原生Chrome），前端59项通过，TypeScript/Vite、
  Ruff/格式及Prettier检查通过。最后缓存校验/图片顺序调整另通过52项相关后端回归。
  新图片测试15项覆盖 opt-out、srcset/懒加载/CDN、五种栅格解码、限额/超时、
  私网重定向、原始下载字节、重复URL去重、部分失败、损坏cache恢复、
  图片任务期间正文可读、重启与删除，以及原图输入可用于Deck理解。
- 原生3条相关浏览器流程通过；IAB用隔离合成页面检查正文、原图、识别内容、
  逐图失败原因及下载入口。小屏幕导入选项截图发现checkbox继承列布局的问题，
  修正后最终Docker mobile截图再次检查。识别测试均使用合成/模拟模型协议。
- 真实公开页面 [Python logos](https://www.python.org/community/logos/) 下载验证：
  22个正文block、2张正文图片，保存原始文件合计65,824字节，0下载错误。
  没有向真实模型发送该页面或用户资料，不由下载测试宣称模型识别质量通过。
- 最终生产镜像完成首次配置（1项）及全部27条浏览器流程（4.2分钟）。
  重启和完整容器重建均比较83份API快照、41个下载哈希、176个文件，
  3份已存密钥解密成功；batch重试复用和主动停止Deck保持成立。测试栈已关闭。
- [container_web_images.py](../tools/container_web_images.py) 在最终生产镜像中，
  使用单独临时数据和模拟传输、关闭容器网络，正向图片保存验收通过：
  五格式解码、取消勾选零图片请求、补图不变正文、私网图片拒绝、原始字节下载、
  restart/retry零额外抓取/识别、资料删除。该步骤已纳入Docker验收脚本。

本机更新：先确认无queued/running任务，SQLite在线备份，正常停止后APFS完整数据
备份，并保留`5802fa5`旧程序及配套前端。新前后端一起启用，77,203条数据库记录
（含迁移记录）及244个资料/密钥文件内容哈希未变，外键检查通过，schema仍018。
本机/内网HTTP、新`save_images`及原始图片下载API契约通过；四份旧15页PDF均ready
并成功下载。没有导入新的生产测试资料、触发真实模型或改写旧Deck。

私有验证产物（不入Git）：

- `<private-verification-path>`、`...-target-final.log`、
  `...-unit-final.log`、`...-docker-final.log`、`...-container-positive.log`。
- 最终Docker隔离数据 `.docker-acceptance-data.kNdGt2`；截图在
  `frontend/test-results/web-images-option-mobile.png`。
- 完整本机备份 `<private-verification-path>`，包含数据、
  在线数据库、旧程序/前端、完整性记录与`result.json`。

边界：公开静态HTML正文及PNG/JPEG/WebP/GIF/AVIF图片；不继承登录态/执行脚本，
SVG、动画逐帧识别和最终Deck精确嵌入原图仍未实现。复杂页面可能漏图；
模型识别受模型能力与费用影响，正文与图片抓取时间分别记录。既有Vite大包提示仍在。

## Deck preview navigation — 2026-10-04

范围：`ef03538`基础加[decision025](decisions/025-deck-preview-navigation.md)，仅前端交互。
普通/专注预览均支持点击大图左/右半边上一页/下一页，以及↑/↓切页；首尾不循环。
透明区域不展示文字/图标，但有可访问名称及键盘焦点反馈。高清查看移到独立链接。
沿现有稳定slide ID路由与缩略图/滚动同步；不修改页序、生成结果、API或schema。

验证：前端全部61项测试通过，TypeScript/Vite、Prettier及diff检查通过。新增单测覆盖
正常/专注切页与边界、高清链接随页切换、输入/select/contentEditable、IME/组合键、
已处理事件、编辑/删除弹窗和监听卸载。3条相关浏览器流程通过（40.8秒），包括
桌面1440×900、iPad横/竖屏、手机390×844的真实点击位置、↑/↓、URL同步与刷新、
首尾页、编辑不误切页、完整图像可见，以及原有导航/草稿返回保护。随后追加手机
触摸事件，Deck lifecycle再通过（15.2秒）。所有浏览器生成均在隔离数据/模拟模型上。
iPad和手机专注预览截图已检查，图片上没有新增可见按钮，高清入口仍可见。

已将构建的前端更新到3000本地实例：备份旧前端后先发布资源、最后原子替换入口，
保留旧资源哈希供已打开客户端继续加载。新HTML与两个资源文件HTTP哈希校验通过，
应用健康；后端进程保持运行，没有修改生产数据或中断任务。刷新浏览器即可加载新交互。
本次不重复后端测试或完整Docker发布验收；阶段40的容器/真实下载结果保持历史范围。
既有Vite大包提示仍在。

私有产物：`<private-verification-path>`、`...-build.log`、
`...-format.log`、`...-browser.log`、`...-touch.log`；截图位于
`frontend/test-results/deck-ipad-focus.png`与`deck-mobile-focus.png`。
前端备份与更新结果在`<private-verification-path>`。

生产 Word 重试已完成：source_ingest completed，509 blocks、27 chunks、status=indexed；原始Word字节保留，Reader和检索可用。未重建其他资料或历史Deck。

## Stage 42 — Deck source manifest, names and PDF filenames (2026-10-04)

实现范围：`cfc17f3`基础+decision026。新Deck创建时冻结资料名、章节目录路径、知识页
名称与revision；清单按需显示，可跳阅读与当前知识页。来源删除/改名后保留原快照；
旧Deck按保存范围与仍保留资料只读还原，明确historical，不假造历史名称。
创建提供auto/source名称策略：单来源/单章节允许，合并多来源拒绝，分别生成按各自
范围独立命名。闲置Deck可重命名，后台任务先停止；用户名称在继续及重写副本中保留。
PDF HTTP文件名来自当前Deck名称；页面文字/图片不改写，export_title保留已有导出签名。
迁移019不修改旧页、引用或已有PDF字节。12语言同步加入新界面文案。

后端完整回归共428项通过：普通沙箱中411通过，17个真实Chrome渲染/PDF检查因进程权限
失败后在允许启动浏览器的隔离环境重跑全部通过（148.8秒），没有跳过。
新增13项来源/命名/迁移/PDF检查通过；随后扩展EPUB/PDF/Word批量名称验证，7项通过。
Ruff check/format全部通过。前端全部66项、Node24 TypeScript/Vite build与Prettier通过。
新增单测覆盖单来源选项可用性、来源按需读取/失败重试、历史不可用名称、知识页版本、
重命名失败与语言切换保留草稿、动态下载名称。保留大包体积提示，未改变依赖或锁文件。

原生相关浏览器2条通过（31.5秒），覆盖批量来源及章节命名、PDF书签路径跳转、浏览器
返回、中文改名/刷新、真实download建议名与PDF字节相等，以及原有停止/继续/平板预览。
平板768×1024截图已检查，无水平溢出；普通/专注预览的原有翻页行为保留。
完整Docker production-image：首次设置1项及全部27条浏览器流程通过（4.4分钟）；
独立容器网页图片协议检查通过。重启及强制重建各验证83个API快照、41个下载哈希、
176个持久文件、3份加密模型密钥可解密，批次幂等与停止状态保持。使用隔离临时数据
及模拟模型，没有向真实模型发送新资料，不宣称新的内容/视觉质量验收。

本地3000应用升级前确认无queued/running任务。完整旧代码/前端/数据库与全文件备份后
优雅关闭并应用019；健康、静态资源HTTP哈希、OpenAPI新字段/入口验证通过。对照旧列
核对104,557条既有记录及2,476个sources/assets/renders/exports/secrets文件哈希完全一致；
允许的新增变化仅3个Deck字段与019迁移登记，foreign_key_check通过。
4份旧15页PDF仍ready、可下载、sha256与保存记录一致，旧Deck来源只读还原可用。
新进程PID38067，schema019；这些是环境快照，接手需重新检查。刷新页面即可加载。

私有备份/升级核对：`<private-verification-path>`；
完整容器日志：`<private-verification-path>`；后端Chrome复验：
`<private-verification-path>`；格式批次复验：
`<private-verification-path>`。隔离容器数据保留在
`.docker-acceptance-data.mRkieg`，没有替换用户data。
界面证据：`frontend/test-results/deck-names-sources-tablet.png`（容器最终版），均不提交Git。
回退必须同时恢复完整schema018数据与备份旧代码，不能让旧代码打开019数据库。

## Development browser startup safety (2026-10-04)

用户提供的报告记录 Chrome 在启动约3.5秒后，于 macOS HIServices
`_RegisterApplication` / `TransformProcessType` 中 SIGABRT。本机同一事件窗口
有五份同类 Chrome 报告，时间对应上一阶段在受限 agent 环境运行真实浏览器测试。
结合本机无法绑定 loopback 端口、允许进程/监听权限后验证成功，原因高度符合
macOS 应用注册受限；没有独立捕获具体被拒绝的系统服务，不能宣称底层根因完全证明。
报告显示 Rosetta，但系统 Chrome 本身为 universal，不能据此判断 Intel-only 或要求重装。

新增 `tools/browser_check.py`：先检查本地端口，再使用静态合成页面验证浏览器启动、
PNG尺寸、PDF页数/尺寸/可提取文字；失败立即停止，不自动重试或切换个人 Chrome，
不输出原始异常细节。端口权限是必要条件，不代表所有 GUI 权限均已通过。
macOS pytest 收集真实 browser tests 时检查端口，拒绝时显式 UsageError；
`npm run test:e2e` 增加同一预检。默认使用配套 ARM64 headless shell，保留显式可选路径。
更新 AGENTS/README/HANDOFF/design，取代此前“沙盒失败再切系统 Chrome”的执行建议。
不变更产品需求、运行时渲染、模型契约、数据库或生产资料。

验证：
- 受限环境：预检返回 LOCAL_TEST_PORTS_UNAVAILABLE；指定真实渲染测试在收集阶段
  明确失败；E2E 预检同样提前停止，均未启动浏览器，也未把未执行检查算作通过。
- 六项新回归覆盖不启动浏览器、首次启动失败不重试、渲染异常关闭进程、诊断不回显
  异常细节，以及 macOS/non-browser/Linux 收集边界。
- 允许启动浏览器的隔离环境：默认 ARM64 Playwright headless shell 153.0.8010.12
  连续三次启动/截图/PDF成功；18项真实渲染/PDF检查全部通过（19.80秒）。
- 全部416项非浏览器后端测试通过（221.24秒），合计434项；前端66项、Node24
  TypeScript/Vite build、Ruff check/format、Prettier和差异空白检查通过。
- Deck 批量来源/章节/导出/命名流程在默认 Node Playwright 浏览器下通过（16.1秒），
  自动预检通过；全部使用隔离测试数据和假模型，无真实模型调用。
- 本次验证窗口新增 Chrome/Chromium .ips 崩溃报告0份；应用健康 HTTP200，原有
  PID38067仍运行，没有重启生产服务。此为本次观测，不保证其他环境永不发生浏览器崩溃。

本次未重新运行完整 Docker 生产镜像验收；没有修改部署打包或运行时行为。
历史阶段42容器证据保留，不冒充本次 HEAD 的完整容器复验。未改变依赖版本或锁文件，
保留既有大包体积提示与 Starlette/httpx 弃用提示。私有崩溃原稿和诊断报告未提交 Git。

## Stage 43 — Chapter Deck source names (2026-10-04)

基于e8116ae，按用户反馈细化026（decision027）：新建Deck选择来源命名时，
单章使用“资料名称-完整目录层级序号-章节名称”。同级从1开始、子章节如1.2.1，
不依赖所选范围/顺序、原始node ordinal或PDF页码。EPUB优先真实nav/NCX次序而非spine。
manifest增加可选number并冻结；来源删除/改名后仍保留原快照。整份资料名称、AI拟名、
用户改名、旧Deck/副本名称保持原规则，PDF下载从当前名称取得，无迁移。
EPUB非标题锚点捕获复用Reader节点，修复来源命名/快照缺失，不改事实blocks。
12套语言同步说明；PRD/design/差异表/HANDOFF和历史026 supersession同步。

验证：相关26项后端通过，完整后端436项通过（含配套浏览器真实渲染/PDF，241.69秒）；
前端66项、Node24 TypeScript/Vite build、Ruff check/format、Prettier、差异空白和
文档链接检查通过。原生Deck batches流程通过（15.2秒），验证1.1层级命名、批量/单章
一致、刷新/目录跳转、真实下载同名及手动改名后保留PDF字节。
新增回归验证逆序/部分选择的完整目录编号、目录顺序优先、来源名称冻结、命名无模型
调用与EPUB锚点正确标题/顺序/事实不变；原有EPUB/PDF/Word批量隔离验证仍通过。

完整生产镜像首次配置1项及全部27条浏览器流程通过（4.3分钟）；网页图片协议验证通过。
重启及强制重建两次核对83个API快照、41个下载哈希、176个持久文件、3份加密密钥，
批次重放与停止状态保留。仅隔离临时数据/假模型，未调用真实模型，无新增视觉质量结论。

本地3000更新前再次确认无queued/running任务，完整在线DB、旧代码/前端与停机全数据
备份后优雅重启。健康/静态资源HTTP哈希校验通过；schema仍019，foreign_key_check通过。
对比104,979条既有记录及2,476个sources/assets/renders/exports/secrets文件完全一致，
包括旧Deck名称、原始资料、出处与PDF；两份已有PDF仍可下载。新进程PID48399，
无创建/重命名生产Deck、无真实模型调用；新建来源命名生效，刷新加载新弹窗说明。

私有完整备份：`<private-verification-path>`；
容器日志：`<private-verification-path>`；原生浏览器日志：
`<private-verification-path>`。隔离容器数据保留在
`.docker-acceptance-data.fOlPpV`，没有替换用户data。既有包体积/弃用提示保留，无依赖变更。

## Stage 44 — Multilingual art layouts and localized repair (2026-10-04)

用户提供的安全诊断显示：15页均authored、生图尚未开始，三轮任务的六次DeckArt调用
都以art_layouts失败，两次issue实际来自主校验与预检重复记录。报告没有原始模型响应，
无法确认该实例是否属于语言误判或真实重复，不把推断写成已证实的模型返回内容。

可复现代码问题：十个不同中文布局在旧a-z-only归一化下全部变为空串并被判重复。
028改用Unicode NFKC/casefold保留文字/空间数字、剔除明确页码标签。实际重复仍拒绝，
仅定位超限成员的pages[i].layout，保留有效编排/内容。安全诊断按影响页展开重复次数及
上限；同一主校验/预检错误去重，修复进展签名纳入业务reason，最多三次，无进展两次即停。
无迁移/依赖/界面文案变更，不写回旧报告、不改已有art/image/PDF或出处事实。

验证：26项相关art/structured/diagnostics检查通过；完整后端439项通过（238.45秒，
含配套浏览器真实渲染/PDF）。随后补充完整/部分/无进展参数场景，9项布局/重复检查
通过，覆盖当前441个后端案例中的新增两项，不重复跑已通过的全套。
覆盖中文不同布局、俄文/阿拉伯文区别、空间比例数字、页码伪变化、真正重复的精确
路径/安全次数、修复有效字段冻结、两次修复成功/有进展第三次/无进展停止及反馈去重。
原生generated-pages浏览器流程通过（26.4秒），Ruff check/format及差异空白检查通过。
未改前端，不重复前端单测/构建；本次未进行完整Docker复验，阶段43容器证据保留其范围。

本地3000确认无queued/running任务后完成旧代码/前端、在线DB和停机全数据备份再更新。
HTTP健康/静态资源哈希、schema019及foreign_key_check通过；104,979条既有记录及2,476个
原始资料/图片/渲染/PDF/加密密钥文件内容完全一致，两份旧PDF仍可下载。原失败Deck的
15页文字保留，未自动重试/生图、未发真实模型请求。新进程PID53263。

随后获得用户明确授权，仅使用该失败Deck已保存的15页文字和当前语言模型，在隔离DB/
密钥副本直接复验视觉编排，不启动worker、不读整本原资料、不生图、不写回原Deck。
真实复验通过：首轮56.547秒，第14页art_unsupported_form；定点修复10.501秒后全部15页
通过，共两次调用、模型耗时67.048秒，已保存文字哈希不变。原Deck仍未自动重试，
没有新增图片/PDF质量结论；这次成功也不证明历史失败返回了哪些布局文字。
隔离复验目录：`<private-verification-path>`。
日志：`<private-verification-path>`；完整私有备份：
`<private-verification-path>`。不提交用户诊断原稿或原始模型内容。

## Stage 45 — Bounded cross-task scheduling (2026-10-04)

基于120d5ec，用户接受跨任务并行方案，029明确取代单重任务串行执行要求。
仍为单进程/单数据目录所有者，持久队列默认3个任务（1–8可设），按资料/Deck/交互
类别轮换；同实体及来源读写冲突保持次序，取消清理完成前不释放资源预约。
模型服务按协议/主机/有效端口共享总额度，默认8（1–20可设），等待按job轮换。
原有内容/识图/生图设置和运行快照保留，跨任务共享准备预算，避免解码/附图内存倍增。
12套语言增加两项模型配置。多文件上传3个worker、Embedding两批并行、网页图片保存后
即可识别、同书背景单飞；整套编排、最终PDF和PDFium安全锁保留真实依赖。

验证：完整后端452项通过（244.98秒）；随后新增三类任务轮转回归，相关45项通过
（16.90秒），合计覆盖当前453个案例，未声称完整453项再次执行。前端69项/18文件、
Node24 TypeScript/Vite build、Ruff check/format、Prettier和差异空白检查通过。
覆盖跨任务峰值、来源读写/同实体预约、关闭/取消join、刚获得请求额度时取消、动态总
额度、共享准备预算、原索引失败保留、同书背景只读一次及网页下载/识别重叠。
定向原生浏览器9条通过（37.8秒）；之后上传时序的最终修正由单测和完整容器覆盖。

第一轮容器27通过/2失败：停止场景仍假设默认串行排队，以及文件选择器在上传刷新
尚未结束时被测试强制触发。停止场景显式设置额度1并恢复原设置；产品刷新不再阻塞
上传worker，文件输入上传中禁用，重复确认按原输入顺序排队，并增加慢刷新/乱序响应
回归。最终容器首次配置1项、完整29条浏览器流程（4.2分钟）及网页图片协议验收通过。
重启/强制重建两次核对83个API快照、41个下载哈希、176个持久文件及3份加密密钥，
批次重放和停止状态保留。仅隔离数据/测试模型，未以浏览器模拟测试证明真实模型质量。

隔离调度实验：6个各等待150ms的模拟任务，额度1时948ms/峰值1，额度3时327ms/峰值3，
仅验证调度并行约2.90倍；未追加真实资料/模型调用，实际提速取决于服务容量、限流、
文档和各阶段依赖，不承诺真实Deck倍速。配置不是RPM/TPM限制，不自动合并DNS别名。

本地3000两次确认无queued/running后，完成旧代码/前端、在线DB和停机全数据备份再
优雅更新。HTTP健康/静态哈希、schema019及foreign_key_check通过；106,048条既有记录
与2,659个资料/图片/渲染/PDF/密钥文件内容完全一致，两份旧PDF可下载，进程PID74941。
没有自动重试旧Deck或调用真实模型。最终前端修正先复制新资源再原子替换index，保留
旧资源以兼容已打开页面，HTTP两个资源哈希通过；未再次重启后端。

私有完整备份：`<private-verification-path>`；最终前端备份：
`<private-verification-path>`。日志：
`<private-verification-path>`；
最终容器隔离数据：`.docker-acceptance-data.XG7Bpf`。不提交用户资料、密钥或模型原文。

## Stage 46 — Artifact batch downloads (2026-10-04)

基于769f463，实现提交f35494d（030）。演示文稿列表多选/全选已有当前PDF的Deck，
下载一个ZIP；PDF使用当前名称并保留原字节，Unicode/大小写等价重名编号，严格检查
归属、状态、当前签名、存在性与SHA256，任一失败不发布部分包。不自动导出或调用模型。
通用选择组件/文件适配器供后续产物复用，当前仅Deck PDF；12语言覆盖新操作与错误。
每次100份/512MiB，浏览器直接下载与Range续传，临时包最多32个/1GiB、两次打包、
最长30分钟有效；容量不足先回收最旧空闲包，传输中的文件保护，不阻塞连续分批下载。
打包线程取消join、传输持Notebook/实体锁，删除关联临时包、关闭清理；无迁移/依赖变更。

完整后端468项通过（249.39秒）；之后相关25项通过（6.95秒），新增暂存关闭/容量与连续
批次回收检查，最终批量下载17项通过（0.96秒），覆盖当前470个案例中的新增两项，
未声称完整470项再次执行。覆盖重名/安全文件名/改名原字节、异笔记本/缺失/忙碌/过期/
损坏文件原子拒绝、限额、过期、删除、下载中断/Range、取消等待实际线程释放锁、
暂存回收不影响活动传输和关闭清理。模型请求数量不变。

前端73项/19文件、TypeScript/Vite build、Ruff check/format、Prettier、差异空白和文档
链接检查通过。初次全前端的既有Reader焦点检查早于异步effect，修正为等待焦点到位，
未改Reader行为；最终全套73项通过。选择保持语言/轮询状态、失效项退出、最多100份、
打包防重复、离开取消等待及安全错误文案均验证。

定向原生完整deck-batches流程通过（最终13.0秒）：合并/分别/章节名称/改单份名称后，
多选四份PDF以ZIP真实下载，核对各项SHA256与单份下载一致、标题正确及手机不溢出；
最终手机截图检查按钮对比度和勾选布局。最终生产镜像首次设置1项、完整29条浏览器
流程（4.2分钟）和网页图片协议验证通过，重启/强制重建两次核对83个API快照、41个
下载哈希、176个持久文件及3份加密密钥，批次重放与停止状态保留。
所有自动验证使用隔离临时资料/测试模型，不使用生产资料或追加真实模型请求。

发布：检测到本地6份Deck生成/排队，保持运行，等待全部结束及最终验收通过；未打断
模型请求。两次空闲确认后备份旧代码/前端、在线DB及停机全数据，再优雅更新本地3000。
HTTP健康/静态资源哈希、schema019及foreign_key_check通过；部署基准109,643条既有
记录和3,097个资料/图片/渲染/PDF/密钥文件完全一致，两份已有PDF可下载，进程PID43222。
新请求入口生效，生产两份已保存PDF的ZIP与单独下载逐项SHA256一致，没有请求重新生成。
该复验之后的全库额外比对发现两条新deck_generate任务和运行记录/Deck状态变化；
因此整库不变结论仅指部署核验窗口，不把同期业务活动说成批量下载改写了事实或静止数据库。
批量下载路径没有模型调用，也没有重试任何Deck；源事实/产物升级完整性以部署基准为准。

完整私有备份：`<private-verification-path>`；更新日志：
`<private-verification-path>`。实现提交f35494d，验证/部署记录另提交。

日志：`<private-verification-path>`。
最终容器隔离数据：`.docker-acceptance-data.7SEZct`；当前原生截图在frontend/test-results。
不提交用户资料、密钥或模型原文。

## Stage 47 — Lossless PDF encoding (2026-10-04)

基于419fae8，031。PDF图片保留全部RGB/gray样本及分辨率，去掉ASCII85，采用级别9
Flate与PNG预测择小。新整页单页PDF标记编码版本，最终组装直接复用，避免重复压缩；
原生兼容文字层/旧单页仍从原页图导出。PNG/资产/原资料字节不变，不使用有损编码或模型。
旧导出签名保持，显式重新生成PDF保存独立压缩版，下载/列表/批量优先ready新版；
普通恢复复用旧版、失败保留原下载，旧链接仍受修订过期/哈希检查。不新增迁移/依赖/UI语言键。

最终完整后端478项通过（261.79秒），Ruff check/format及差异空白检查通过。
新增8项覆盖RGB/gray/RGBA行为/不可压缩噪声、逐样本一致、缩略图/页尺寸/书签/metadata、
Poppler独立渲染旧新PDF完全同像素、单页不重复编码、旧签名/字节冻结、显式另存与缓存、
ZIP包含优化版原字节、两版修订失效、失败回退以及失败新版的后续恢复。
初次完整回归477通过/1失败：20页模拟流程超过原5秒等待，定位为最终PDF重复编码；
复用已编码单页后定向9项通过。该并发/顺序测试不是延迟基准，20页等待调整为15秒，
并发峰值/完成/原文顺序断言保留；最终完整478项通过，不把延长等待代替压缩路径修复。

只读现有20页PDF及页图，在私有/tmp离线验证，无生产写入或模型请求：
原70,835,048字节，最终导出41,157,813字节，减少41.9%；20页全部颜色样本/分辨率和
书签一致，原始文件未修改。旧页图首次压缩导出37.3秒；不把此样本比例/耗时外推所有Deck。
另有同PDF直接图片流优化样本41,157,842字节（元数据/封装有差异），逐页像素验证一致。
样本位于`<private-verification-path>`，无用户正文/图片入Git。

日志：`<private-verification-path>`。
最终实现2f1efc5生产镜像首次设置1项、完整29条浏览器流程（4.6分钟）及网页图片协议
验收通过；重启/强制重建两次核对83个API快照、41个下载哈希、176个持久文件和3份
加密密钥，批次重放与主动停止状态保留。隔离目录`.docker-acceptance-data.IWDcXD`。
初版镜像也通过29条，但发布以避免重复编码后的最终镜像为准；前端未修改，不声称新增
前端单测结果。所有自动流程使用临时数据/测试模型，不以此证明真实生成文字或模型能力。

本地3000确认两次无queued/running后，在线DB备份、正常停止及全数据克隆，再更新后端。
完整备份`<private-verification-path>`，旧代码419fae8可回退，前端未替换。
HTTP健康、静态资源、schema019及foreign_key_check通过；部署基准109,675条既有记录与
3,097个资料/资产/渲染/PDF/密钥文件完全一致，两份既有PDF仍可下载。PID63950仅为当时
状态。未对生产旧Deck自动导出或重试、未调用真实模型。服务已启用新导出逻辑；已有
Deck由用户点击重新生成PDF才另存优化版。更新日志`<private-verification-path>`。

### 用户授权的现有PDF后台批量优化 — 2026-10-04

用户明确要求批量处理已有PDF，复用031已部署的export API和持久队列；没有新增自动
升级行为、批量UI、数据库写脚本或独立数据目录所有者，服务未重启。只读发现与校验后，
37份当前ready旧PDF（600页）分别通过服务API排入deck_export/optimize任务，沿用配置
同时3份；两份partial Deck没有任何已保存PDF，跳过且不触发补图/重试。已优化/忙碌/
主动暂停/缺文件或损坏项的跳过检查保留；本批37项全部成功。

排队后的监测462秒（不含前置备份/校验）。下载总体积由2,016,838,067字节降为
1,195,387,731字节，减少821,450,336字节/40.73%；这是下载大小减少，旧版全部保留。
37份新文件的完整SHA256、页数/页面尺寸/书签顺序验证通过；原生与整页两种模式抽样
4页的全部像素样本及提取文字一致，没有声称再次独立渲染全部600页。
37份应用详情均优先返回新export ID，下载Range响应与对应保存文件的首1024字节一致；
下载端点本身仍检查全文件哈希。最终无queued/running任务、无失败、无模型调用。

批次前只读SQLite在线备份与私有原文件清单在
`<private-verification-path>`；source/node/block/citation/span/model
事实表哈希及批次前全部资料/资产/页图/旧PDF/密钥文件哈希在结束时完全一致。
该目录保存before.db、manifest/entries/result、pixel-samples和downloads回执，均不入Git。
日志`<private-verification-path>`，下载复核日志
`<private-verification-path>`。本轮是已授权的一次维护执行，
不据此宣称产品已新增通用批量重新导出入口；应用默认下载已使用压缩版。

### 用户授权的被替代旧PDF清理 — 2026-10-04

用户确认清理上批已验证的37份旧Deck PDF及对应导出记录；不是原始上传PDF、页图或
其他历史版本。使用上述私有entries清单逐项检查旧/新ID、归属、签名、ready状态、
SHA256与应用当前版本，并验证既有恢复备份。两次空闲检查后正常停止服务，维护进程
持有instance锁；复制完整当前数据并再次检查37份旧、新备份哈希，再事务删除准确37行。
沿用export_files_deleted触发器和FileMaintenance清理37个归属目录；事前队列为空、无其他
归属孤儿，事后garbage队列为空。未新增清理API/自动策略、迁移或调用模型。

移除应用目录中的2,016,838,067字节旧PDF；保留1,195,387,731字节压缩版与恢复备份。
备份为APFS克隆，以上是应用文件逻辑大小，不代表实际磁盘空间释放。其余3,097个
资料/资产/页图/渲染/PDF/密钥文件完整SHA256一致；剩余导出行逐字段相同，其他所有表
计数/哈希一致，SQLite integrity_check和foreign_key_check通过。清理失败的离线回滚
路径已准备，本次没有触发回滚。

正常恢复同版本服务后，37份详情均使用原来的压缩版ID，37份Range下载与对应保存文件
首1024字节一致（下载端点仍校验全文件哈希）；37个旧下载与37个旧预览链接均404。
重启后的全部表与清理完成快照一致，最终无queued/running任务。服务PID72076仅为当时
状态。这是一项数据维护，没有代码/UI变更；没有重复宣称全量单测或容器测试。

完整清理前备份、allowlist、deleted-rows、before.db、前后完整哈希清单及result回执：
`<private-verification-path>`；执行日志：
`<private-verification-path>`。临时维护工具未加入仓库，备份/用户内容不入Git。

## Stage 48 — Embedding model switch and index rebuild (2026-10-04)

基于f26e2a8，032。旧保存行为已核实为自动source_ingest重试，改为配置写事务内排队
专用source_reindex；当前Notebook关联的已解析文字资料按source去重，不发送解绑项。
设置新增整体/逐份进度、安全失败原因、待处理重建、失败重试和显式全部重算，12语言
对齐。新配置区分地址/模型/维度，重复保存及密钥轮换跳过有效索引；旧签名升级兼容。
显式全部重算创建新索引身份，避免同名模型换权重后仍用失败旧向量。原文/引用与产物
不变，不重解析/OCR，继续用持久队列、读写预约、共享请求额度与重启恢复，无迁移。

定向29项后端通过，包含10项新增索引案例及既有模型/并发契约：真实handler路径的共享
资料、原文件/段落/精确引用、模型/地址/维度变化、密钥轮换、旧签名、失败原子保留、
仅失败重试、排队/运行连续切换、源删除保护、强制同名版本与正常中断恢复。首轮连续
切换用第二活动job触发现有唯一约束失败，已改为更新唯一job目标，未弱化数据库约束。
不把上述隔离mock结果当成真实模型检索质量或速度验收。

前端完整76项通过（含新增3项设置进度/重试/轮询卸载），生产构建、12语言键/插值、
Ruff check/format、Prettier及差异空白检查通过。原生定向6条浏览器通过，包含模型保存、
失败重试、关窗后台继续、reload与390px布局；截图已实际检查，没有横向溢出。
最终完整后端488项通过（260.71秒），日志`<private-verification-path>`；
额外保护加入前的487项完整回归也通过，发布以488项为准。前端与定向日志分别为
`<private-verification-path>`，无真实模型调用。

最终生产镜像首次设置1项、完整30条浏览器（4.4分钟，含强制全部重算的新身份核验）及
网页图片协议检查通过；重启/force-recreate两次分别核对83个API快照、41个下载哈希、
176个持久文件和3份密钥，主动停止与批次复用保留。隔离目录`.docker-acceptance-data.K7oHXt`，
日志`<private-verification-path>`。初版镜像30条也通过，最终以加入
同名模型身份保护后的镜像为准。此前非浏览器467项、独立浏览器18项及初版定向检查
作为过程证据，不重复相加成最终测试总数。

发布实现2a119ba。两次确认本地3000无queued/running后，在线DB、旧代码/前端及正常
停服后的完整数据备份，再更新同版本schema019的单实例。HTTP健康/新API schema/
前端入口及静态资源哈希、SQLite integrity_check和foreign_key_check通过。更新前后
全部109,749条既有记录和3,097个资料/资产/页图/PDF/密钥文件完全一致，模型配置不变；
37份当前压缩PDF的ID/状态/链接保持，Range响应匹配保存字节。当前16份关联Notebook
的已解析文字资料全部ready，没有升级自动重建或真实模型调用，最终无活动任务。
PID87630只代表当时状态。完整备份`<private-verification-path>`，
执行日志`<private-verification-path>`；当前生产前端/后端生效。
恢复旧程序必须配合对应数据，不能让旧程序处理新source_reindex或新模型身份。

## Stage 49 — Statistics consent without a receiver (2026-10-04)

基于e49519d，033。当前部署configured=false，前端据此禁用了默认未勾选开关。
改为独立保存用户选择，成功PUT后显示反馈，失败回滚并可重试；12语言说明未配置时
仅本地暂存、不发送。没有修改后台捕获/发送契约，也没有配置外部平台、启用生产同意
或引入账户/商业功能。接收服务运营归属与商业化讨论以033的未实施建议为准。

完整前端78项通过，构建和Prettier通过，语言键/插值由既有完整i18n测试验证；
后台隐私定向9项通过（新增无接收配置时不触发HTTP且关闭清空），Ruff check/format
和git diff --check通过。首次uv检查因受限缓存访问未执行，改为既有虚拟环境对应工具，
以实际执行结果为准。原生隔离浏览器2项通过：configured=false契约可勾选、重开持久化、
关闭/保存反馈，以及既有同意/诊断不含内容检查；前者只模拟配置标志，真实无接收HTTP
行为由后台测试覆盖。浏览器预检通过，截图实际检查。所有接收HTTP仅测试MockTransport
或本地4301，不访问真实模型/外部统计。没有重跑无关的完整后端/Docker验收，Stage48
对应的包装验收仍为上次版本证据，不能称本轮完整Docker复验。

构建暂存`<private-verification-path>`，不在生产dist中
构建。发布只更新静态前端，保留旧hashed assets兼容已打开标签；不重启后端/改DB或密钥。
发布前只读核对活动任务0；旧前端备份
`<private-verification-path>`。HTTP入口与两份静态资源完整
字节匹配构建，统计状态前后均enabled=false/configured=false/queued_events=0，没有
新增接收配置或统计发送。页面刷新后生效。首次核查误用不存在的全局/api/jobs路径得到
404，后续以只读SQLite计数检查任务；没有启动第二个数据目录所有者。

### 当前多语言覆盖核查 — 2026-10-04

用户询问支持是否齐全；只读检查基于1f2a54d，没有修改业务代码或生产偏好。
12目录均725键，键集合、非空值与插值参数一致；定向i18n单测9项通过。
隔离原生浏览器1条覆盖全部12语言的切换/刷新持久化、模型草稿保留、390px/1024px
无横向溢出、阿拉伯语RTL，通过（5.4秒，含服务启动）。无真实模型或生产数据使用；
没有重跑全量/容器验收，也没有据此宣称翻译经过母语审校或12语言模型效果已验收。

尚存的完整性缺口：Setup的API Base URL/API Key/Model ID仍为固定英文技术标签；
DeckDiagnostics日期跟随浏览器默认locale而非应用选择；Chat无足够证据时保存并直接
展示英文INSUFFICIENT，未做本地化映射。后者是系统返回提示，不应混同用户原文翻译。
此外，Chat正常回答按问题语言，Knowledge按源语言（更新保留已有页语言），Deck可
独立选择输出语言；切换界面语言本来就不翻译已保存用户资料/产物。后续补全应保留
该区分、原文引用和旧产物；当前没有把发现的问题标记为已修复。

## Stage 50 — Output languages and localization completion (2026-10-04)

基于50d8593及关联索引修复a5cd7c3，decision034。修复上轮核查的固定技术标签、
英文资料不足系统提示及诊断日期/时长locale；新增笔记本“新内容语言”，默认跟随界面，
可独立选择相同12种语言，提交时冻结给问答/知识/摘要/提纲，Deck继承初始值。
既有内容/原文引文和CitationSpan不翻译、不重写；知识更新保留页metadata语言，
旧API/队列省略参数兼容。Docker增加Noto core字体，无数据库迁移或自动重建。
本节取代Stage49末尾核查中这些“尚存缺口”的当前状态，保留原历史核查作为当时证据。

完整后端519项通过（288.87秒，1个既有Starlette依赖弃用警告），日志
`<private-verification-path>`。新增28项语言契约检查及1项分层缓存检查
覆盖所有语言名/阶段/payload/metadata、无任意指令拼接、原文引用范围、知识更新和旧请求。
补充canonical资料不足metadata断言后，既有相关测试单独1项通过；未新增生产代码。
完整前端80项通过，TypeScript/Vite生产构建、Prettier、Ruff check/format与差异空白检查
通过；12目录均734键，键/非空/插值一致。Vite仍有既有大bundle提示，不作为已修复性能项。
构建暂存`<private-verification-path>`，不在生产dist构建。

原生隔离浏览器7条通过（40.5秒），预检通过，覆盖所有12语言切换/持久化/草稿/
手机与平板/RTL、13次新问答语言请求、印地语知识、阿拉伯语摘要、日语提纲、韩语Deck
初始值，以及设置/索引回归；手机截图已实际查看，无横向溢出。日志
`<private-verification-path>`。先前失败发现未关联旧资料在Embedding
切换后重新关联没有补当前索引，已以a5cd7c3修复，完整后台和浏览器复验通过，不重解析/OCR。
新E2E另修复知识按钮名称包含计数和重复测试TXT复用导致无ingest job的测试前提，
使用每轮不同的合成测试资料；不把早期失败记录称为全部通过。

以上全部使用临时资料、测试provider及MockTransport，无真实模型调用或生产资料测试。
自动检查证明语言传递、约束与引用保护，不证明真实12语言译文准确性、生图文字质量、
母语审校完成或模型始终遵循指令。Docker全套及本地升级结果在完成后补记。

容器前两次均31条通过、1条新语言E2E失败，尚未执行后续重启/重建检查。第一次错误是
把知识页空article可见当作生成完成；第二次poll读取了创建请求尚未返回时的空列表，
抛异常后finally提前删除测试Notebook，使并发创建出现外键拒绝。最终测试明确等待
POST成功回执、该job完成、再按返回的page ID读取metadata，不依靠数组位置或定时睡眠。
修正后原生定向1条通过（20.3秒），日志
`<private-verification-path>`；没有为适应测试弱化业务校验。
镜像Noto Sans Arabic/Devanagari两字体名匹配成功；前述Free字体默认匹配仅证明系统
fallback存在，不代替新增字体安装核对。最终完整容器验收仍待本节后续记录。

最终生产镜像首次设置1条、完整32条浏览器（4.8分钟）及网页原图协议检查全部通过。
restart与force-recreate各自核对83个API快照、41个下载哈希、177个持久文件和3份密钥；
批次重试复用、主动停止状态保留。隔离目录`.docker-acceptance-data.DFFyev`，日志
`<private-verification-path>`。最终以此完整运行作为容器
验收证据；前两轮失败不计入通过总数，无原生/容器浏览器输出目录重叠运行。

本地实现ac4f83f（含a5cd7c3修复，验收修正b39e819）已发布到127.0.0.1:3000。
升级两次确认queued/running为0；在线DB、旧代码/前端及正常停服后的完整数据已备份：
`<private-verification-path>`。单实例正常停止/重启，没有新迁移。
HTTP健康、三种新语言API的12值schema、前端入口/静态资源字节、SQLite integrity及
foreign_key检查通过。更新前后全部109,749条已有记录与3,097个受保护资料/资产/页图/
PDF/密钥文件哈希一致，37份当前PDF的版本/链接/Range下载字节保持；模型与匿名统计
配置保持，统计仍关闭且无接收配置。无升级自动重建、真实模型调用或既有内容翻译。
最终无活动任务；PID36027仅是发布时快照。执行日志
`<private-verification-path>`。旧hashed assets保留供旧标签使用，
刷新后加载新语言选择；回退仍需对应旧代码与完整备份，不能混用模型身份/队列契约。

## Stage 51 — Browser-derived initial language (2026-10-04)

基于80b1bd9，035。未保存选择时前端按浏览器有序偏好匹配12语言，中文Hans/Hant优先
于地区，地区变体归并可用目录，未匹配回退英文。GET ui_language缺省为null，统计
部分更新不再持久化隐式zh-CN；已存值不迁移，PUT仍拒绝null。自动检测不自动PUT或
缓存为固定偏好，读取未设置状态清旧cache，手动保存值优先；既有内容/隐私保持。

完整后端520项通过（284.94秒，1个既有依赖弃用警告），日志
`<private-verification-path>`；偏好/隐私定向29项通过，验证无保存
选择及统计更新/重启后保持未设置。前端110项通过，新增28个匹配案例与2个偏好行为
检查；TypeScript/Vite、Prettier、Ruff check/format与git diff --check通过。首次格式
检查使用错误工作目录，未执行Ruff且提示i18n.ts格式；随后在正确目录检查并格式化，
最终均通过。未更新语言目录内容，原734键/插值检查保持。
构建暂存`<private-verification-path>`，格式化前后
构建输出hash相同；没有直接在生产dist构建。

原生隔离浏览器4条通过（28.9秒）：法国加拿大fr、香港中文繁体、阿拉伯语RTL、
不支持的意大利语回退en、reload自动选择、手动de保存后另一日语浏览器仍de；
问答/知识/转换/Deck的共享新内容语言、已有英文切换与首次设置回归也通过。
日志`<private-verification-path>`。fresh GET使用null契约模拟，不删除
共享数据库；显式PUT和另一个浏览器读取走真实隔离API。后台空库GET/null行为由
实际API单测验证。首次设置测试显式选择中文，避免开发机locale影响原中文操作流程。
没有真实模型/外部翻译调用或生产数据测试。完整Docker及发布状态见后续补记。

最终生产镜像首次设置1条、完整33条浏览器（4.9分钟）和网页原图协议验收通过；
重启与force-recreate各核对83个API快照、41个下载哈希、177个持久文件和3份密钥，
批次复用与主动停止状态保留。隔离目录`.docker-acceptance-data.Y4e11e`，日志
`<private-verification-path>`。没有重叠原生/容器浏览器运行。

实现18adcdc已在完整备份后更新本地127.0.0.1:3000，发布前两次确认无queued/running。
备份`<private-verification-path>`，包含在线数据库、旧代码/
前端及正常停服后的完整数据。API健康/schema/静态资源字节、SQLite完整性与外键检查
通过；全部109,749条旧记录和3,097个受保护文件哈希保持，37份PDF的版本/链接及
Range下载字节保持，模型/统计/已有保存语言不变，无升级模型调用或自动内容改写。
未保存语言时GET新的null契约属预期变化，不代表迁移或删除旧偏好。统计继续关闭、无
接收服务配置。最终无活动任务，PID46620仅当时快照；执行日志
`<private-verification-path>`。保留旧hashed assets，刷新后生效。


## Stage 52 — Bilingual MIT publication preparation (2026-10-04)

User chose MIT and daozen/opennotelm, then requested English and Chinese public-facing
documentation. Original branch/history and private operational copies are retained.
Public docs deidentify machine paths and private case labels without changing historical
verification scope; original v0.1 archives remain unchanged. No production environment,
user data, model requests or live service restart was involved.

Full backend: 533 passed (284.48s, one existing dependency deprecation warning). Frontend:
110 passed, TypeScript/Vite and formatting passed; Ruff check/format and diff checks passed.
13 release-guard cases cover private/runtime files, safe examples and version/tag input.
Full native browser: 33 passed (3.3m). Two initial E2E startup failures used an ancestor
Node 20.9.0; they are not counted as passing. Final invocation uses Node 24 directly,
and Vite uses the same process executable. Matching bundled-browser preflight passed.

First isolated Bookworm container: fresh setup 1 passed, full 33 passed (4.9m), web-image
protocol check passed. Restart and force-recreate each preserved 83 API snapshots,
41 download hashes, 177 persisted files and three decryptable saved keys; batch reuse
and deliberately stopped Deck state retained. This proves the initial package flow,
not any later changed image. Test data/providers were synthetic and isolated.

Python advisory audit originally found three distinct cryptography advisory IDs.
Updated only cryptography to 50.0.2; full regression and synthetic 48.0.1-to-50.0.2
Fernet decryption passed. Updated Python audit found no known vulnerabilities, excluding
the unpublished local project; npm audit found zero. Gitleaks full history and Git-visible
public-tree scans found zero. Reports stay ignored/local, not attached to public CI assets.

Actionlint passed with shellcheck unavailable/disabled; shell syntax checks passed.
Source/notice/source-distribution bundles were generated twice with identical checksums.
Source archive had 393 safe entries and no user/runtime data; runtime notices included
PDFium native BUILD_LICENSES, 48 installed Python packages and 113 frontend production
packages. Inventory covers 49 runtime Python and 310 locked npm entries including development
and optional platform packages; it is not a complete OS/browser SBOM or legal audit.
English/Chinese real UI screenshots use self-written synthetic material and mock providers.

Full Trivy 0.75.0 Bookworm image scan found 82 high and 7 critical package/advisory entries
(44 distinct high/critical advisories, one reported fixed version); Python rows were only
base pip (five medium, one low), with no high/critical language-package findings. These
scanner entries are not all proven exploitable: Debian states CVE-2023-45853 affects
unbuilt contrib/minizip, not the distributed zlib binary. No blanket suppression or
unfixed filtering was added. Container release gate fails on high/critical findings.
Independent Trixie candidate reduced findings to 60 high/1 critical entries (23 distinct
 high/critical advisory IDs), with no reported fixed versions and no language-package
 findings. Available OS updates were applied; unused pip/Xvfb removed. Trixie is supported
 by the installed Playwright version. Final functional/image verification follows below.
 These remaining OS records require targeted applicability review or upstream remediation;
 no suppression or safe-for-release claim is made.

Official checks: [cryptography changes](https://cryptography.io/en/latest/changelog/),
[Playwright supported platforms](https://playwright.dev/python/docs/intro#system-requirements),
[Debian zlib advisory scope](https://security-tracker.debian.org/tracker/CVE-2023-45853).
GitHub configuration, hosted CI, dual-architecture image verification and actual publication
are distinct remaining steps; writing workflows does not establish any of them.


Final Debian 13/Trixie image: fresh setup 1 passed (1.6s), all 33 browser flows passed
(4.9m), web-image protocol checks passed. Restart and force-recreate each retained
83 snapshots, 41 download hashes, 177 files and three saved decryptable secrets, batch
reuse and deliberately stopped state. Matching browser 153.0.8010.12 exported 8,557,082
bytes of complete credits (757 license sections) and built-in terms; both are retained
in the image. Removed base pip and Xvfb confirmed. Production was not upgraded.

Final submitted container_scan.sh produced a CycloneDX SBOM and retained every severity
record, then correctly exited 1 on the remaining 60 high/1 critical OS entries; the
security gate has NOT passed. No fixed versions were reported for those entries.
Trivy noted the font descriptor “M+ FONTS License” could not be normalized as SPDX;
installed font copyright files remain available. SBOM generation does not replace
license review or certify a vulnerability-free image. No Docker/host data was scanned.

Clean public branch continues the remote LICENSE-only commit, with a signed-off source
snapshot and final evidence update; original private history remains on its original
branches. An isolated single-branch clone passed Git fsck with no unreachable history.
Public source archive contains 396 reviewed entries; all manifest hashes checked.
The initial public build guard rejected untracked temporary dependency symlinks; local
Git excludes corrected the test setup without relaxing committed-source checks.
Bilingual release notes render version-pinned links, and source/notices/source archives
and SHA256SUMS are prepared locally. Actual push/tag/GHCR/Release are not performed.
See RELEASE_STATUS for remaining OS triage and owner/cloud checks, not a publication claim.
## Stage 53 — Native XML and container hardening (2026-10-05)

Scope: continue MIT release preparation and resolve confirmed native-library gaps;
no production data/model calls, service upgrades, tags, registry pushes or GitHub
Release. The working preparation branch remains separate from the clean public
snapshot. See decision037 and the bilingual CONTAINER_SECURITY_REVIEW.

- Actual lxml 6.1.3 wheel previously loaded libxml2 2.14.6. The same locked source
  now builds a static wheel against checksum-pinned libxml2 2.15.4 / libxslt 1.1.45.
  Both compiled and runtime XML versions verified inside the candidate. CPython
  separately reports Expat 2.8.5. Native `uv sync` is not patched by the Docker build.
- Native build sources/hashes, full XML/XSLT/libexslt copyrights retained. Runtime
  checks reject a mismatched wheel/library or downgraded security baseline; native
  SBOM additions preserve existing OS components and the original scanner SBOM.
- Actual Compose app inspect confirms user `app`, cap-drop `[ALL]` and
  `no-new-privileges:true`. Initializer uses only CHOWN; no recursive ownership or
  stored-file rewrite. Component-absence probes confirmed no cupsd/lp, systemd-homed,
  Archive::Tar or system Python libxml2 bindings in the candidate.
- Backend non-browser regression: **518 passed, 18 browser tests deselected**
  (258.43s), then **19 focused release/native checks passed**, comprising 13 previous
  release guards and 6 native tests. These counts overlap; do not sum them.
  The final three native additions were verified in the focused run after the main
  regression started. One known Starlette/httpx deprecation warning remains.
- Isolated Docker: empty setup **1 passed** (1.7s), full suite **33 passed** (4.8m),
  five web-image formats and article/original-byte preservation passed. Restart and
  force recreation each preserved **83 API snapshots, 41 download hashes, 177 files,
  3 decryptable model secrets**, independent sibling reuse and deliberate stop state.
  Actual tested image: `sha256:44b3f99ae1e3dc50a7eb37fdf3cf7bdfb9d1e421fe29f2bcfc7e95c49649bab8`.
- After final license/version-check changes, rebuilt candidate
  `sha256:da05b8627d8e2e2913f4b99ed4a0d8c1ae43a576c5eee608ee2b45c440c2782d`
  passed actual Chromium 153.0.8010.12 startup, 1920×1080 screenshot and one-page
  1440×810 PDF/text check, plus the five-format mocked web-image protocol acceptance.
  Runtime remains XML2.15.4/XSLT1.1.45. The full 33-flow run refers to the earlier
  candidate above; final differences are release notices and strengthened checker/tests.
- Full final Trivy scan intentionally **failed**, retaining **60 HIGH + 1 CRITICAL**
  records, **23 unique advisories** (also 127 MEDIUM/129 LOW/2 UNKNOWN). Raw JSON/SBOM
  retained; enriched SBOM adds the two actual static XML components without deleting
  old OS-library entries. No blanket ignore list or claim of zero vulnerabilities.
- Ruff check/format **247 files**, Bash syntax and pinned Actions lint passed.
  Release file/MIT/version/local-link guards and diff-whitespace checks passed.
  Frontend source was unchanged, so its prior 110 tests/native 33 flows were not repeated.
- GitHub repo read confirms expected owner/admin permission and unchanged LICENSE-only
  main. HTTPS/SSH dry-run push attempts lacked a usable local identity and changed
  no remote refs. Browser/settings authentication and real hosted CI remain outstanding.
- Clean public snapshot continues only the existing remote LICENSE history; tree equality,
  DCO, fsck and complete public Git bundle checks passed. Public history/file secret
  scans found no matches. Release assets contain 404 safe source entries, 113 frontend
  notices, XML/XSLT original copyrights, and five hash-verified upstream archives
  (certifi, tld, lxml, libxml2, libxslt). Manifest commit/asset hashes and separate
  native-component inventory checked; no runtime data, symlinks or private history.

Remaining release blockers are explicit in RELEASE_STATUS and CONTAINER_SECURITY_REVIEW:
finish system-library applicability/patch review and GitHub settings/hosted checks,
then verify both release architectures and deliberately approve publication. Native
OS/package scans, real-model quality and a general security/legal audit are not proved
by these tests. Production application and live data remain untouched.

## Stage 54 — Hosted Beta checks and vendor fixes (2026-10-05)

Scope: execute the explicitly authorized public upload/hosted checks and prepare
publication after passing gates. No new publication authorization is required; actual
account login/settings and completed release checks remain operational prerequisites.

- Uploaded 404 reviewed files through GitHub Git Data APIs, including nine synthetic
  binary fixtures/captures whose Git blob hashes were verified. Remote tree
  `dd447eeae2f9a6ac0b744645b84f8b254a5d38c6` matches the local public snapshot.
  Commit `03bd8580412adb45ec674ab0d2faaa3c2b0489a8` has only the original LICENSE
  commit as parent; native fetch confirms author/footer identity. Private history
  was not uploaded. [PR 1](https://github.com/daozen/opennotelm/pull/1) is attached.
- Actual [hosted run 37235053270](https://github.com/daozen/opennotelm/actions/runs/37235053270)
  passed release contracts, secrets, DCO and Python dependency audit. Backend had
  **536 passed, 3 failed in 471.06s**. All failures were still-running image/PDF tasks
  exceeding the five-second test wait, rather than successful results being accepted.
  Corrected both the shared deadline and the ten-page explicit override to 30 seconds;
  terminal status/result assertions and production contracts remain unchanged.
- **54 affected generation/retry tests passed** (89.57s). **42 focused security/release
  checks passed** (23 new checks plus 19 existing guards). These are focused results,
  not a claim of a current full local backend pass. Backend/frontend/Docker CI jobs
  now run independently, with every job required by the reusable release workflow.
- Compatible official Debian Expat **2.8.5-2** and ACL **2.4.0-1** binaries were pinned
  for both architectures using hashes from signed Debian indexes. ARM64 image build,
  exact identities, dependency health, package file checksums and loaded Expat version
  passed. Corresponding source/packaging hashes and complete notices are included.
  Runtime retains no unstable repository. Source-archive attachment verification for
  this incremental candidate remains a separate step.
- Linux server rendering uses CPU drawing, without host graphics/LLVM/XML input;
  unused mount/umount/nsenter/infocmp executables are removed. Actual runtime probes
  verified 82 runtime-code/lockfile hashes, matching policy digest, exact affected
  package versions, UID/capabilities/no-new-privileges, component absence, no authorized
  mounts/display/graphics devices, and real screenshot/PDF process maps.
- ARM64 image `sha256:c2df6905cb5c6f3b52b38112c942dccdc3a2d8f324daac480d7b23d2f4b25159`
  passed the complete scanner/review gate: raw **60 HIGH + 1 CRITICAL** retained,
  **5 verified vendor-fixed records**, **56 conditional supported-runtime records**,
  **zero unresolved high/critical records**. Full raw JSON, raw/enriched SBOM and
  independent evidence remain local. This is not a general OS patch/security claim.
  Version/source/policy changes, new advisories, missing evidence or expiry on
  **2026-11-04** require reassessment; negative tests exercise these failure paths.
- Both vendor-fix and final CPU-hardened candidates passed isolated fresh setup
  **1 + 33 browser flows** (5.0m and 4.9m). Restart and recreation each preserved
  **83 snapshots, 41 download hashes, 177 files, 3 decrypted synthetic secrets**,
  stopped Deck state and batch sibling reuse. Five-format web-image checks passed.
  Isolated containers were cleaned up; no native/Docker browser output overlap.
- Ruff check/format **252 files**, workflow lint and browser startup/render/PDF
  preflight passed. Existing live data/service/native dependencies were not changed;
  no actual model calls or user-material tests were used.

Follow-up hosted checks, both release architectures, account-dependent settings,
tag/image visibility, anonymous pulls, final bilingual assets and Beta publication
are recorded separately as they actually complete. Initial cloud failures above
are retained as historical evidence, rather than replaced with local passes.


## Stage 55 — Hosted results and precise checksum false positive (2026-10-05)

[Run 37238505777](https://github.com/daozen/opennotelm/actions/runs/37238505777)
tested public head `efe5078c7f9da7077b54c3035fafcfda3f206387`, whose tree exactly
matches the locally reviewed tree. Both public commits have DCO identity verified;
private development ancestors remain local.

- Hosted backend: **562 passed in 432.50s**, Ruff check/format passed.
- Hosted frontend: **110 passed**, build/format/npm audit passed; **33 real browser
  flows passed in 5.8m**.
- Hosted amd64 container: fresh setup **1 + 33 flows passed** (5.3m), restart and
  recreation each preserve **83 snapshots, 41 download hashes, 177 files and 3
  decrypted synthetic secrets**. Stopped Deck and batch sibling preservation passed.
- Hosted amd64 raw scan retains **60 HIGH + 1 CRITICAL**. Actual native/vendor
  checks and supported-runtime probes pass; **5 fixed**, **56 conditional**, **zero
  unresolved high/critical records**. This is the same scoped, expiring assessment
  as local ARM64, not a general OS security claim or final published-digest check.
- Release contract passed metadata checks but Gitleaks flagged the exact public
  `secrets.py` source SHA-256 in the runtime-review manifest. Independently recomputed
  hash matches; this is a checksum, not a credential. Added a rule-specific exception
  requiring BOTH exact path and entire exact record. All default rules remain active.
- Actual local Gitleaks verifies the exception, rejects the same value in another
  file, another value in the same record, and an API-key-shaped value in the same
  manifest. Public Git history and tree scan pass; reports remain fully redacted and
  local. Cloud failure logs now identify the failed stage without detected values.
- This scanner-only correction and documentation require hosted follow-up. No live
  service/data or product behavior was changed. Account login/settings, final
  release assets/tag/image digest and actual Beta publication remain pending.
