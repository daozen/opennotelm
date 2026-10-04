# Contributing to OpenNoteLM

[简体中文](CONTRIBUTING.zh-CN.md)

Bug reports, documentation, translations and focused code contributions are welcome.
Discuss substantial scope changes in an issue before implementing them. Use the
[issue templates](https://github.com/daozen/opennotelm/issues/new/choose), synthetic
examples and safe error codes. Security reports follow [SECURITY](SECURITY.md).
All project spaces follow our [code of conduct](CODE_OF_CONDUCT.md).

## License and sign-off

Contributions are accepted under MIT; authors retain copyright. Each contribution
commit should carry a [Developer Certificate of Origin 1.1](https://developercertificate.org/)
sign-off confirming that you have the right to submit it:

```sh
git commit -s -m "fix: explain the concrete change"
```

The footer is `Signed-off-by: Your Name <your-email>`. Use an identity/email you are
comfortable putting in a public Git history. A sign-off is a rights certification,
not a copyright transfer. No CLA is currently required. Dependency-bot-only commits
are exempt; maintainers still review license changes. See [licensing](docs/LICENSING.md).

## Development setup

Use Python 3.12, uv and Node.js 24. Fork/clone the repository, inspect Git state and
use a focused branch. Coding agents use `codex/` for new task branches.

```sh
uv sync --locked
uv run playwright install chromium
```

In `frontend/`:

```sh
npm ci
npm run build
```

From the repository root, start an **isolated** development instance:

```sh
task_data_dir=$(mktemp -d)
DATA_DIR="$task_data_dir" uv run uvicorn opennotelm.main:app \
  --app-dir backend --host 127.0.0.1 --port 4304 --no-access-log
```

Open http://127.0.0.1:4304. For UI hot reload, in another terminal under `frontend/`:

```sh
OPENNOTELM_API_PROXY=http://127.0.0.1:4304 npm run dev -- --port 5174 --strictPort
```

Do not run another process against a real user's `data/` directory. Do not use real
documents or paid providers for automated tests. Synthetic model fixtures are in
`backend/tests/`; frontend acceptance starts its own test service.

## Validation

```sh
uv run ruff check .
uv run ruff format --check .
uv run pytest -q
git diff --check
```

In `frontend/`:

```sh
npm test
npm run build
npm run format:check
npx playwright install chromium
npm run test:e2e
```

Linux browser/PDF checks need browser system libraries, Poppler and Noto fonts.
On macOS, run real browser tests in a terminal/test command allowed to start local
listeners and browsers; first run `uv run python tools/browser_check.py`. Stop if
preflight fails rather than repeatedly launching a personal browser. In a restricted
environment use `pytest -m 'not browser'`, then complete the browser checks separately.

Packaging changes require `bash tools/docker_acceptance.sh`. It uses isolated data
and port 4303; do not overlap native and Docker tests sharing the same output folder.
Report actual skips and limitations. Mocks verify contracts, not real-model content
or image accuracy.

## What makes a good pull request

- Explain the concrete problem, resulting behavior and relevant verification.
- Preserve original documents, ContentBlock IDs, exact citation offsets and old
  artifact signatures. Keep successful checkpoints during retries and cancellation.
- Add meaningful regression coverage for behavior, security or data integrity.
- Add ordered migrations; never edit an already-applied migration. Keep lockfiles current.
- Keep all **12** UI catalogs and interpolation parameters aligned; preserve drafts.
- Do not log or commit sources, keys, raw prompts/responses, databases or private URLs.
- Update PRD/design/change matrix for behavior changes, and acceptance evidence for
  tests. Preserve historical decisions with explicit supersession notes.

New Decks use complete image pages; saved native Decks remain compatible. Source
text and model output are untrusted data. One process owns a data directory; the
bounded task scheduler provides concurrency. Do not add server workers, cloud
accounts, agents or PPTX as incidental scope expansion.

Architecture and coding-agent work start with [HANDOFF](docs/HANDOFF.md),
[current PRD](docs/PRD.md), [design](docs/SYSTEM_DESIGN.md),
[requirements changes](docs/REQUIREMENTS_CHANGES.md) and [AGENTS](AGENTS.md).
Maintainers review scope, provenance, recovery, licenses and test evidence before
merging; a green check alone is not automatic approval. Support is best effort.
