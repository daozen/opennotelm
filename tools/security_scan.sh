#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$repo_root"
output="${1:-.release-work/security}"
mkdir -p "$output"
tool_dir="$(mktemp -d)"
trap 'rm -rf "$tool_dir"' EXIT
case "$(uname -s)/$(uname -m)" in
  Darwin/arm64) platform=darwin_arm64; expected=b40ab0ae55c505963e365f271a8d3846efbc170aa17f2607f13df610a9aeb6a5 ;;
  Darwin/x86_64) platform=darwin_x64; expected=dfe101a4db2255fc85120ac7f3d25e4342c3c20cf749f2c20a18081af1952709 ;;
  Linux/x86_64) platform=linux_x64; expected=551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb ;;
  Linux/aarch64) platform=linux_arm64; expected=e4a487ee7ccd7d3a7f7ec08657610aa3606637dab924210b3aee62570fb4b080 ;;
  *) printf 'Unsupported secret-scanner platform.\n' >&2; exit 2 ;;
esac
curl --fail --silent --show-error --location \
  "https://github.com/gitleaks/gitleaks/releases/download/v8.30.1/gitleaks_8.30.1_${platform}.tar.gz" \
  --output "$tool_dir/archive.tar.gz"
actual="$(shasum -a 256 "$tool_dir/archive.tar.gz" | cut -d ' ' -f 1)"
if [[ "$actual" != "$expected" ]]; then
  printf 'Secret-scanner download checksum mismatch.\n' >&2
  exit 2
fi
tar -xzf "$tool_dir/archive.tar.gz" -C "$tool_dir" gitleaks
python3 tools/verify_secret_scan.py "$tool_dir/gitleaks"
# Reports stay local/temporary and fully redact detected values. Never upload them.
if ! "$tool_dir/gitleaks" git . --config "$repo_root/.gitleaks.toml" \
  --log-opts='--all --full-history' --redact=100 \
  --report-format json --report-path "$output/history.json" > "$output/history.log" 2>&1; then
  printf 'Secret scan failed in Git history. Inspect the local redacted report; no values are logged.\n' >&2
  exit 1
fi
# Scan only Git-visible public files. Never traverse ignored production data,
# private verification reports, .env or generated artifacts in the working tree.
mkdir -p "$tool_dir/public-tree"
while IFS= read -r -d '' file; do
  [[ -f "$file" ]] || continue
  [[ ! -L "$file" ]] || { printf 'Refusing symlink.\n' >&2; exit 2; }
  case "$file" in
    data/*|*/data/*|.local-services/*|*/.local-services/*|.release-work/*|*/.release-work/*|.venv/*|*/.venv/*|node_modules/*|*/node_modules/*|dist/*|*/dist/*|.e2e-data*|*/.e2e-data*|.docker-acceptance-data*|*/.docker-acceptance-data*)
      printf 'Refusing private file.\n' >&2; exit 2 ;;
    .env|.env.*|*/.env|*/.env.*)
      [[ "$(basename "$file")" = .env.example ]] || { printf 'Refusing private file.\n' >&2; exit 2; } ;;
  esac
  mkdir -p "$tool_dir/public-tree/$(dirname "$file")"
  cp "$file" "$tool_dir/public-tree/$file"
done < <(git ls-files -z --cached --others --exclude-standard)
if ! "$tool_dir/gitleaks" dir "$tool_dir/public-tree" --config "$repo_root/.gitleaks.toml" \
  --redact=100 --report-format json \
  --report-path "$output/tree.json" > "$output/tree.log" 2>&1; then
  printf 'Secret scan failed in current files. Inspect the local redacted report; no values are logged.\n' >&2
  exit 1
fi
printf 'Secret scan passed for Git history and current files. Reports retained locally.\n'
