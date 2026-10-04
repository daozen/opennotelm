#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$repo_root"
export OPENNOTELM_DATA_DIR
OPENNOTELM_DATA_DIR="$(mktemp -d "$repo_root/.docker-acceptance-data.XXXXXX")"
export OPENNOTELM_PORT=4303 OPENNOTELM_BIND_ADDRESS=127.0.0.1
export OPENNOTELM_IMAGE=opennotelm:local
export ALLOWED_HOSTS='localhost,127.0.0.1,[::1]'
stack=(docker compose -p opennotelm-acceptance -f compose.yaml -f compose.acceptance.yaml)
acceptance_python="${OPENNOTELM_ACCEPTANCE_PYTHON:-$repo_root/.venv/bin/python}"
if [[ ! -x "$acceptance_python" ]]; then
  acceptance_python=python3
fi
"$acceptance_python" -c 'import sys; assert sys.version_info >= (3, 12), "Acceptance needs Python 3.12+: run uv sync --locked or set OPENNOTELM_ACCEPTANCE_PYTHON"'

cleanup() {
  mkdir -p frontend/test-results
  "${stack[@]}" logs --no-color > frontend/test-results/container.log 2>&1 || true
  "${stack[@]}" down || true
}
trap cleanup EXIT

docker info > /dev/null
"${stack[@]}" build
"${stack[@]}" up -d --wait --wait-timeout 120
# Verify optional original-image archiving on fresh temporary data inside the image.
# The fixture uses mocked page/image/model transport and never accesses the network.
"${stack[@]}" exec -T app /app/.venv/bin/python < tools/container_web_images.py
(
  cd frontend
  # Exercise the first setup on an empty database, then every existing browser flow.
  npm run test:e2e -- --config playwright.container.config.ts e2e/skeleton.spec.ts
  npm run test:e2e -- --config playwright.container.config.ts
)
"$acceptance_python" tools/container_acceptance.py prepare
"${stack[@]}" restart app
"${stack[@]}" up -d --wait --wait-timeout 120
"$acceptance_python" tools/container_acceptance.py verify
"${stack[@]}" up -d --force-recreate --wait --wait-timeout 120
"$acceptance_python" tools/container_acceptance.py verify
"${stack[@]}" ps
printf 'Container acceptance passed. Artifacts: %s/frontend/test-results\n' "$repo_root"
printf 'Isolated data retained: %s\n' "$OPENNOTELM_DATA_DIR"
