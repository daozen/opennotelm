# 发布准备与公开发布

[English](RELEASING.md)

目标仓库 https://github.com/daozen/opennotelm，采用 MIT。
首个候选标签 `v0.1.0-beta.1`，应用元数据 `0.1.0`；准备不等于发布标签、镜像或 Release。
实际验证记录在 [ACCEPTANCE](ACCEPTANCE.md)，未运行的云端 CI 不算通过。

## 公开分支与检查

本地历史含私有机器路径/操作记录，密钥扫描没有命中也不应直接推送完整历史。
首次公开代码应基于远程现有仅含 LICENSE 的 main 创建干净快照；保留完整私有历史，
不强推、不抹掉远程版权声明。公开文档已整理，历史原稿另行保留，不随发布包上传。

- 核对 MIT、依赖清单、测试素材来源及演示截图。
- 不含用户资料、生图、数据库、`.env`、密钥、提示/响应或私有验证报告。
- 执行 `uv run python tools/release_check.py --tag v0.1.0-beta.1`
  与 `bash tools/security_scan.sh`，扫描报告保留本地，不上传。
- 完成后端/前端、原生浏览器与隔离 Docker 检查，诚实记录跳过项和质量边界。
- 公开快照与已验源码逐文件核对，提交带 DCO，私有历史可恢复，不需要重写原分支。

## GitHub 所有者设置

新增文件不会自动开启以下设置，需要仓库所有者操作：

1. 开启 Issues、私密漏洞报告、可用的密钥扫描/推送保护、Dependabot 告警与安全更新。
2. 保护 main：PR 评审与 checks 检查，禁止强推/删分支；单人项目设置可实际执行的评审规则。
   当前检查名称：release-contract、test、frontend、container，发布仍要求全部通过。
3. 不信任的 fork 工作流需审批；PR 仅只读权限，不用 pull_request_target 或生产/模型密钥。
4. 配置 release environment 的所有者审批，取决于账号/仓库支持，不能认为 YAML 已开启。
5. Actions 默认只读，手动草稿任务才申请写权限；补简介、topics，验证报告入口。
6. 需要时审查期间保持 GHCR 私有，正式发布时设公开并验证匿名拉取、双架构与来源证明。

## 本地发布附件

先提交审查后的修改；脏工作区不会打包：

```sh
uv sync --locked
npm ci --ignore-scripts --prefix frontend
uv run python tools/build_release.py --tag v0.1.0-beta.1
```

输出在忽略的 `.release-work/assets/`：已提交源码包、运行依赖许可原文、经锁文件校验
的原样 certifi/tld/lxml 源码、固定哈希的 libxml2/libxslt 源码及许可、含底层组件的
锁定依赖清单、manifest、SHA256SUMS。
仅访问公开上游源码，不调用模型或读用户资料。解包后用隔离数据验证首次 Docker 启动。
两项固定的 Expat/ACL 厂商修复也保留原样 Debian 源码、打包文件和许可，不在运行镜像
加入不稳定发行版软件源。
源码清单不是完整容器 SBOM；镜像另生成每架构 SBOM/来源证明，保留浏览器/字体/系统声明。
容器漏洞扫描与 Python/npm 扫描也是独立步骤。
扫描额外核对实际内置 XML 版本，将相应组件补入 SBOM，同时保留原始 SBOM 与全部
系统包发现；当前未解决项见[中英文安全核查](CONTAINER_SECURITY_REVIEW.md)。

## 草稿与发布

公开分支审查合并、真实 GitHub CI 通过后，对确定提交创建带说明的标签；
有签名身份时使用 `git tag -s`，否则用 annotated tag，不移动已发布标签。
手动运行 prepare-release 并填标签，重新检查准确提交、生成双架构版本镜像与证明，
记录 digest，创建**草稿预发布**，不会自动公开 Release。

首发文案中英文齐全，链接自动转换为对应版本仓库 URL；在 GitHub 预览核对链接、附件、镜像。
最终下载核对校验值、分别验证架构、
开放所需镜像访问、确认安全报告和隐私默认值，再有意发布预发布版本。
不会自动开启账号、付费服务或统计。

后续版本说明包含迁移、备份/回退、安全修复和已知限制。版本与锁文件共同维护，
依赖变化时更新清单。当前仍为 MIT，不添加商业限制或 CLA；升级测试不使用真实用户数据。
依赖更新审查后运行 `uv run python tools/update_dependency_inventory.py` 刷新许可元数据，
可能需要查询公开包仓库，再核对许可差异；CI 会拒绝过期清单。

构建后执行 `bash tools/container_scan.sh`：只扫描镜像，保留全部原始记录与 CycloneDX
SBOM，另记实际修复/受支持运行条件/未解决项。未解决高危或严重项仍失败，包括无
修复项目。准确厂商修复及配置适用性需实际探针、源代码/策略哈希和准确版本核对，
2026-11-04到期，新发现/漂移不继承。报告留在本地忽略目录，不挂载用户资料。
