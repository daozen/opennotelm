#!/usr/bin/env bash
# Scan a reviewed local/registry image; never inspect application data mounts.
set -euo pipefail
repo_root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$repo_root"
image="${1:-opennotelm:local}"
output="${2:-.release-work/container-security}"
mkdir -p "$output"
tool_dir="$(mktemp -d)"
trap 'rm -rf "$tool_dir"' EXIT
case "$(uname -s)/$(uname -m)" in
  Darwin/arm64) platform=macOS-ARM64; expected=4a77108cccf8e55c8d6823e1e759939a622277e66cd0daa3c1fc621ed69e4568 ;;
  Linux/x86_64) platform=Linux-64bit; expected=c6e65abddb348e25f10549df887045629cf28cc72453cd1c63acb717316b3f3f ;;
  Linux/aarch64) platform=Linux-ARM64; expected=a1ee9f6ffb7d112b64ff726a2a0717c21175c1114361391f4a132956751a13b3 ;;
  *) printf 'Unsupported container-scanner platform.\n' >&2; exit 2 ;;
esac
curl --fail --silent --show-error --location \
  "https://github.com/aquasecurity/trivy/releases/download/v0.75.0/trivy_0.75.0_${platform}.tar.gz" \
  --output "$tool_dir/archive.tar.gz"
test "$(shasum -a 256 "$tool_dir/archive.tar.gz" | cut -d ' ' -f 1)" = "$expected"
tar -xzf "$tool_dir/archive.tar.gz" -C "$tool_dir" trivy
export DOCKER_HOST
DOCKER_HOST="$(docker context inspect --format '{{.Endpoints.docker.Host}}')"
# pip metadata does not describe statically embedded native library versions.
# No mounts, network or elevated permissions; this never opens user data.
docker run --rm --network none --cap-drop ALL --security-opt no-new-privileges:true \
  --entrypoint /app/.venv/bin/python "$image" \
  /app/tools/check_xml_runtime.py --json > "$output/native-xml.json"
docker run --rm --network none --cap-drop ALL --security-opt no-new-privileges:true \
  --entrypoint /app/.venv/bin/python "$image" \
  /app/tools/install_debian_security.py --check > "$output/debian-security.json"
docker run --rm --network none --cap-drop ALL --security-opt no-new-privileges:true \
  --entrypoint /app/.venv/bin/python "$image" \
  /app/tools/probe_security_runtime.py > "$output/applicability.json"
docker run --rm --network none --cap-drop ALL --security-opt no-new-privileges:true \
  --entrypoint /app/.venv/bin/python "$image" \
  /app/tools/check_audio_runtime.py --json > "$output/native-audio.json"
# Keep all severity findings; do not suppress unfixed findings or scan secrets.
"$tool_dir/trivy" image --cache-dir "$output/cache" --timeout 15m --scanners vuln \
  --format json --output "$output/vulnerabilities.json" "$image"
"$tool_dir/trivy" image --cache-dir "$output/cache" --timeout 15m --scanners vuln \
  --skip-db-update --format cyclonedx --output "$output/sbom.raw.cdx.json" "$image"
python3 tools/native_xml_sbom.py --sbom "$output/sbom.raw.cdx.json" \
  --native "$output/native-xml.json" --audio "$output/native-audio.json" --output "$output/sbom.cdx.json"
python3 tools/review_container_findings.py --scan "$output/vulnerabilities.json" \
  --runtime "$output/debian-security.json" --output "$output/review.json" \
  --applicability "$output/applicability.json" --policy tools/container_runtime_review.json
