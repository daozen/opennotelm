# 036 — Public MIT Beta preparation

Date: 2026-10-04. Accepted user requirement: keep MIT, prepare publication thoroughly,
and provide release-facing documentation in English and Chinese.

This decision adds distribution/maintenance policy, not a hosted product. It does
not supersede source/citation preservation, one data-owner process, consent rules,
existing artifact compatibility or earlier bounded concurrency decisions.

## Decisions

- Keep MIT and the existing remote copyright holder, plus contributors. Accept
  contributions under MIT with DCO; no CLA/copyright assignment or commercial restriction.
- Separate bilingual public docs and synthetic demos from private operational context.
  Preserve original v0.1 archives. Private copies/history remain recoverable but are
  excluded from the initial public snapshot, which continues the remote LICENSE-only main.
- Guard private files, local links, version/license metadata and exact locked
  dependency coverage. Secret scanning copies only Git-visible public files, never
  ignored live user data. Do not upload scanner reports.
- Preserve application/native/browser/font notices. Ship unmodified certifi/tld
  sources with lock-verified hashes and runtime license text assets.
- Pin Actions commits and use read-only CI. PR DCO checks contain no message logging.
  Manual version release depends on full checks and verifies the tagged commit;
  image builds include dual architectures and SBOM/provenance, then create a draft
  prerelease for review. No automatic publication or project analytics receiver.
- Compose can pin a published image/version/digest; source builds remain default.
  Acceptance overrides the image to a local build and retains disposable data/ports.
- Upgrade cryptography from 48.0.1 to 50.0.2 after advisory verification. The app
  uses Fernet, not the affected PKCS7/X.509 APIs; this removes known package findings
  without changing stored-key formats. Intel macOS native wheels are no longer offered
  upstream; document Docker as the preferred path. Production environment is untouched.

- Candidate runtime uses supported Debian 13/Trixie with available system updates;
  removes unused pip and Xvfb tools. Complete built-in Chromium credits/terms are
  exported inside the image. Full OS scanning retains unfixed findings and blocks
  publication on unresolved high/critical records; source audits are separate.

## Evidence and limits

See ACCEPTANCE Stage52 for actual checks. Python/npm scans are not a full container
vulnerability or legal audit. Synthetic providers are not real-model quality evidence.
GitHub settings, hosted CI and publishing are not established by writing these files.
