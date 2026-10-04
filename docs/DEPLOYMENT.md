# Installation, upgrades and recovery

[简体中文](DEPLOYMENT.zh-CN.md)

## Build the current source

Install Docker with Compose. Clone the official repository, copy `.env.example`
to `.env`, and run `docker compose up -d --build` from its root. Open
http://localhost:3000 and complete model setup. `docker compose logs --tail 100 app`
and `docker compose ps` help check startup; redact anything private before sharing.

The image bundles Chromium and Noto fonts; no separate database or Redis is needed.
The app runs as a non-root user. The init service only sets ownership of the mounted
data directory itself. If restored files have different ownership, fix them for
UID/GID 10001 before startup rather than making the whole tree world-writable.

For native development see [CONTRIBUTING](../CONTRIBUTING.md); it is not a packaged
desktop installer. macOS can use Docker Desktop or an already configured Colima
runtime. Test-runtime details are in [Docker acceptance](https://github.com/daozen/opennotelm/blob/main/docs/README.md).
Current cryptography wheels no longer cover Intel macOS; native installation there
may need upstream build prerequisites. Docker's Linux amd64 image is the preferred
path on those machines. Platform availability is not a guarantee of completed testing.

## Published images

**This option only works after the corresponding version is published and its GHCR
package is public.** The release workflow prepares Linux amd64/arm64 images and
records the digest in the draft release. Source-build installation remains available.

Set an explicit version in `.env`, for example:

```dotenv
OPENNOTELM_IMAGE=ghcr.io/daozen/opennotelm:0.1.0-beta.1
```

Then run:

```sh
docker compose pull
docker compose up -d --no-build
```

For stronger reproducibility use `ghcr.io/daozen/opennotelm@sha256:<published-digest>`.
Do not rely on an unversioned `latest` tag for upgrades. Release download assets
include source, checksums, dependency notices/inventory and this Compose setup.

## Configuration and trusted-network access

`.env.example` lists safe defaults. Configure models in the UI; optional server-side
API-key environment variables are supported. UI-saved concurrency values take
precedence over initial environment defaults. `.env` is read by Compose, not
automatically by native Uvicorn; native processes require exported variables.

The default bind address is `127.0.0.1`. To allow a **trusted LAN**, set a specific
reachable local bind address and add that host/address to `ALLOWED_HOSTS`. Restrict
access at the operating-system/network level. There is no app login or authorization;
every reachable client can access your data and settings. Allowed Hosts is not an
access-control mechanism. Do not forward the port onto the public internet.

Container `localhost` cannot reach a model running on the host. Docker Desktop
provides `host.docker.internal`; other runtimes may need a configured host gateway.
Choose an address reachable from the container and test each role in settings.

## Back up

1. Stop or finish current work deliberately. Preserve active job checkpoints;
   a deliberately stopped Deck remains stopped after restart.
2. Stop the stack using `docker compose down` (do not delete the data directory).
3. Copy the **entire configured data directory**, including `secrets/`, its master
   key, database and associated files, to a protected backup location.
4. Record the source commit or image version/digest alongside the backup. Test
   restoration using a separate data directory and port, without paid model calls.

An online database-only copy is not a complete backup: source files, assets and the
encryption key must match. Losing the master key makes stored credentials unusable.
Protect backup access as carefully as access to the original data.

## Upgrade

After a complete stopped backup, switch to a reviewed source tag and rebuild, or
change the pinned image and pull. Start with `docker compose up -d --build` for source
or `docker compose up -d --no-build` for a published image. Migrations run at startup.
Check health, existing notebooks/downloads and settings before resuming stopped work.

One process owns the directory. Never point another native/container instance or
multiple Uvicorn workers at it. Keep the complete old backup until verification ends.

## Restore or roll back

Stop the new instance, preserve its current directory separately, restore the full
backup into the configured location, and start the matching old code/image version.
Check file ownership and model key availability. **Do not open an upgraded database
with older code**; restore the old database and files together. Do not delete the
instance lock file to bypass a still-running owner.

For a non-destructive restore rehearsal use a separate directory/port and local
test providers. A restored interrupted job can resume from checkpoints and send
model requests; isolate provider access unless those requests are intended.

The candidate runtime uses Python 3.12 on Debian 13/Trixie. Image security status is tracked separately in [preparation status](RELEASE_STATUS.md); a successful functional test does not clear vulnerability findings.
The Docker build uses a verified replacement for lxml's embedded XML libraries;
native `uv sync` does not apply that replacement. Default Compose drops app
capabilities and prevents privilege escalation; do not remove those controls to
work around a failed startup. See [security review](https://github.com/daozen/opennotelm/blob/main/docs/SECURITY_SUPPORT.md).
