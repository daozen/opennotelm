# Image concurrency in model settings

Status: Accepted, 2026-10-02. Supersedes decision 010's 1–4 range.

2026-10-04: [029](029-bounded-cross-task-scheduling.md) replaces single-heavy-job
execution with bounded task scheduling and shared preparation/provider budgets.
The saved per-run 1–20 snapshot and old artifact compatibility remain.

Expose image concurrency in the image-model card with a separate save action.
Changing this limit does not invoke model capability tests, create test images,
or update model credentials. Both Chinese and English interfaces support 1–20;
the default remains 2. A value of 1 makes whole-page generation serial.

`GET/PUT /api/settings/models/image-generation` reads and validates the limit.
Persist the validated integer under the `image_generation` app-settings key.
Precedence is persisted setting, then `IMAGE_GENERATION_CONCURRENCY`, then 2.
Language and telemetry preferences retain their separate storage and API.
No schema migration or data rewrite is needed.

Snapshot the limit before a Deck generation run's first model call. Updating
settings during understanding, authoring or image creation affects later runs,
including queued jobs and retries, while the active run keeps its original cap.
Record the cap in completed Deck generation metadata. PDF ordering, isolated
page failures and cancellation retain the behavior in decision 010. Native
browser composition remains serial; one heavy job runs at a time.

Tests verify strict API bounds, saved-value precedence across a real restart,
unchanged model credentials/preferences, retryable UI errors, and actual peaks
of 1, 2 and 20 in a delayed mock image provider. The 20-request test verifies
application scheduling; each real provider's capacity and rate limit vary.
