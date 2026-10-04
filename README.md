# OpenNoteLM

[简体中文](README.zh-CN.md) · [User guide](docs/USER_GUIDE.md) · [Releases](https://github.com/daozen/opennotelm/releases) · [Contributing](CONTRIBUTING.md)

A local-first, self-hosted AI workspace for reading, asking questions, building
knowledge, and turning your sources into illustrated Visual Decks.

**Your sources → cited answers → reusable knowledge → Visual Deck → PDF**

OpenNoteLM is preparing its first public **0.1 Beta**. It is an independent MIT
project, not affiliated with Google or NotebookLM. Bring your own model services;
there is no account requirement or bundled paid API key.
See the [bilingual preparation status](docs/RELEASE_STATUS.md) for actual checks and unresolved items.

![OpenNoteLM workspace with synthetic demonstration material](https://github.com/daozen/opennotelm/blob/main/docs/images/workspace.jpg)

*Interface demonstration using self-written material and deterministic test models.
This screenshot demonstrates the UI, not real-model answer or image quality.*

## What you can do

- Import multiple EPUB, PDF, Word `.docx`, Markdown and text files, or public web URLs.
  Optionally save web article images; recognize scans and illustrations with a
  vision-capable language model.
- Read real chapter trees, move between chapters, and ask questions with links to
  the original passages. Save and update source-grounded knowledge pages.
- Generate one combined Deck or separate Decks for selected sources/chapters.
  Chapter Decks automatically use the uploaded parent book as background.
- Let content and your instructions guide the visual style. New Decks generate
  complete image pages, with editable text drafts and provenance kept in the app.
- Stop/resume generation, inspect safe failure details, rename Decks, revise pages,
  export PDFs and batch-download current PDFs as a ZIP.
- Use 12 interface and output languages, including Arabic RTL. First use follows
  your browser's language preferences; saved choices take precedence.

## Quick start: Docker

Install Docker with Compose, then:

```sh
git clone https://github.com/daozen/opennotelm.git
cd opennotelm
cp .env.example .env
docker compose up -d --build
```

Open **http://localhost:3000**. In Model settings, configure and test:

| Role | Required capability | Used for |
|---|---|---|
| Language | OpenAI-compatible chat and structured JSON; vision for scans/images | Answers, interpretation, OCR, Deck text |
| Embedding | Embeddings with a consistent vector dimension | Retrieval and index rebuilding |
| Image | Compatible image-generation endpoint | Whole-page Visual Deck images |

These roles can use different services. API compatibility alone does not guarantee
vision, structured-output quality, or readable image text. Capability tests may
incur charges. Model setup and troubleshooting are in the [user guide](docs/USER_GUIDE.md).

Inside Docker, `localhost` means the container. For a service on your computer use
its reachable host address, such as `http://host.docker.internal:11434/v1` on Docker
Desktop. Never publish credentials in issues or screenshots.

Versioned prebuilt images will be available after the corresponding release is
published. Until then, build from source. See [installation and upgrades](docs/DEPLOYMENT.md).

## Data, privacy and limitations

- Sources and artifacts are stored in your local `data/` directory. **AI requests
  send relevant content to the model services you configure.** Fully offline use
  requires local model services. Statistics are off by default; no project-owned
  receiver or analytics key is bundled. See [privacy](docs/PRIVACY.md).
- This is a **single-user application with no built-in authentication**. The
  default port binding is local-only. Do not expose it directly to the internet.
  See [security](SECURITY.md).
- Generated image pages can contain incorrect text or redrawn chart details.
  Check the saved draft and original evidence. Default image PDFs do not yet have
  searchable/selectable body text; original figures are understood but not embedded
  exactly in final pages.
- Legacy `.doc`, PPTX export, login-protected/script-only web pages, multi-user
  hosting and guaranteed model quality are outside the current release scope.
- Back up **the complete data directory, including its encryption master key**.
  One process owns one data directory; do not use multiple server workers.

## Develop and contribute

Python 3.12, [uv](https://docs.astral.sh/uv/) and Node.js 24 are the supported development
toolchain. Setup, meaningful tests and contribution sign-offs are documented in
[CONTRIBUTING](CONTRIBUTING.md). Architecture and coding-agent handoff start at the
[documentation index](https://github.com/daozen/opennotelm/blob/main/docs/README.md).

Bug reports and provider compatibility reports are welcome via
[Issues](https://github.com/daozen/opennotelm/issues). Use synthetic examples and
review diagnostics before sharing. Please follow the [code of conduct](CODE_OF_CONDUCT.md).
Planned work is in the [roadmap](ROADMAP.md); it does not promise delivery dates.

## License

[MIT](LICENSE): commercial use, modification and redistribution are allowed under
its terms. Dependencies retain their own licenses; see [third-party notices](THIRD_PARTY_NOTICES.md).
Uploaded documents and generated artifacts are not automatically MIT licensed.
[Commercial use and contribution rights](docs/LICENSING.md) explain the boundaries.
