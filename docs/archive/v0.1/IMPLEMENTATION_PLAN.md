# V0.1 implementation and verification

The supplied [PRD](PRD.md) and [system design](SYSTEM_DESIGN.md) are the product
contract, extended by later explicit user requests. The 2026-10-02 request adds
DOCX, source-image recognition, scanned PDFs and batch chapter scopes. Cloud accounts
and autonomous agents remain outside this implementation.

## Architecture decisions

- React + TypeScript + Vite; FastAPI + Python 3.12; one ASGI server and an in-process
  durable SQLite worker. The browser and API share one origin in production.
- SQLite WAL, ordered transactional SQL migrations, foreign keys, a single `data/`.
- Raw documents and normalized blocks are the fact layer. Retrieval indexes are
  disposable. Citations always refer to block spans, never chunk IDs.
- Provider calls live behind one gateway. All credentials are environment
  references or encrypted files; the encryption key is part of the data backup.
- Embedded cosine search is sufficient for 50 sources/notebook. No external vector DB.
- Model-authored semantic content and deck style retain original-source citations.
  Following the user's phase 21 decision, new Decks use image-generated complete
  pages including text; saved native Decks retain their RenderSpec and measured text.
- Heavy work runs through a SQLite queue, one heavy job at a time. Stages and slide
  outputs are persisted so recovery can preserve completed work.
- Anonymous telemetry defaults off; strict event/property allowlists if enabled.

## Milestones

| # | Vertical slice | Required verification | Status |
|---|---|---|---|
| 1 | Skeleton, migrations, Docker, notebooks, tested model setup | API/secret/provider tests, browser flow, restart | Implemented; production-image Docker acceptance passed on 2026-10-02 |
| 2 | EPUB import, normalized model, chapter reader | Valid book, hostile ZIP, persisted reader | Implemented |
| 3 | Chunk, embedding, scoped retrieval, grounded chat | Scope isolation, follow-up, provider failures | Implemented |
| 4 | Evidence validation, citations, reader jumps | Fabricated ID rejected, exact original quote | Implemented |
| 5 | Text PDF, Markdown, TXT | Scanned PDF rejection, semantics, sanitization | Implemented |
| 6 | Knowledge generation, edit, update, provenance | Full scope synthesis, preservation, citations | Implemented |
| 7 | Deck brief, narrative, style, semantic slide content | 10/15/20 plans, schemas, provenance | Implemented |
| 8 | Model visual composition, deterministic renderer | Render bounds, page output, text positions | Implemented |
| 9 | Image adapter, assets, partial states | One failed slide, retry, continue without image | Implemented |
| 10 | PDF export with searchable text | Page count, text extraction, visual inspection | Implemented |
| 11 | Slide revisions, text edits, reorder, delete | Only changed slide regenerated, stale export invalidated | Implemented |
| 12 | Recovery, diagnostics, privacy, release acceptance | Restart/upgrade, queue retry, full browser E2E | Recovery/privacy implemented; final audit and release acceptance pending |
| 13 | Source-specific editorial depth and illustrated visual storytelling | Compare real outputs with the supplied NotebookLM reference, inspect every page, preserve exact searchable text and original citations | Implemented; replacement real PDF reviewed after targeted revisions, user evaluation open |
| 14 | Readable PDF source preview | Reflow character/word fragments on existing imports, retain page/citation anchors, adjustable type and expanded reading, desktop/mobile browser checks | Implemented; existing PDF APIs and regression checks verified |
| 15 | Container runtime and reproducible deployment acceptance | Clean setup, full browser suite on production image, 15-page PDF, restart/recreation, encrypted secrets, host model connectivity | Implemented; macOS Colima / Linux ARM64 acceptance passed; CI check added |
| 16 | Simplified Chinese / English interface | Hot switching, persisted locale, privacy independence, untouched source content/drafts, complete browser and Docker flows | Implemented; bilingual browser and Docker acceptance passed on 2026-10-02 |
| 17 | Paragraph evidence and citation context | Existing glyph citations, exact offsets, complete wrapped sentences, scoped paragraph evidence, reader jump and restart | Implemented; native and production Docker acceptance passed on 2026-10-02 |
| 18 | Addressable workspace navigation | Notebook/chapter/knowledge/Deck deep links, refresh/new-tab/history restoration, scoped questions and draft protection | Implemented; native and production Docker acceptance passed on 2026-10-02 |
| 19 | Reader continuation and honest directory | Previous/next chapter and page, separate PDF page jump, no invented directory, footer focus, exact scopes and refreshed locations | Implemented; native and production Docker acceptance passed on 2026-10-02 |
| 20 | Integrated explanatory Deck scenes | Design before artwork, concise copy budgets, cited visual relations, native curves/pictograms, visible path/text checks, legacy asset compatibility | Implemented for saved/native Decks; real trial was 14/15 renders, not visually accepted; user chose whole-page image generation in phase 21 |
| 21 | Whole-page image Decks | One image-model call creates each complete page including text; default creation, saved-content copies, single-page revisions/retry, lossless raster PDF/preview, preserved original citations | Implemented; 15-page real-provider review and final native/Docker acceptance passed; user visual evaluation open, automated image-text verification not implemented |
| 22 | Varied visual expression across the Deck | Research public generation workflows, persist a whole-deck visual repertoire, content prerequisites and repetition checks, stable per-page caches, bilingual plan/copy UI, compare a real 15-page copy | Implemented; 193 backend tests, Docker acceptance and real 15-page review passed; automatic image-text verification remains open |
| 23 | Direct source content, concurrent images and a stable Deck viewer | Remove unsolicited editorial notes upstream; preserve legacy copy and offer a content-rewritten copy; bounded whole-page workers, cancellation/retry/page-order checks, serial/parallel real-provider comparison; independent rail/preview scrolling and fitted image | Implemented; 205 backend tests, 25 frontend tests, native/Docker browser acceptance and real-provider two-page comparison passed; deployed to LAN on 2026-10-02 |

