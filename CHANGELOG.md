# Changelog

[简体中文](CHANGELOG.zh-CN.md)

Release tags and downloadable assets are listed in
[GitHub Releases](https://github.com/daozen/opennotelm/releases).
The application/package base version is `0.1.0`. Published tags and assets are
authoritative on GitHub Releases; development changes below are not a new release.

## Unreleased

- Add source-linked solo/dialogue Podcasts with approximate 5/10/20/30/60-minute
  targets, editable scripts, checkpointed speech, playback and MP3/ZIP downloads.
- Add optional OpenAI-compatible Speech/Gemini configuration and local Qwen3-TTS setup.
- New public images require an updated security and license review for FFmpeg.

## 0.1 Beta baseline

### Included

- Notebook-based reading, exact source citations, chat and reusable knowledge pages.
- Batch EPUB/PDF/DOCX/Markdown/text import, scans and illustration recognition;
  public-page snapshot import with optional original-image archiving.
- Chapter trees, combined/separate Deck generation and automatic parent-book context.
- Content-adaptive whole-page image Decks, page revision, stop/resume/delete,
  safe failure details, source manifests and source-based names.
- PDF export with lossless size optimization, renamed downloads and batch ZIPs.
- Bounded durable cross-task scheduling, per-provider/stage concurrency controls,
  checkpoint recovery and Embedding index rebuilding.
- Twelve interface/output languages, Arabic RTL and browser-derived initial language.
- Local data storage, encrypted model keys and opt-in statistics with no bundled receiver.
- MIT licensing, public contribution/security policies and versioned release tooling.
- Verified Docker rebuild of embedded XML libraries, native-component SBOM entries
  and minimum container permissions. Remaining release blockers are tracked in
  [security review](docs/SECURITY_SUPPORT.md).

### Known limitations

- Single user; no authentication, tenant isolation or safe direct public exposure.
- Model/provider quality varies; generated images can contain incorrect text or
  redrawn chart details. Review drafts and original evidence.
- New image PDFs have no selectable/searchable body-text layer. Original images
  are understood but not embedded exactly into final pages.
- Legacy `.doc`, PPTX and authenticated/script-only web capture are unsupported.
- Automated provider fixtures establish protocol/flow behavior, not real-model quality.

### Upgrade notes

Back up the complete data directory and encryption master key before upgrading.
Run one application process per directory. Migrations are automatic; rollback
requires restoring the matching full backup and old code/image. Existing sources,
citations and saved Decks are not automatically rewritten or regenerated.
