#!/usr/bin/env bash
# Optional local inference service; never installs Torch into the application environment.
set -euo pipefail
qwen_repo_root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$qwen_repo_root"
if [[ "$(uname -s)/$(uname -m)" != "Darwin/arm64" ]]; then
  printf 'This tested setup targets Apple Silicon macOS. See docs/QWEN_TTS.md for other hosts.\n' >&2
  exit 2
fi
qwen_runtime="$qwen_repo_root/.local-services/qwen3-tts"
mkdir -p "$qwen_runtime"
if [[ ! -x "$qwen_runtime/venv/bin/python" ]]; then
  uv venv "$qwen_runtime/venv" --python 3.12
fi
uv pip install --python "$qwen_runtime/venv/bin/python" -r tools/qwen-tts/requirements-macos-arm64.txt
"$qwen_runtime/venv/bin/python" - <<'PY'
from huggingface_hub import snapshot_download
snapshot_download(
    "Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice",
    revision="85e237c12c027371202489a0ec509ded67b5e4b5",
    local_dir=".local-services/qwen3-tts/model",
    allow_patterns=["*.json", "*.safetensors", "*.txt", "*.model", "*.tiktoken"],
    max_workers=4,
)
PY
printf 'Installed. Start with: bash tools/run_qwen_tts.sh\n'