Each completed milestone needs a working browser flow, persistence, error handling,
relevant retry behavior, meaningful automated tests, and a manual acceptance path.
Commits are kept by coherent change; lockfiles and CI make builds reproducible.

### Current document enhancements

| # | Vertical slice | Required verification | Status |
|---|---|---|---|
| 24 | Model-settings image concurrency, 1–20 | Persisted values, frozen running tasks, bilingual UI, Docker restart | Implemented in `abb4651` |
| 25 | Word `.docx` upload | Body/heading/list/table semantics, safe archives, migration preservation and rollback | Implemented; backend and browser acceptance passed |
| 26 | Document images and scanned PDF | Original previews, bounded vision schema, capability probe, citations, failed/partial retry, stable facts and rebuilt indexes | Implemented; fixture-provider and real `gpt-6-luna` image-recognition acceptance passed; real sampling used the previously authorized PDFs through localhost:8317 only |
| 27 | Batch chapter Visual Deck scopes | PDF/EPUB/Word directories, non-heading EPUB anchors, empty/foreign scopes, overlap, ordering and excluded content | Implemented; backend and browser acceptance passed |
| 28 | Separate Deck batches and directory tree | Generation mode/counts, source subsets, parent/child/mixed selection, level selection, atomic creation, idempotent retry, independent scopes/citations/retry and persistence | Implemented; 245 backend and 37 frontend tests, 19 Docker browser flows across the full run and targeted rerun, restart/recreation integrity passed; deployed to LAN on 2026-10-03 |
| 29 | Deck stop/resume/delete and viewport-sized preview | Queued/running cancellation, saved-progress resume, cancellation persistence, owned-file cleanup and preserved sources/siblings; desktop/iPad/phone focus preview | Implemented; 254 backend cases, 40 frontend tests, 20 Docker browser flows and final focus/lifecycle checks passed; restart/recreation retained stopped work; deployed to LAN on 2026-10-03 |
| 30 | User-directed Deck interpretation | User instructions from first reading; model explanations/background/examples with distinct provenance; editorial defaults and source-only/density overrides; fresh content-copy research and preserved original | Implemented; validation and real textual sampling recorded in ACCEPTANCE.md and decision 015 |
| 31 | Content-adaptive visual style | Content/request-aware direction comparison, preserved medium through image generation, flat-style compatibility, restyled copies with unchanged text/citations, legacy prompt preservation and real cross-topic sampling | Implemented; validation recorded in ACCEPTANCE.md and decision 016 |
| 32 | Adaptive style on content-rewrite copies | Reproduce legacy style inheritance, opt both UI copy entries into restyling, backend defaults and explicit preservation, distinct-palette regression and browser click flow | Implemented; affected regression and browser validation passed, recorded in ACCEPTANCE.md |

## Verification constraints

This development host initially had no Docker executable or user-provided AI
credentials. User-configured Language, Embedding and Image models are now available
and real-provider acceptance is in progress. Mock provider tests validate protocol
and failure handling; they are not a substitute for real model quality/capability
or Docker release acceptance. The Docker environment and production-image acceptance
were completed on 2026-10-02; see [Docker acceptance](../../DOCKER_ACCEPTANCE.md).
Unverified release checks remain explicitly pending.
