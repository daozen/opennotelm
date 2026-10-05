# Container security support / 容器安全适用条件

## English

The supported deployment is the default Compose configuration: one non-root
application process, dropped capabilities, no-new-privileges and headless CPU
rendering. Its security gate combines raw package findings with exact vendor-fix
and runtime-applicability evidence. **This is not a claim that every installed OS
library is patched or universally unaffected.**

The build recompiles locked lxml against SHA-256-pinned libxml2 **2.15.4** and
libxslt **1.1.45**. System Expat **2.8.5-2** and ACL **2.4.0-1** use verified official
Debian packages for both release architectures. Original sources, package files and
copyright notices accompany the distribution. Native `uv sync` uses upstream wheels
and does not receive the Docker-specific replacement.

| Component | Required evidence |
|---|---|
| XML, ACL and Expat | Actual fixed binary identity, installed checksums and loaded/compiled library versions. |
| util-linux and ncurses | Affected management executables absent; no privileged mount or fstab authorization path. |
| CUPS, systemd and Perl | Affected service/module components absent; client libraries do not imply server presence. |
| X11 and graphics | No X display/socket, graphics device or GPU rendering. |
| OS XML and LLVM | Application uses fixed parsers; actual CPU browser process maps do not load the old OS libraries. Only generated/escaped HTML enters rendering; page scripts and requests are disabled. |

The full raw scanner report and SBOM are retained. Assessment is written separately;
**unresolved high/critical findings fail the gate**. Records are bound to exact
advisories, package/source/lockfile versions, policy digest and verified runtime
conditions. New findings, drift, missing evidence or review expiry **2026-11-04**
require reassessment. Updating hashes alone does not constitute a review.

Root/privileged containers, GPU/X11/device mounts, arbitrary source-code mounts and
custom renderers fall outside this assessment. Release architecture checks are
separate; consult the workflow for the actual image being installed.

## 简体中文

受支持部署采用默认 Compose：单个非 root 服务进程、删除额外权限、禁止提权、无界面的
CPU 渲染。安全门禁结合原始扫描、准确厂商修复和实际运行条件，**不宣称所有系统库均已
修复或在任意配置下都不受影响**。

镜像以固定哈希的 libxml2 **2.15.4**、libxslt **1.1.45** 重编译锁定 lxml；系统 Expat
**2.8.5-2** 和 ACL **2.4.0-1** 采用双架构已核对的官方 Debian 包，保留对应源码、打包
文件和版权声明。原生 `uv sync` 使用上游 wheel，不获得这项 Docker 专用替换。

检查实际二进制、文件校验值、加载版本、权限及受影响组件是否存在；Linux 使用 CPU
绘制，无 X11 和图形设备。资料由已修复的解析器处理，实际浏览器进程不加载旧系统 XML
和 LLVM 库；渲染仅接受生成或转义后的 HTML，不执行源网页脚本或请求。

完整扫描和 SBOM 保留，适用性评估另存；**未解决高危或严重问题仍会阻止发布**。
结论绑定准确漏洞、包/代码/锁文件、策略及运行条件。新漏洞、配置变化、证据缺失或
**2026-11-04** 复核到期必须重新评估，不能仅重算哈希放行。特权、GPU/X11、设备或任意
代码挂载、自定义渲染器不沿用结论；发布架构需单独验证。

## Policy and tooling / 策略与工具

The Deck-language change in [039](decisions/039-deck-output-language.md) only affects
model instructions, validated language codes and explicit output-language propagation. It adds no parser, package, executable, privilege, device or rendering
path; the existing advisory conditions and expiry remain unchanged. Updated source
signatures require fresh runtime probes and an image scan before release.

[039](decisions/039-deck-output-language.md)仅调整模型语言指令、语言代码白名单及各阶段的语言传递，不新增解析器、依赖、权限或渲染路径。原漏洞适用条件和
复核期限保留；更新源码签名后仍须重新执行实际运行探针和镜像扫描才能发布。

- [Vendor package pins / 厂商包配置](../tools/debian_security_packages.json)
- [Runtime applicability policy / 运行适用性策略](../tools/container_runtime_review.json)
- [Runtime probe / 实际运行探针](../tools/probe_security_runtime.py)
- [Finding assessment / 扫描结果评估](../tools/review_container_findings.py)
- [Security checks / 安全检查](../tools/security_scan.sh)
- [Design decision / 设计决策](decisions/038-hosted-beta-checks-and-vendor-fixes.md)
