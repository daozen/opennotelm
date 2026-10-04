# Reliable Deck evidence, local repairs and content workers

Date: 2026-10-03

2026-10-04: [029](029-bounded-cross-task-scheduling.md) adds bounded cross-task
scheduling and shared stage/provider budgets, replacing the single-heavy-job rule.
Evidence, local repair, checkpoint, cancellation and saved artifact contracts remain.

## Failure mechanisms

The chapter planner received whole-work evidence IDs but validated against only IDs
appearing in the chapter dossier prose. Registered background references were consequently
rejected. Source-image readings also used valid IDs in Markdown links or single brackets;
the strict double-bracket matcher treated these responses as uncited. Retrying regenerated
the entire reading or twenty-page storyboard without supplying the rejected candidate.

Additional real-case verification exposed two further issues: the conservative UTF-8
byte/token estimate rejected normally completed Chinese output whose reported token usage
fit the allocation; and page structure and copy length could fail successively, exhausting
two attempts before the newly exposed constraint could be repaired.

## Evidence and repair contract

Planning receives a catalog of primary/background packets with registered immutable spans.
Background packets supplied by whole-work context remain valid even when not quoted by the
selected dossier. Chapter focus and page-level allowed references remain explicit. Unknown
IDs are rejected; original citation spans continue to be checked and persisted unchanged.

Normalize bracketed references only when their exact IDs belong to the current catalog:
single/double brackets, whitespace and empty/# Markdown anchors. Do not guess numeric
footnotes, strip unknown IDs or reinterpret arbitrary external hyperlinks.

Structured retries receive candidate JSON, diagnosed field paths and feedback as untrusted
user data. Independent page constraints are diagnosed together even when schema validation
fails first: citation basis, copy length and dependent hierarchy/relationship references.
Request bounded field patches for planning; page authors return a complete single-page
structure because nested patch syntax was itself unreliable in real cases. Apply only the
diagnosed fields and validate the complete candidate again. Container paths subsume their
descendants so removal of an element does not leave stale array indices in the repair.
If a provider returns full JSON despite the patch request, copy only diagnosed fields where
paths are available. Other valid pages and successful synthesis checkpoints are retained.
Planning and synthesis allow two attempts. Page authoring permits a third only when a prior
repair exposes a different validation constraint or substantially reduces copy overflow;
unchanged failures stop after two. Copy-only repair retains original facts/quotations and
avoids reattaching image pixels. Schema or semantic repairs retain required originals.

Opening/body/closing authors receive explicit copy targets. The storyboard reading budget
is a design target with an 8% counting margin; the absolute page ceiling remains 450 units
(or 900 for explicit dense-copy preferences). A budget failure reports fragment counts and
a lower target. Do not silently truncate substantive content or quoted words.

When an illustrated Deck still has unauthored pages, retain valid page specs and mark it
partial before art direction. Preserve the page error instead of masking it with
DECK_CONTENT_REQUIRED. A bulk retry authors only missing pages, then continues art, image
generation and export; previously valid content and its citations remain unchanged.

Use reported positive integer completion-token usage when available, otherwise the existing
conservative estimate. Reject length-truncated syntheses and enforce a separate bounded
UTF-8 size ceiling even when usage is reported. Existing already-valid checkpoints remain
compatible. This does not increase configured model context/output budgets.

## Concurrency and reusable visual readings

Model settings → Language model → Deck content generation concurrency accepts strict
integers 1–20, default 2, independently of image recognition and final image generation.
GET/PUT `/api/settings/models/content-generation` persists only this setting. Environment
fallback is `CONTENT_GENERATION_CONCURRENCY`, also exposed by Docker Compose.

Each Deck snapshots its limit at start. Fixed workers overlap independent reading groups
and page authors; results retain input/slide order and progress counts completed work.
Global understanding reductions, narrative/style decisions, art direction and export remain
ordered. Cancellation joins all workers and native file preparation/cache writes before
returning. Provider failures preserve actionable errors and successful checkpoints/pages.

Validated compact original-image readings can be reused across identical requests.
Source-owned `visual-readings` caches bind source/block/checksum, model endpoint/ID/context,
prompt/visual versions, instructions, preferences and whole-work context. Canonical IDs
permit reuse across jobs and are remapped to current original-source IDs on load. Validate
cache references and size; corrupt/missing entries are misses. Atomic writes prevent partial
entries. Source deletion removes its cache. Page authors still receive relevant originals;
this cache does not substitute transcripts for required original-pixel understanding.

## Diagnostics and limits

Migration 017 adds content-free per-attempt diagnostics tied to a job, deleted with it.
Record stage, latency, attempt, outcome, known validation categories/field paths, actual
attached-image count, citation normalization and safe provider finish/token metadata.
Task-local context prevents parallel requests from mixing usage. Export no prompts,
source text, rejected values, unrecognized field names or credentials. Deck errors identify
source interpretation, planning or page validation instead of calling all failures a
knowledge-page error.

Tests cover registered background absent from prose, unknown citations, exact normalization,
patch preservation, bounded/progress-sensitive repairs, usage/truncation, cache remapping,
corruption, concurrency 1/2/20, stable order, snapshot changes, cancellation/native cleanup,
restart persistence and diagnostic privacy. Real-model samples verify two book chapters and
the illustrated PDF; samples cannot establish an aggregate production failure rate or
provider capacity at concurrency 20. Generation speed still depends on provider capacity
and document/deck size.
