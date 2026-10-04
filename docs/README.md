# 文档入口

本目录分为当前契约、接手操作、验证记录和历史决策。
2026-10-03 已把后续用户要求合并到主 PRD/设计；原始 v0.1 不再作为当前功能限制。

## Public documentation / 公开使用与发布文档

- User guide / 使用指南：[English](USER_GUIDE.md) · [简体中文](USER_GUIDE.zh-CN.md)
- Deployment / 安装升级：[English](DEPLOYMENT.md) · [简体中文](DEPLOYMENT.zh-CN.md)
- Privacy / 隐私：[English](PRIVACY.md) · [简体中文](PRIVACY.zh-CN.md)
- Licensing / 许可商业使用：[English](LICENSING.md) · [简体中文](LICENSING.zh-CN.md)
- Release checklist / 发布清单：[English](RELEASING.md) · [简体中文](RELEASING.zh-CN.md)
- [Bilingual first-Beta notes / 中英文首发文案](releases/first-beta.md)
- [Preparation status / 发布准备状态](RELEASE_STATUS.md)
- [Dependency inventory / 锁定依赖清单](DEPENDENCIES.json)

## 新 coding agent 的阅读顺序

1. [HANDOFF](HANDOFF.md)：快速理解、启动隔离实例、修改入口、调试、升级/回退和完成标准。
2. [PRD](PRD.md)：当前需求与范围，含已取代的默认行为和仍未实现项。
3. [需求差异](REQUIREMENTS_CHANGES.md)：逐项对比原始 v0.1 与后续要求。
4. [SYSTEM_DESIGN](SYSTEM_DESIGN.md)：实际架构、数据、生成链路、缓存/版本/并发和 API。
5. [IMPLEMENTATION_PLAN](IMPLEMENTATION_PLAN.md)：已交付、验证到的范围及发布余项。
6. 当前任务相关的下列专题/决策，最后再查完整历史验收。

仓库级工程约束见 [AGENTS](../AGENTS.md) 和 [CONTRIBUTING](../CONTRIBUTING.md)。

## 专题与证据

- [ACCEPTANCE](ACCEPTANCE.md)：历史逐阶段记录，包含失败/限制与真实样本，不是单一当前规范。
- [DOCKER_ACCEPTANCE](DOCKER_ACCEPTANCE.md)：隔离生产镜像验收、宿主模型地址、运行环境恢复。
- [UI_REVIEW](UI_REVIEW.md)：系统界面/交互发现、改进与验证范围。
- [INTERNATIONALIZATION](INTERNATIONALIZATION.md)：界面语言保存、草稿保持和翻译维护。
- [PRIVACY](PRIVACY.md)：隐私、遥测、无正文诊断与分享边界。
- [视觉表达调研](research/deck-visual-expression.md)：公开技巧与观察，不能当作产品实现或源文证据。
- [v0.1 基线归档](archive/v0.1/README.md)：用户最初 PRD/设计的完整原文与旧阶段计划。

## 决策索引及当前适用范围

| 文档 | 主题 | 当前适用性 |
|---|---|---|
| [001](decisions/001-rendering.md) | deterministic rendering/text fidelity | 旧 native 路径保留；默认整页由 008 取代 |
| [002](decisions/002-deck-editorial-quality.md) | 解读与视觉质量 | 质量原则；解释约束结合 015 |
| [003](decisions/003-readable-source-projection.md) | PDF 可读投影 | 当前阅读契约 |
| [004](decisions/004-paragraph-citation-context.md) | 段落证据与引用 | 当前引用契约 |
| [005](decisions/005-addressable-navigation.md) | URL 导航 | 当前路由契约 |
| [006](decisions/006-reading-navigation.md) | 连续阅读与真实目录 | 当前阅读导航 |
| [007](decisions/007-integrated-page-design.md) | 集成原生页面设计 | native 兼容；默认整页由 008 取代 |
| [008](decisions/008-whole-page-image-generation.md) | 完整图文页/PDF | 当前默认；视觉/内容策略随后扩展 |
| [009](decisions/009-deck-visual-repertoire.md) | 全套表达形式 | 当前 art 编排；自适应语言结合 016 |
| [010](decisions/010-direct-content-and-concurrent-pages.md) | 元说明/生图并发/双区滚动 | 默认标签规则保留；并发范围由 011、自由解释由 015 更新 |
| [011](decisions/011-image-concurrency-model-settings.md) | 生图并发 1–20 | 当前 Image 设置 |
| [012](decisions/012-word-vision-and-chapter-scopes.md) | DOCX/识图/扫描/多章 | 当前导入；串行识别由 019 取代，分别生成由 013 扩展 |
| [013](decisions/013-separate-decks-and-chapter-tree.md) | 逐资料/章节与树 | 当前批量范围契约 |
| [014](decisions/014-deck-controls-and-preview.md) | 停止/继续/删除/预览 | 当前任务与响应式预览 |
| [015](decisions/015-user-directed-deck-interpretation.md) | 模型解释/用户优先/basis | 当前内容策略，副本 style 默认随后由 016 修正 |
| [016](decisions/016-content-adaptive-deck-style.md) | 自由自适应风格/副本 | 当前风格策略 |
| [017](decisions/017-automatic-parent-work-context.md) | 自动全书阅读 | 当前章节上下文 |
| [018](decisions/018-original-images-in-deck-reading.md) | 原图输入理解 | 当前多模态 Deck；最终不嵌图 |
| [019](decisions/019-controlled-image-recognition.md) | 受控识图并发 | 当前识别设置与 worker |
| [020](decisions/020-deck-generation-reliability.md) | 引用/修复/token/缓存/内容并发 | 当前可靠性契约 |
| [021](decisions/021-deck-art-repair-and-failure-details.md) | art 多规则修复与失败详情 | 更新 020 的作者修复协议、按 Deck 诊断范围与请求失败记录 |
| [022](decisions/022-ui-review-and-common-languages.md) | 系统UI审查与12语言 | 小屏幕分区、Modal、操作层级、RTL及完整本地翻译 |
| [023](decisions/023-batch-files-word-fix-and-web-import.md) | 多选上传/Word 修复/网页 URL | 当前网页资料、快照、公网安全/代理DNS和批量回执 |
| [024](decisions/024-optional-web-image-archive.md) | 可选网页原图保存与后台识别 | 取代023图片说明限制；正文先可用、受控识别、原图与引用保留 |
| [025](decisions/025-deck-preview-navigation.md) | 预览图左右点击与键盘翻页 | 普通/专注预览统一页选择，保留高清入口与输入/弹窗保护 |

| [036](decisions/036-public-mit-beta-release.md) | MIT 公开 Beta 准备 | 中英文发布文档、DCO、许可资产、干净公开历史与发布检查 |

更新功能时维护 PRD、设计和变更矩阵；decisions 记录为何取舍，ACCEPTANCE 记录具体验证。
归档原文不改，旧决策需保留历史并在顶部明确被取代的范围。
