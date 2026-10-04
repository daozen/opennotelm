# First Beta preparation status / 首个 Beta 准备状态

Target / 目标：`daozen/opennotelm`, MIT, proposed tag / 候选标签 `v0.1.0-beta.1`.
The reviewed source is uploaded to [PR 1](https://github.com/daozen/opennotelm/pull/1).
No versioned Beta Release has been published. / 公开源码已上传至 PR 1，尚未发布版本化 Beta。

## English

Completed locally:

- English/Chinese README, installation/backup, user guide, contribution/DCO, security,
  privacy, commercial-use explanation, roadmap, changelog and first-Beta release notes.
- Synthetic examples and real bilingual UI captures, dependency inventory and notices.
- Read-only pinned CI, private-file/secret/version/license guards, dependency checks,
  isolated installation tests and a manual workflow that creates a draft prerelease.
- Backend 533 and frontend 110 tests, native 33 browser flows and the first container's
  fresh setup plus 33 flows and restart/recreate persistence checks passed.
- Cryptography security update and old/new Fernet compatibility passed; Python/npm
  package audits and secret scans passed. Container scans are separate.
- Final Debian 13 image also passed fresh setup, all 33 flows and restart/recreate
  persistence checks; complete browser credits/terms are retained. Its security gate
  failed as expected on unresolved OS records, with a full SBOM generated.
- October 5 correction: Docker rebuilds locked lxml against verified libxml2 2.15.4
  and libxslt 1.1.45, checks actual native versions and preserves original-source
  notices. App capabilities are dropped; the initializer retains only CHOWN.
  Another complete 33-flow container run and restart/recreate checks passed.
  [Security review](CONTAINER_SECURITY_REVIEW.md) distinguishes these changes from
  the remaining OS findings; native installations are not automatically patched.
- October 5 follow-up: pinned Debian Expat/ACL fixes, CPU server rendering and removal
  of unused administrative tools. The ARM64 gate preserves all 60 HIGH + 1 CRITICAL
  raw records, independently verifies 5 fixes and verifies supported-runtime conditions
  for 56 records; unresolved count is zero for this exact configuration. Review expires
  November 4; this is not a general patched-OS claim. See decision 038.
- The public Git tree was uploaded through the connected GitHub application and
  matched the reviewed snapshot. Public commit `03bd858` has only the original
  LICENSE commit as parent, with a verified matching DCO footer.
- Actual initial [GitHub run](https://github.com/daozen/opennotelm/actions/runs/37235053270):
  release contract, secrets, DCO and Python audit passed; backend had 536 passes and
  3 bounded-wait failures. The shared test deadline was corrected and 54 affected
  generation tests plus 42 release/security checks passed locally. Follow-up cloud
  jobs are independent; local tests do not substitute for their actual results.

Before publishing:

1. Complete actual follow-up GitHub checks and verify release images on both
   architectures. The scoped ARM64 security gate passes; preserve the raw report
   and verify the same conditions on amd64. Do not bypass drift/expiry/new findings.
2. Review and merge the updated `codex/public-beta` PR only after checks pass;
   retain private development history locally. Do not push private branches.
3. Enable the repository settings listed in [RELEASING](RELEASING.md). The available
   browser was signed out and the connector could inspect, but not apply, those settings.
   Native Git login remains unavailable, but the connected app successfully uploaded
   the reviewed source. That app does not expose repository settings/release operations.
4. Run actual GitHub checks, verify both image architectures, package visibility and
   anonymous pulls, then review the bilingual draft/assets/checksums and publish deliberately.

Source has been uploaded; no public tag, image push or GitHub Release has been performed. No live
user-data tests, model calls, application upgrade or production restart were involved.
Mock tests do not prove real-model content accuracy or native-speaker translation review.

## 简体中文

本地已完成：

- 中英文 README、安装/备份、使用指南、贡献/DCO、安全、隐私、商业使用说明、
  路线图、变更日志与首个 Beta 发布文案。
- 自编示例、真实双语界面截图、依赖清单和许可声明。
- 只读且固定版本的 CI，私有文件/密钥/版本/许可检查，依赖审计、隔离安装验收，
  以及仅创建草稿预发布的手动工作流。
- 后端 533 项、前端 110 项、原生浏览器 33 项，以及首轮容器首次设置、33 项流程、
  重启/重建持久性检查通过。
- Cryptography 安全升级及旧/新版本 Fernet 兼容验证通过；Python/npm 依赖和密钥
  审计通过，容器漏洞扫描单独记录。
- 最终 Debian 13 镜像也通过首次设置、33 项流程及重启/重建持久性检查，完整浏览器
  许可与条款已保留；安全检查因未解决的系统库记录退出失败，完整 SBOM 已生成。
- 10 月 5 日补充：Docker 重编译锁定的 lxml，使用并核对 libxml2 2.15.4/XSLT1.1.45，
  保留来源、许可与原样源码附件；应用删除额外系统权限，初始化仅保留 CHOWN。
  再次通过完整 33 项容器流程及重启/重建检查。[安全核查](CONTAINER_SECURITY_REVIEW.md)
  区分这些修复与剩余系统包记录，原生安装不会自动获得该替换。
- 10 月 5 日续：固定 Debian Expat/ACL 修复包、CPU 服务绘制并删除不用的管理工具。
  ARM64 门禁保留全部 60 条高危、1 条严重原始记录，5 条核对实际修复，56 条核对受
  支持运行条件，准确配置下未解决项为零；11 月 4 日到期，不宣称系统库普遍已修复。
- 已通过 GitHub 连接器上传准确公开树，提交 03bd858 仅接续原 LICENSE 提交，DCO
  姓名邮箱匹配。PR 1 提供审查入口，私有开发历史未上传。
- 首轮真实云端检查：发布规范、密钥、DCO 和 Python 审计通过；后端 536 通过、3 项
  等待期限失败。已修正测试期限，本地受影响的 54 项生成测试和 42 项发布/安全检查
  通过；后续检查独立运行，本地通过不等于云端已经通过。

正式发布前：

1. 完成后续实际 GitHub 检查，并验证双架构发布镜像。准确 ARM64 配置下安全门禁
   已通过，保留原始报告，amd64 需核对同样条件；不能绕过漂移/过期/新发现。
2. 检查通过后审查并合并 `codex/public-beta` PR；私有完整历史留在本地，不推送。
3. 按[发布清单](RELEASING.zh-CN.md)开启仓库设置。当前浏览器未登录，已有连接器
   能读取仓库信息，但不能应用这些设置。
   本机 Git 登录仍不可用，但连接器已完成公开源码上传；该连接器未提供仓库设置及
   发布页面操作，仍需要浏览器登录。
4. 完成真实 GitHub 检查、双架构镜像验证、包公开性及匿名拉取检查，再审查中英文
   草稿、附件与校验值，并有意发布。

源码已上传，尚未发布公开标签、镜像或 GitHub Release。没有用真实用户资料测试、调用模型、
升级现有应用或重启生产服务。模拟测试不证明真实模型准确性或母语翻译审校已完成。
