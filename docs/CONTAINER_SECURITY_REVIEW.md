# Container security review / 容器安全核查

Date / 日期: 2026-10-05. This is a release-preparation review, not a claim of
completed publication or a general security audit. / 本页记录发布准备核查，不代表已发布或
完成全面安全审计。

## Current review / 当前核查（038）

The October 5 follow-up passes the local **ARM64 supported-runtime gate**. The full
raw scan still contains **60 HIGH + 1 CRITICAL records**; none are removed. Five
records have independently verified vendor fixes: system Expat **2.8.5-2** and ACL
**2.4.0-1**, pinned to official Debian binaries for both architectures with verified
SHA-256, package identity, installed file checksums, dependency health and loaded
Expat version. The corresponding original sources/packaging/notices are retained.

The remaining 56 records (18 advisories) have explicit applicability records for the
supported server configuration in `tools/container_runtime_review.json`. This is
the project's analysis of the application and verified runtime; it is **not a vendor
claim that those system libraries are fixed or generally unaffected**.

| Component | Current classification and required evidence |
| --- | --- |
| util-linux (4 advisories) | Affected mount/nsenter tools removed; no root/capability/privileged mount caller, no fstab authorization; initializer only chowns the directory inode. |
| ACL (1), Expat (4) | Actual fixed vendor packages and runtime/file verification; only the five exact advisory/package/version records are recognized. |
| CUPS, systemd, Perl | Required cupsd/lp, systemd-homed and Archive::Tar components are absent. Client-library presence is not service presence. |
| ncurses | Vulnerable infocmp executable removed; the advisory concerns its analyze_string implementation, rather than the retained terminal libraries. |
| X11/render | Malicious-X-server prerequisite absent: headless CPU rendering, no display/X authority/socket or graphics devices. |
| OS libxml2 (8) | Python bindings absent. Application XML uses fixed static lxml or CPython Expat; CPU rendering never loads OS libxml2/LLVM. Generated/escaped HTML only, disabled JavaScript and page network; source/lockfile hashes and actual browser process maps are verified. |

The gate verifies the exact policy digest, source inventory/hashes, affected package
versions, runtime UID/capabilities/no-new-privileges, component absence and real
screenshot/PDF conditions. It still rejects **every unresolved high/critical record**.
New advisories, package/source/lockfile/policy drift, missing evidence or review expiry
**2026-11-04** cannot inherit a decision. Do not simply refresh hashes to bypass review.
The result does not apply to root/privileged, custom renderer, GPU/X11/device/source-mount
deployments. GitHub checks and release architecture verification remain separate gates.

本地 **ARM64 受支持运行方式下的门禁已通过**。原始扫描仍有 60 条高危、1 条严重记录，
未删减。5 条对应系统 Expat 2.8.5-2 和 ACL 2.4.0-1 的实际厂商修复；双架构官方包
固定哈希，核对身份、实际文件、依赖与加载版本，并保留源码/打包文件/许可。

其余 56 条（18 个漏洞）按准确版本逐项核对当前服务的触发条件：受影响的服务/模块/
管理工具缺失，非特权且没有挂载授权；Linux 仅 CPU 绘制，无图形设备或 X11；资料
使用已修复解析器，旧系统 XML/LLVM 库不进入这条渲染路径，原文脚本/HTML 不执行。
这是项目结合代码和实际探针的适用性分析，不是厂商宣布系统库已修复或普遍无影响。

源代码/锁文件哈希、策略摘要、包版本、权限、组件缺失及真实截图/PDF进程条件均核验。
未解决项仍失败，新漏洞、版本/代码漂移、证据缺失或 2026-11-04 复核到期不能继承。
不能仅刷新哈希绕过核查；特权、图形设备、X11、自定义渲染/代码挂载等部署不沿用
本结论。云端检查和发布架构需单独完成。细节见 [038](decisions/038-hosted-beta-checks-and-vendor-fixes.md)。

## Stage 53 historical checkpoint / Stage 53 历史检查点

The following describes the earlier candidate before decision 038 and is retained
as historical context. Its unresolved statuses are superseded by the current review
above for the exact verified configuration only. / 以下为 038 前候选镜像的历史记录，
仅在上方准确核查的配置和记录范围内由当前结论取代。

## English

### Implemented correction

