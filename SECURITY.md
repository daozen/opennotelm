# Security policy

[简体中文](SECURITY.zh-CN.md)

OpenNoteLM is currently a **single-user, trusted-device/self-hosted application**.
It has no built-in login, authorization, tenant isolation, or secure public sharing.
Do not expose the app directly to the public internet. The default Compose binding
is loopback. Anyone who can access your instance can access its documents and
settings; an allowed Host value is not authentication.

## Reporting vulnerabilities

Use [GitHub private vulnerability reporting](https://github.com/daozen/opennotelm/security/advisories/new)
when enabled. If that entry point is unavailable, open an issue titled
"Request a private security contact" **without exploit details or sensitive data**;
the maintainer will arrange a private channel. Never put API keys, source documents,
database dumps, prompts, raw model responses, or private URLs in a public issue.

Include the version/commit, deployment type, affected component, impact and minimal
reproduction using synthetic data. Coordinate disclosure after a fix is available.
Reports are handled on a best-effort basis; there is no guaranteed response SLA.

## Supported versions

OpenNoteLM is a Beta application. Security fixes target the latest
published Beta; older snapshots have no promised backports. Release status is in
[CHANGELOG](CHANGELOG.md) and [GitHub Releases](https://github.com/daozen/opennotelm/releases).
Update only after backing up the complete data directory and encryption key.

## Boundaries and operator responsibilities

- Model endpoints receive relevant source text/images and user instructions.
  Configure only trusted services and check their own data policies and terms.
- Public-page imports reject private addresses, pin resolved addresses, preserve
  snapshots and do not run scripts or carry browser login cookies. They are not a
  general authenticated browser scraper.
- Documents and model output are untrusted input. Never use imported text as
  system instructions or execute attachments. Keep parser dependencies updated.
- Protect the data directory and backups, including its encryption master key.
  Local key encryption is not protection from someone who can read the whole disk.
- One process owns one data directory. Do not run multiple Uvicorn workers against it.
- Anonymous statistics are off by default. Diagnostic downloads are not automatic
  support uploads. See [privacy](docs/PRIVACY.md).

These boundaries do not constitute a completed independent penetration test.
