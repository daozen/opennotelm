# Release preparation and publication

[简体中文](RELEASING.zh-CN.md)

## Repository and status

Target: https://github.com/daozen/opennotelm. License: MIT.
The first candidate is `v0.1.0-beta.2`, with application metadata `0.1.0`.
Preparation does not publish a tag, image or Release. Current evidence belongs in
[ACCEPTANCE](ACCEPTANCE.md), not in claims about cloud CI runs that have not happened.

The local development history contains private machine paths/operational context.
Keep it private even when secret scanning finds nothing. Prepare the initial public
code snapshot on top of the target's existing LICENSE-only `main` rather than pushing
the private development branch/history. Preserve the full local history separately;
do not force-push or erase the existing remote copyright statement.

## Before uploading the prepared public branch

- Review MIT notices, dependency inventory, synthetic fixture provenance and screenshots.
- Confirm the tree contains no original user documents, model artifacts, databases,
  `.env` variants, secrets, prompts/responses or private operational reports.
- Run `uv run python tools/release_check.py --tag v0.1.0-beta.2` and
  `bash tools/security_scan.sh`. Scanner reports stay local; never upload them.
- Run backend lint/format/tests, frontend tests/build/format, full native acceptance
  and isolated Docker acceptance. Report actual skips and quality limitations.
- Compare public snapshot files with the verified source. Keep a focused, signed-off
  initial commit and a recoverable local copy of private history. No rewrite is required.

## GitHub repository settings

These are owner actions, not features automatically enabled by adding files:

1. Enable Issues, private vulnerability reporting, secret scanning/push protection
   and Dependabot alerts/security updates where available.
2. Protect `main`: require reviewed PRs and the `checks` jobs; block force pushes and
   branch deletion. For a solo-maintainer repository, set review rules that remain usable.
   Current check names: `release-contract`, `test`, `frontend`, `container`.
3. Require approval for untrusted fork workflow runs. PR workflows use read-only
   permissions, no privileged `pull_request_target` and no production/model secrets.
4. Configure a `release` environment with the owner's approval before the release job.
   Approvals depend on GitHub account/repository support; do not assume the YAML sets them.
5. Keep Actions token defaults read-only; only the approved release jobs request their required writes.
6. Add the repository description/topics and check security/contact links.
7. Keep the GHCR package private during review if appropriate, then make it public
   for anonymous pulls when publishing. Verify both Linux architectures and attestations.

## Prepare assets locally

Commit reviewed changes first; no artifacts are created from a dirty tree:

```sh
uv sync --locked
npm ci --ignore-scripts --prefix frontend
uv run python tools/build_release.py --tag v0.1.0-beta.2
```

Default output is the ignored `.release-work/assets/`. It includes a committed-source
archive, copied runtime notices, original certifi/tld/lxml sources verified against lockfile
hashes, pinned libxml2/libxslt sources/notices, the locked dependency inventory with
native-container components, a manifest and SHA256SUMS. The pinned Expat/ACL replacements
additionally retain original Debian source
packages, packaging and full notices; no unstable repository is added to the image.
Creation accesses
public upstream source archives, not models or user data. Check extraction and fresh
Docker startup from the archive using isolated data. Hash-check all attachments.

The source inventory is not a complete container SBOM. The image build creates
per-platform SBOM/provenance, and retains browser/native/font/OS notices. A full
container vulnerability scan remains distinct from Python/npm dependency scans.
The scan also checks actual embedded XML versions and adds those components to its
SBOM while preserving the raw scanner SBOM and all OS findings. See the bilingual
[container security review](CONTAINER_SECURITY_REVIEW.md) for the scoped findings and conditions.

## Draft and publish

After the public branch is reviewed/merged and actual GitHub CI passes, manually run
**prepare-release** from protected `main`, supplying the release tag and exact reviewed
40-character commit SHA. It verifies main ancestry and reruns checks on that commit.
After release-environment approval, it creates or verifies the immutable annotated tag.
Native Ubuntu amd64 and arm64 runners build separate images by digest, retain
SBOM/provenance, scan each exact image and check startup with empty data. Only
verified images are combined into a versioned manifest; an existing differing image
version is never overwritten. The final job records the digest and creates a
**draft prerelease**. It does not auto-publish the Release.
已合并且检查通过后，从受保护的 main 手动运行 prepare-release，填写版本标签和
已审查提交的完整 SHA。流程复验该提交，经发布环境批准后创建不可移动的附注标签，
在两个原生架构机器分别构建、扫描和验证，再合并镜像并创建发布草稿。已有匹配标签可继续；
不覆盖现有发布、不同的镜像版本或移动标签。

The first-Beta body is bilingual, with documentation links converted to version-pinned
repository URLs; check its GitHub preview, attachments and image pulls.

Final review: download and hash-check attachments, smoke-test both platforms, make
the package accessible as intended, configure security reporting, confirm privacy
defaults and remove any unreleased claims from the release-specific announcements.
Then publish the prerelease intentionally. No paid account/service is activated.

## Ongoing maintenance

Release notes must state migrations, backup/rollback, fixed vulnerabilities and known
limitations. Update version metadata/lockfiles together; regenerate the inventory
whenever dependencies change. MIT remains the current license; no commercial-use
restriction or CLA has been added. Do not test upgrades against live user data.
After reviewing a dependency update, use `uv run python tools/update_dependency_inventory.py`
to refresh metadata (public registry requests may be needed), then review the resulting
license changes. CI rejects stale inventory entries.

After building, run `bash tools/container_scan.sh`. It scans only the image and retains
all raw findings plus a CycloneDX SBOM and a separate applicability review. Unresolved
high/critical findings fail, including unfixed entries. Exact vendor fixes and current
supported-runtime decisions require independent probes, matching source/policy hashes
and package versions, and expire on November 4, 2026. New/drifted findings do not inherit
decisions. Reports stay in the ignored local directory, without mounted user data.

Use native runners for browser/runtime probes; QEMU cross-build execution is not
a substitute for native verification. Runner mapping follows the
[GitHub runner reference](https://docs.github.com/en/actions/reference/runners/github-hosted-runners)
and the [Docker distributed-build guidance](https://docs.docker.com/build/ci/github-actions/multi-platform/).
The workflow may be updated independently of an already reviewed release target;
source archives, image labels and tags still identify that exact application commit.
