# 037 — Native XML verification and container permissions

2026-10-05 update: exact verified vendor fixes and supported-runtime classification
are extended by [038](038-hosted-beta-checks-and-vendor-fixes.md); raw findings remain retained.

Date: 2026-10-05. Continues decision [036](036-public-mit-beta-release.md).
This corrects the assumption that a successful Python package audit covers the
native libraries statically embedded in Python wheels. It does not relax the
container release gate or authorize publication of an unresolved candidate.

- Rebuild locked lxml 6.1.3 in a separate Linux Docker stage against SHA-256-pinned
  libxml2 2.15.4 and libxslt 1.1.45. Preserve the Python API/version and locked
  upstream source; install the replacement after the final uv sync.
- Verify compiled and runtime versions independently during build and scanning.
  Keep the native manifest beside full copyright texts and retain native source/
  notice release assets. Native `uv sync` is not silently patched by this change.
- Drop all app capabilities, enable no-new-privileges, retain only CHOWN in the
  one-shot directory initializer. Preserve UID, one owner process, file formats,
  original sources, secrets and stored artifacts.
- Retain all full-scan OS findings. Component absence, upstream fixed versions and
  conditional reachability are distinct claims; no blanket suppression or automatic
  severity downgrade. See [review](../CONTAINER_SECURITY_REVIEW.md).

Functional/security evidence is recorded in ACCEPTANCE Stage53. Existing production
services and live user data are excluded from verification and are not upgraded.
