#!/usr/bin/env bash
# Optional per-user macOS service; never installs a system daemon or exposes a LAN port.
set -euo pipefail
test "$(uname -s)" = Darwin
qwen_repo_root="$(cd "$(dirname "$0")/.." && pwd)"
qwen_runtime="$qwen_repo_root/.local-services/qwen3-tts"
test -x "$qwen_runtime/venv/bin/python"
test -d "$qwen_runtime/model"
# LaunchAgents cannot read a Documents checkout under macOS privacy controls.
# Keep only the optional runtime/model in the user's application-support directory.
qwen_service_runtime="$HOME/Library/Application Support/OpenNoteLM/Qwen3-TTS"
mkdir -p "$qwen_service_runtime/logs"
cp -cR "$qwen_runtime/venv" "$qwen_runtime/model" "$qwen_service_runtime/"
cp "$qwen_repo_root/tools/qwen_tts_server.py" "$qwen_service_runtime/server.py"
qwen_agent_dir="$HOME/Library/LaunchAgents"
qwen_agent="$qwen_agent_dir/org.opennotelm.qwen3-tts.plist"
mkdir -p "$qwen_agent_dir" "$qwen_runtime/logs"
"$qwen_service_runtime/venv/bin/python" - "$qwen_service_runtime" "$qwen_agent" <<'PY'
import plistlib
import sys
from pathlib import Path
runtime, target = map(Path, sys.argv[1:])
with target.open('wb') as stream:
    plistlib.dump({
        'Label': 'org.opennotelm.qwen3-tts',
        'ProgramArguments': [str(runtime / 'venv/bin/python'), '-u', str(runtime / 'server.py')],
        'WorkingDirectory': str(runtime),
        'EnvironmentVariables': {'PYTORCH_ENABLE_MPS_FALLBACK': '1', 'HF_HUB_OFFLINE': '1', 'QWEN_TTS_ROOT': str(runtime)},
        'RunAtLoad': True,
        'KeepAlive': {'SuccessfulExit': False},
        'ThrottleInterval': 60,
        'StandardOutPath': str(runtime / 'logs/service.log'),
        'StandardErrorPath': str(runtime / 'logs/service.log'),
    }, stream)
target.chmod(0o600)
PY
qwen_domain="gui/$(id -u)"
launchctl bootout "$qwen_domain/org.opennotelm.qwen3-tts" 2>/dev/null || true
launchctl bootstrap "$qwen_domain" "$qwen_agent"
printf 'Qwen3-TTS user service installed: http://127.0.0.1:8320/health\n'
