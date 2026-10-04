# Configurable document image recognition concurrency

> 2026-10-03 文档整理：范围说明：本功能控制导入/重试识别；Deck 的分段理解与页写作并发随后单独在 [020](020-deck-generation-reliability.md) 实现，三项设置独立。

Date: 2026-10-03

## Decision

Document image recognition now uses a fixed worker pool instead of a serial image loop.
The independent setting is in Model settings → Language model → Image recognition
concurrency. It accepts strict integers 1–20, defaults to 4, and is persisted under the
`image_recognition` app-settings key. GET/PUT `/api/settings/models/image-recognition`
change only this setting: saving does not call providers, alter model credentials,
retest capabilities or change Deck image generation concurrency. Unsaved installations
use `IMAGE_RECOGNITION_CONCURRENCY`; Docker Compose exposes the same fallback.

Each source-ingestion/recognition-retry task snapshots its limit once. This bounds native
image preparation, memory-resident payloads and model requests, rather than creating an
unbounded coroutine per page. Results and image metadata retain original document order;
progress advances by completed images regardless of completion order. The existing
single source-job queue is unchanged. This does not parallelize Deck interpretation or
embedding batches. Recognition continues to use the configured language model.

Successful transcripts remain immutable source recognition facts. A per-kind/checksum
lock allows concurrent duplicate images to reuse one successful model response and
serializes shared checkpoint writes. Missing/corrupt caches are retried; one failed image
does not discard successful images. Existing JSON repair and faithful-transcription
instructions remain unchanged. Changing concurrency does not invalidate transcripts.

Cancellation joins the worker group and outstanding native image decoding before
returning, retaining completed checkpoints for retry. PDFium page rendering retains its
thread-safety lock; model requests overlap outside this lock. Original source media,
transcript size limits, image normalization and citation provenance are unchanged.

## Validation and limits

Tests cover limits 1/4/20, out-of-order completion, monotonic progress, settings changes
while running, duplicate single-flight, partial failure/cache retry, cancellation and
native-thread cleanup. API tests cover strict validation, environment fallback,
restart persistence and independence from generation/model/preference/secret settings.
Shared UI tests cover load/save failure and retry; browser tests cover placement,
Chinese/English switching, reload persistence and narrow-screen layout.

The configured local language endpoint accepted four simultaneous requests for four
existing PDF images, returning four valid results in 16.4 seconds. Retrying used cached
results without new requests. This verifies that endpoint at concurrency 4; it is not a
serial-versus-parallel benchmark or a guarantee that a provider supports concurrency 20.
Actual speed depends on provider capacity and rate limits.
