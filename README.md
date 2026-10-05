# OpenNoteLM

[简体中文](README.zh-CN.md) · [User guide](docs/USER_GUIDE.md) · [Releases](https://github.com/daozen/opennotelm/releases) · [Contributing](CONTRIBUTING.md)

Turn books, documents and web articles into understanding—and into visual stories
you can share. OpenNoteLM is a local-first, self-hosted AI notebook with cited
answers, reusable knowledge pages and illustrated **Visual Decks**.

**Read → ask with citations → build knowledge → generate a Visual Deck → export PDF**

MIT licensed. Bring your own language, embedding and image services. No account
required. An independent project, not affiliated with Google or NotebookLM.

![English workspace in the local Demo notebook](docs/images/workspace.jpg)

## From sources to Visual Decks

Choose a whole document or select chapters in a directory tree. Generate one
combined Deck, or a separate Deck for each source or chapter. A chapter automatically
uses its uploaded parent book as background, so interpretation has the bigger picture.

- **Content-led visual design.** The model proposes a visual direction from the
  subject and your instructions, rather than choosing from a fixed theme catalog.
  A whole-Deck art plan varies diagrams, comparisons, timelines and scenes while
  keeping a coherent visual language.
- **Integrated image and text.** The image model creates a complete page with both
  artwork and typography. Saved text drafts and source references stay available
  for review. Original document images inform understanding and relevant page writing.
- **Interpretation you can guide.** Specify audience, depth, output language and
  visual style. Ask for accessible explanations, analogies or background knowledge;
  supporting source passages remain distinct from added interpretation.
- **Revise without starting over.** Edit text or ask AI to revise a page, regenerate
  its visual, reorder/delete pages, or create a rewritten/restyled copy. Review the
  exact sources and chapters used by a Deck.
- **Stay in control.** Stop/resume queued or running generation, retain successful
  pages on failure and inspect failure details. Tune bounded content, recognition
  and image concurrency in Model settings.
- **Share the result.** Rename Decks, use source/chapter names, download PDFs with
  the Deck title, or batch-download current PDFs as a ZIP. PDF optimization preserves
  page pixels and resolution.

![Visual Deck preview with page navigation and editing controls](docs/images/deck.jpg)

*Screenshots use the local Demo notebook with the English interface. AI-generated
pages are examples; text and chart details should be checked against the saved draft
and original source.*

## A notebook for the whole reading workflow

- **Bring your sources:** batch EPUB, PDF, Word `.docx`, Markdown and text uploads,
  plus single or batch public URLs. Optionally archive web images; recognize scanned
  pages, illustrations and tables with a vision-capable language model.
- **Read and trace:** real chapter trees, continuous chapter/page navigation and
  answers linked to relevant original passages. Save answers into knowledge pages,
  edit them and explicitly update them as your understanding grows.
- **Use your language:** twelve interface and generation languages, Arabic RTL,
  browser-derived first-use defaults and saved preferences. Existing content stays intact.
- **Keep your workspace:** sources, snapshots, citations and artifacts remain in
  your data directory. Switch embedding services and rebuild indexes without
  reparsing documents or changing original citations.

<details>
<summary>See the source reader</summary>

![English source reader in the Demo notebook](docs/images/reader.jpg)

</details>

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

For versioned image availability, check the [release page](https://github.com/daozen/opennotelm/releases).
The command above builds from source. See [installation and upgrades](docs/DEPLOYMENT.md).

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
