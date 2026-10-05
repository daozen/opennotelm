# Docker acceptance

This check builds the production image and serves its production frontend/API.
Existing application instances and their data are not used. A temporary
`.docker-acceptance-data.*` directory and port 4303 isolate all test data.

## Runtime on Apple Silicon macOS

Apple Silicon users can run Docker Engine in [Colima](https://colima.run/docs/installation/).
Install and start it with:

```sh
brew install colima docker docker-compose docker-buildx
colima start --vm-type vz --mount-type virtiofs --cpu 4 --memory 6 --disk 40 --ssh-config=false
docker info
docker compose version
```

Homebrew's Compose and Buildx plugins require `cliPluginsExtraDirs` to include
`/opt/homebrew/lib/docker/cli-plugins` in `~/.docker/config.json`. Merge this field
with existing configuration. Docker Desktop or an existing Linux Docker Engine
can also run this acceptance stack.

## Repeatable check

The browser test driver needs the development dependencies (`uv sync --locked`
and `npm ci` in `frontend/`) and its Playwright browser installed. The deployed
application itself requires only Docker. From the repository root:

```sh
bash tools/docker_acceptance.sh
```

The script prefers `.venv/bin/python` and requires Python 3.12 or newer for the
persistence driver. Set `OPENNOTELM_ACCEPTANCE_PYTHON` to an alternative compatible
executable when running without the project virtual environment.

The check runs first setup on an empty database, then all browser flows against
the image. Before browser checks, [container_web_images.py](../tools/container_web_images.py)
uses separate temporary data and mocked transports inside the production image to
verify five raster decoders, text-only import, optional image saving, blocked private
image URLs, exact original downloads, unchanged article facts, restart/retry reuse
and source deletion. It makes no real model or remote-page requests.
The browser checks import EPUB, text PDF, fragmented PDF, Markdown, TXT, illustrated
Word (.docx) and a scanned PDF with bookmarks; verifies
grounded chat/knowledge and original citations; generates and revises a 15-page
illustrated deck; and exports its PDF. After both a process restart and complete
container recreation it compares API state, all saved source/asset/render/export/
secret file hashes, and PDF/preview download hashes. Discovery using each saved
encrypted key verifies decryption still works. The application runs as UID 10001.
Source-image previews and recognition checkpoints are included in file comparisons,
and original-image download bytes are checked after restart and recreation.
The hierarchy fixture adds nested PDF bookmarks. Two selected subchapters create
separate 10-page Decks. Batch request identities, exact chapter scopes, citations,
previews and both PDFs survive restart/recreation, and repeating the same batch
request reuses its original Deck IDs.
The Deck lifecycle browser flow stops queued and running Decks, resumes saved
pages, verifies desktop/iPad/phone focus preview, deletes through the viewer and
Studio, and preserves original sources and a sibling PDF. A retained stopped Deck is
checked after both process restart and container recreation to ensure it remains
stopped and does not automatically generate.
The model-settings browser flow saves image concurrency without a capability test;
the restart/recreation check also verifies a saved concurrency of 20 survives.

`compose.acceptance.yaml` adds only a synthetic provider/telemetry receiver on
the app container's loopback interface. It has no published port and sends no
data externally. These checks establish packaging, protocols, browser flows,
rendering and persistence; real-model design quality is recorded separately.

The script always stops its test stack. Test-only data is retained at the printed
path for inspection; screenshots, PDF, state and logs are in
`frontend/test-results/`. These directories are ignored by Git and image builds.
Do not run two acceptance scripts concurrently: they share port 4303 and the
`opennotelm-acceptance` Compose project.
Native and Docker browser runs also share the default Playwright output directory.
Run them sequentially, or give a native run its own `--output` directory; overlapping
runs can delete each other's trace files and produce false acceptance failures.

## Deployment addresses

Default deployment remains `http://localhost:3000`. An alternative port/data
directory can be supplied with `OPENNOTELM_PORT` and `OPENNOTELM_DATA_DIR`.
For trusted LAN access set `OPENNOTELM_BIND_ADDRESS=0.0.0.0` and add the machine's
LAN address to `ALLOWED_HOSTS`; both settings are passed through Compose.

Inside a container, a model service running on the Mac must use a host address
such as `http://host.docker.internal:8000/v1`, rather than `localhost`. Verify that the name resolves to your host gateway. Re-test and save the endpoint
in model settings after changing it; the existing saved key can be reused.

## Runtime troubleshooting

If the Docker daemon is unavailable, inspect its status and VM logs. Check for
other running workloads before restarting Docker or its VM. Preserve disks and
configuration; do not delete the VM to repair an acceptance failure. Re-run the
isolated acceptance procedure after restoring the runtime.
