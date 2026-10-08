#!/usr/bin/env bash
set -euo pipefail
qwen_repo_root="$(cd "$(dirname "$0")/.." && pwd)"
qwen_runtime="$qwen_repo_root/.local-services/qwen3-tts"
test -x "$qwen_runtime/venv/bin/python"
test -d "$qwen_runtime/model"
# Optional inference libraries can create working-directory caches. Keep these isolated.
cd "$qwen_runtime"
export PYTORCH_ENABLE_MPS_FALLBACK=1 HF_HUB_OFFLINE=1
exec "$qwen_runtime/venv/bin/python" -u "$qwen_repo_root/tools/qwen_tts_server.py"