The locked latest stable `lxml 6.1.3` wheel actually loaded **libxml2 2.14.6**.
Python package audits did not report that embedded native version. Upstream
[libxml2 2.15.4](https://download.gnome.org/sources/libxml2/2.15/libxml2-2.15.4.news)
contains the relevant native fixes; see the Debian records for
[CVE-2026-86138](https://security-tracker.debian.org/tracker/CVE-2026-86138) and
[CVE-2026-86144](https://security-tracker.debian.org/tracker/CVE-2026-86144).

The Docker build now compiles the **same locked lxml source** against pinned,
SHA-256-verified libxml2 **2.15.4** and libxslt **1.1.45** in a disposable stage.
The resulting wheel is installed after the final dependency sync. Compilers and
build dependencies are not copied to the runtime stage. Build and scan commands
check both compiled and loaded versions; the separate native report retains source
URLs/hashes. Full copyright texts, including libexslt, remain in the image; release
assets also include the unmodified native sources and notices.

This correction applies to the **rebuilt Docker image**. A native `uv sync` still
installs upstream wheels; it does not inherit this replacement. The existing local
application environment has not been changed. Installing Python dependencies alone
does not prove native-library security.

Compose additionally drops all application capabilities and sets
`no-new-privileges`. The one-shot root initializer retains only `CHOWN` to set
ownership of the mounted directory itself. These controls supplement fixes; they
are not blanket grounds for suppressing advisories.

### Remaining system-library findings

The refreshed full scan still reports **60 HIGH + 1 CRITICAL package/advisory entries,
23 distinct CVEs**. Several binary packages share an advisory. The system libxml2
package is distinct from the rebuilt lxml library; it remains a dependency of LLVM/
Mesa. Fontconfig/Mesa also retain system Expat. Removing libraries required by
Chromium merely to reduce findings is not a validated solution.

| Component | Advisory IDs | Verified facts and remaining work |
| --- | --- | --- |
| util-linux | CVE-2026-76642, CVE-2026-78408, CVE-2026-78409, CVE-2026-78410 | Mount/namespace or privileged-helper paths. Application capabilities are dropped; `nsenter` remains installed. Exact affected-path review is still required. |
| acl | CVE-2026-54369 | `setfacl` is absent; the application uses `chmod`, not the pathname ACL setter. The installed library record remains unresolved by the gate. |
| cups | CVE-2026-34980 | Only the client library is installed; `cupsd`, `cups-browsed` and `lp` are absent. The described printing-server/queue path is absent in this candidate. |
| Expat | CVE-2026-66046, CVE-2026-76956, CVE-2026-76957, CVE-2026-93990 | CPython uses its own Expat 2.8.5; the OS library is 2.8.3 and retained by graphics/font dependencies. Those consumers need separate assessment. |
| ncurses | CVE-2025-69720 | The affected `infocmp` utility remains installed. No application call was found, but absence of an application call is not an upstream package fix. |
| systemd | CVE-2026-16742 | The affected `systemd-homed` service is absent; installed systemd/udev client libraries do not establish that this service is present. |
| X11/render | CVE-2026-88806, CVE-2026-88807 | Described attacks require a malicious X server. Application rendering is headless, default Compose exposes no X socket, and DISPLAY is unset; the libraries remain installed. |
| libxml2 | CVE-2026-6653, CVE-2026-74860, CVE-2026-86138, CVE-2026-86139, CVE-2026-86140, CVE-2026-86142, CVE-2026-86143, CVE-2026-86144 | Actual application lxml now uses 2.15.4. OS package reports a reverted 2.9.14; OS consumers need separate reachability/patch assessment. System Python libxml2 bindings are absent. |
| Perl | CVE-2026-9538 | Perl `Archive::Tar` is absent from the candidate; the application uses Python archive readers. The described Perl module path is absent. |

Advisory descriptions and distribution statuses were checked against the
[official Debian tracker](https://security-tracker.debian.org/tracker/).
“No DSA” or “minor issue” is not evidence that a package is unaffected. Findings
are retained without a blanket ignore list; the release gate **continues to fail**.

Before release, finish the exact applicability review of remaining consumers or
use verified vendor fixes. Any future exception must name an exact advisory,
package/version, evidence, supported runtime conditions and review expiry; it must
not silently cover new versions/advisories or differently configured deployments.
GitHub CI and both release architectures are separate outstanding checks.

## 简体中文

### 已实施的修复

锁定的最新稳定版 `lxml 6.1.3` wheel 实际加载的是 **libxml2 2.14.6**，Python 包审计
没有报告这一内置底层版本。上游 libxml2 **2.15.4** 已包含相关修复，原始来源和漏洞
链接见上方英文说明。

Docker 现在在独立构建阶段，用固定版本并校验 SHA-256 的 libxml2 **2.15.4**、libxslt
**1.1.45** 重新编译**锁文件中同一版本的 lxml 源码**，在最终依赖同步后安装生成的
wheel。编译器和构建依赖不进入运行镜像。构建及扫描都检查实际编译/加载版本，原始
版权文本（包括 libexslt）保存在镜像中，发布附件包含对应原样源码、许可及来源哈希。

修复仅适用于**重新构建的 Docker 镜像**。原生 `uv sync` 仍使用上游 wheel，不会自动
获得这一替换；当前本机应用未升级。仅安装 Python 依赖不能证明底层库安全。

Compose 中应用删除全部额外系统权限，禁止通过执行程序获得新权限；一次性初始化
仅保留调整目录所有权需要的 CHOWN。它们是补充防护，不是批量忽略漏洞的理由。

### 剩余项与下一步

重新扫描仍有 **60 条高危、1 条严重包/漏洞记录，共 23 个不同漏洞**。它们是系统包
记录，同一漏洞可能对应多个包。镜像还保留 LLVM/Mesa 所需的旧系统 libxml2，以及
字体/图形组件所需的系统 Expat；与应用新编译的解析库不同，不能为了扫描数字直接
删除，否则可能破坏浏览器和 PDF 导出。

上表列出全部 23 个漏洞及候选镜像的实际事实。已确认打印服务、systemd-homed、Perl
Archive::Tar 和系统 Python libxml2 绑定不存在；挂载、X11 及其他库的运行条件仍需
逐项核对。发行版标注“不单独发安全公告”或“次要问题”不等于没有影响。

没有批量忽略或放行，安全门禁仍失败。正式发布前需要完成剩余组件的精确影响核查，
或使用经过验证的厂商补丁。如果确需例外，必须限定具体漏洞、包版本、证据、支持的
运行条件及复核期限，不能覆盖未来新漏洞或不同部署配置。GitHub CI 与双架构镜像
仍需另外验证。实际运行结果见 [ACCEPTANCE](ACCEPTANCE.md)。
