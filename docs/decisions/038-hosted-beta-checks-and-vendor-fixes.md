# 038 — Hosted Beta checks and pinned vendor fixes

Date: 2026-10-05. Status: implemented; publication gates still apply.
Extends [036](036-public-mit-beta-release.md) and
[037](037-native-xml-release-hardening.md). The exact verified fixes and supported-runtime
applicability rules below supersede unconditional treatment of those scanner records.

## Context / 背景

Package audits cannot establish the security of embedded native libraries or OS
runtime paths. Release gates must assess the exact image and preserve unresolved
findings, with narrowly scoped evidence rather than blanket scanner ignores.

包审计不能证明内置底层库或系统运行链路安全。发布门禁必须检查准确镜像并保留未解决
记录，以限定范围的证据判定，不能批量忽略扫描结果。

## Decisions / 决策

- Preserve the original public LICENSE commit and import a reviewed source tree;
  never push private development ancestors. Use a reviewed pull request as the publication boundary.
- Hosted backend, frontend and Docker jobs run independently. A failed backend
  test must not hide frontend or container results. All jobs remain required by the
  reusable release checks.
- Shared test polling retains a monotonic deadline, increased from 5 to 30 seconds
  for synthetic image/PDF work on slower hosted runners. Short explicit deadlines
  remain available. No application timeout, retry or validation is relaxed.
- The Docker build installs only SHA-256-pinned official Debian `libexpat1 2.8.5-2`
  and `libacl1 2.4.0-1` binaries for amd64/arm64. Hashes were checked against Debian
  signed package indexes. No unstable repository is added to the runtime. Package
  identities, dependency health, installed file checksums and loaded Expat version
  are checked. These are specific reviewed vendor fixes, not a general distribution
  upgrade. Replacements retain their original notices and source-package archives.
- Trivy still labels these new versions affected using Debian 13's unfixed source
  records. A separate review recognizes only CVE-2026-54369 (ACL) and
  CVE-2026-66046/76956/76957/93990 (Expat), for the exact installed package versions
  with successful independent runtime verification. Official evidence is linked
  per record. Review expires **2026-11-04**; drift, other ecosystems, new advisories,
  expired review or missing OS scan cannot inherit an exception.
- The other 18 advisories have individual, version-specific applicability records
  in `container_runtime_review.json`. Server rendering is restricted to CPU drawing
  on Linux; mount/umount/nsenter/infocmp are removed. The probe verifies source and
  lockfile hashes, exact OS package versions, matching policy digest, UID/capabilities,
  no-new-privileges, absence of affected service/modules/tools, no mount authorization,
  no displays/devices and actual screenshot/PDF browser process maps. The old OS XML/
  LLVM library is not loaded on this path; document XML uses the independently fixed
  parsers. Rendering accepts generated/escaped HTML with JavaScript and page requests
  disabled, rather than arbitrary document HTML or XML. These records apply only to
  this exact supported server runtime, not privileged/custom/GPU/X11 deployments.
- Retain the complete raw findings and SBOM. Write `review.json` separately with
  verified fixes, conditional applicability and unresolved high/critical records.
  **Any unresolved high or critical record still fails the gate**. A new advisory,
  changed runtime code/lockfile, policy/version drift, missing evidence or expiry
  requires a fresh review. This is a narrowly checked application threat-model review,
  not a general OS security audit or a claim that all installed libraries were patched.

公开树接续原 LICENSE 提交，保留私有开发历史。各检查任务独立执行；仅测试等待
期限扩大到 30 秒，产品超时和校验不变。镜像仅安装两项准确、经过校验的厂商修复，
不加入不稳定发行版的软件源。原始漏洞报告不删改，5 项确定已修复记录单独标注，
有明确版本、实际文件/运行库核对及期限；新漏洞、其他版本不能继承。另外 18 个漏洞
逐项限定在当前受支持的服务运行方式，验证代码/锁文件哈希、包版本、策略摘要、
组件缺失、权限和真实浏览器进程条件。Linux 服务限制 CPU 绘制并移除管理工具；
不接收任意网页脚本/XML进入系统旧解析库。受支持配置之外不沿用结论。未解决项、
条件变化或证据缺失仍失败；不宣称系统库全已打补丁或完成通用安全审计。

## Compatibility / 兼容

The runtime remains one non-root process. MIT still covers
project-owned code; vendor components retain their own terms. The ACL library's LGPL
notice and corresponding original source/packaging are distributed separately.

## Verification / 验证

Use the [verification guide](../ACCEPTANCE.md) and
[container support conditions](../CONTAINER_SECURITY_REVIEW.md).
