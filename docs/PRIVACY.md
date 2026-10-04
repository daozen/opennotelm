# Privacy and diagnostic data

[简体中文](PRIVACY.zh-CN.md)

Documents and artifacts live in the local data directory. AI features send the selected
evidence, instructions and relevant saved content to the model endpoints configured by
the operator. Offline inference requires local model services.

## Diagnostics

Settings → “下载诊断报告” downloads JSON containing app/OS/parser versions, source type
counts, configured model IDs, up to 100 job traces, up to 100 content-generation attempt
records and aggregate retrieval scores from the last 50 answers. Attempt records include
stage, duration, outcome/attempt number, allowlisted validation categories/field paths,
image counts and safe token/finish metadata. Task-local metadata isolates concurrent calls;
unknown field names and rejected values are excluded. Deck → “查看失败详情” / “查看生成记录”
loads only that Deck's jobs, runs, page states and up to 500 attempts (50 shown in the UI).
Refresh and download are available; known rules, safe numeric constraints and available
HTTP status/error codes identify schema, evidence, copy-budget and request failures.
Older attempts cannot gain details that were never recorded. These selected outcomes
are not complete provider request tracing. It excludes filenames, titles, source text, questions, prompts,
responses, endpoint URLs, secrets, raw logs and database dumps. Unrecognized error
codes are replaced with `UNKNOWN_ERROR`. Inspect a downloaded report before sharing it.
Downloading a report does not send it to a support service.

Local job logs contain only event, stage, random entity ID, safe error code, elapsed
time and app version. Framework automatic tracing/metrics/log export is explicitly
disabled, including automatic OTLP setup from environment variables. Production starts
without access logs. No browser analytics SDK, replay, autocapture or prompt tracing
is installed.

## Optional anonymous statistics

Statistics default off. Enable or disable them in Settings → “允许匿名使用统计”.
Disabling clears queued events and prevents subsequent sends; requests that began
before disabling may already have reached the receiver. AI model configuration is
independent of this setting.

Supported events: `app_started`, `source_import_started`, `source_import_completed`,
`source_import_failed`, `chat_message_sent`, `chat_response_completed`,
`chat_response_failed`, `knowledge_generated`, `knowledge_updated`,
`deck_generation_started`, `deck_generation_completed`, `deck_generation_failed`,
`slide_regenerated`, `slide_revised`, `pdf_exported`, `model_connection_tested`.

Business properties are limited to source type, file size bucket, slide count, duration
bucket and a known error code. The sender adds app version and OS family. Durations
are rounded up to 1 second / 10 seconds / 1 minute / 5 minutes / 1 hour / 1 day; file
size buckets are below 1 MiB, 1–10 MiB, 10–50 MiB and 50 MiB or more. No source, notebook,
slide or job identifier is sent. A randomly generated install UUID persists locally;
it is never derived from hardware, email, IP address or a key.

Events are validated before entering the SQLite queue and again before sending. The
queue retains at most 1,000 events for at most seven days. Batches contain at most 50
events, retry from one minute to one hour, and preserve event UUIDs across retries.
No usage is backfilled from time when statistics were off. Network failures do not
fail document or generation tasks. Model-client credentials and cookies are never
shared with the statistics client; redirects are rejected.

## Receiver configuration for self-hosted deployments

There is no built-in project token. Operators who want statistics can supply their
own PostHog project token as `TELEMETRY_PROJECT_TOKEN` and optionally `TELEMETRY_HOST`.
The default host is `https://us.i.posthog.com`; an EU or self-hosted HTTPS host is also
supported. Loopback HTTP is supported for local testing. Restart after changing these
environment variables, then explicitly enable statistics in Settings. With no token,
the UI reports that sending is unavailable, but you can still save an opt-in choice;
events remain in the bounded local queue until a receiver is configured. A public project ingestion token is used,
not a personal PostHog API key. No PostHog account is required to use OpenNoteLM itself.

The sender follows the [PostHog batch API](https://posthog.com/docs/api/capture), sends
`$process_person_profile: false` for anonymous events and `$geoip_disable: true` to
disable GeoIP enrichment. It never sends identify/group/alias events. See PostHog's
[anonymous event documentation](https://posthog.com/docs/data/anonymous-vs-identified-events)
and [server-side GeoIP control](https://posthog.com/docs/libraries/node).
The configured receiver necessarily sees the network request; transport anonymity
is not promised.
