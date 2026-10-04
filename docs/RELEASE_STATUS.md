# First Beta preparation status / 首个 Beta 准备状态

Target / 目标：`daozen/opennotelm`, MIT, proposed tag / 候选标签 `v0.1.0-beta.1`.
Preparation is not publication. / 准备不代表已经发布。

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

Before publishing:

1. Resolve the container security gate: the updated Debian 13 candidate still has
   60 high and 1 critical package/advisory records (23 distinct advisories), without
   reported fixed versions. These are scanner records requiring applicability review,
   not all proven exploitable. No blanket suppression was applied. Findings and actual final
   image verification are recorded in [ACCEPTANCE](ACCEPTANCE.md#stage-53--native-xml-and-container-hardening-2026-10-05).
2. Review the clean `codex/public-beta` snapshot continuing the remote LICENSE-only
   main; retain the private development history locally. Do not push private branches.
3. Enable the repository settings listed in [RELEASING](RELEASING.md). The available
   browser was signed out and the connector could inspect, but not apply, those settings.
   Local HTTPS and SSH push preflights also lack usable authentication; no source was uploaded.
4. Run actual GitHub checks, verify both image architectures, package visibility and
   anonymous pulls, then review the bilingual draft/assets/checksums and publish deliberately.

No source push, public tag, image push or GitHub Release has been performed. No live
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

正式发布前：

1. 解决镜像安全检查：更新后的 Debian 13 候选仍有 60 条高危、1 条严重包/漏洞记录
   （23 个不同漏洞），未给出已修复版本。需要核查实际影响，不代表每项已证实可利用，
   没有批量忽略这些记录。发现项和最终镜像的实际验证见
   [ACCEPTANCE](ACCEPTANCE.md#stage-53--native-xml-and-container-hardening-2026-10-05)。
2. 审查基于远程仅含 LICENSE 的 main 创建的干净 `codex/public-beta` 快照；完整私有
   开发历史留在本地，不推送私有分支。
3. 按[发布清单](RELEASING.zh-CN.md)开启仓库设置。当前浏览器未登录，已有连接器
   能读取仓库信息，但不能应用这些设置。
   本机 HTTPS/SSH 模拟推送也没有可用登录身份，尚未上传源码。
4. 完成真实 GitHub 检查、双架构镜像验证、包公开性及匿名拉取检查，再审查中英文
   草稿、附件与校验值，并有意发布。

尚未推送源码、公开标签、镜像或 GitHub Release。没有用真实用户资料测试、调用模型、
升级现有应用或重启生产服务。模拟测试不证明真实模型准确性或母语翻译审校已完成。
