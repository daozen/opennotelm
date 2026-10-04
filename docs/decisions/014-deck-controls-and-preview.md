# Deck controls and viewport-sized preview

2026-10-03 UI follow-up: [decision 022](022-ui-review-and-common-languages.md) replaces the stacked small-screen source/Studio panels with section navigation. Lifecycle APIs and independent preview scrolling remain.

The 2026-10-03 request adds stop/resume/deletion for every Deck and improves
reading on smaller screens. It extends the existing generation queue and cached
pipeline rather than creating replacement Decks for resume. No database migration
is required; job cancellation is already a supported durable state.

## Preview

The previous fixed-height workspace allocated its leftover height to the preview.
Titles, progress, export controls and descriptions therefore made the preview
smaller, especially on tablets. The preview now owns approximately one dynamic
viewport of height, with a 520px lower bound in the normal workspace. The surrounding
page scrolls to reach it. Its thumbnail rail and page content still scroll
independently, and selecting a thumbnail resets only the page content scroll.

At widths of 1100px or less the Deck occupies the full workspace width; the source
and Studio panels follow it. Phone thumbnails form a compact horizontal rail.
A focus-preview dialog covers the viewport, locks background scrolling, contains
keyboard focus and closes with Escape or its exit button. Previous/next page controls
and a current-page counter make it usable without the rail. Focus restores to the
entry control, and the original page scroll position is retained on exit. Preview
images fit the available content space. This does not change saved images or PDFs.

## Stop and resume

`POST /api/decks/{id}/stop` works for both queued and running work, including
page revision and export tasks belonging to the Deck. A transaction marks the job
cancelled and the Deck paused before cancellation is delivered. Queued work cannot
be claimed, and cancelled work is not automatically requeued on application restart.
Running work has a separately tracked task; cancelling it joins its complete cleanup,
including the page TaskGroup and shielded image/PDF writing threads. The heavy worker
continues with other Decks after an intentional cancellation. Progress and terminal
job updates cannot overwrite the persisted cancelled state.

`POST /api/decks/{id}/resume` requeues the same job identity and exact payload. This
preserves an already-applied page revision or an export request. Existing content,
plans, design, ready image assets and renders are reused by the pipeline's caches;
only incomplete stages are continued. Repeated resume of active work returns its
current state. The older manually stopped Decks also support resume through their
cancelled jobs. Intentional cancellation is logged separately from generation
failure and does not emit a failure telemetry event.

Mutation routes and the generic job-retry route serialize by entity while cancellation
unwinds, so resume, edits and deletion cannot race with one another. Read-only polling
continues normally. Stop closes the application's request to its provider; whether
an already-submitted remote request itself stops or consumes usage depends on the
provider, which is outside this application's job lifecycle.

## Delete

Every Deck has deletion in both its viewer and Studio card, regardless of status.
A confirmation names the Deck and explains that its pages, images and PDFs are
removed while original sources remain. The delete endpoint first cancels and joins
any related running work. One transaction deletes its slide citations, jobs and Deck.
Existing foreign-key cascades remove page designs, assets, all render/export versions,
revision records and checkpoints, and existing durable garbage-file triggers enqueue
file cleanup. Cleanup drains after commit and retries after restart if interrupted.
Repeating deletion of an already-deleted Deck succeeds without touching other data.

Batch receipts are retained as tombstones. A repeated original request whose Deck
was deleted returns `DECK_BATCH_DELETED` instead of silently recreating it or returning
an invalid Deck. A new generation request uses a new request key. Library refreshes
ignore superseded responses so an old poll cannot reinsert a deleted card. Deleting
the open Deck returns to the notebook conversation and clears its address.

## Verification

Tests cover queued/running stop, restart persistence, exact-payload resume, cached
content/images, pre-start cancellation, surviving worker/siblings, idempotent operations,
full owned-file cleanup, and deletion while an actual PDF assembly thread is running.
Frontend tests exercise stop/resume, explicit confirmation and failed deletion, bilingual
focus preview, Escape and focus/scroll restoration. Browser checks generate synthetic
Decks, stop queued and image-generating work, resume cached pages, preserve independent
PDFs/sources, and delete through the viewer and Studio. Desktop, iPad landscape/portrait
and phone dimensions verify the minimum preview height, full-screen fit and no horizontal
overflow. All acceptance providers are isolated synthetic providers.
