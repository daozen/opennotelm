# Delivery map / 实现范围与后续方向

Product behavior is defined in [PRD](PRD.md), architecture in
[SYSTEM_DESIGN](SYSTEM_DESIGN.md), and engineering procedures in [HANDOFF](HANDOFF.md).
This map describes capabilities rather than a development timeline.

当前行为见需求定义，架构见系统设计，工程操作见接手手册。下表按能力整理，不记录开发流水。

| Area / 能力 | Implemented / 已实现 | Boundary / 边界 |
|---|---|---|
| Sources / 资料 | Batch file/URL import, EPUB/PDF/DOCX/Markdown/TXT, scans and images, saved web snapshots. / 批量文件及 URL、扫描和插图、网页快照。 | No legacy DOC, login cookies or page scripts; Word layout is not reproduced exactly. / 不支持旧 DOC，不携带登录态或执行脚本，不完整还原 Word 排版。 |
| Reading / 阅读 | Real chapter trees, continuous reading, page navigation, readable PDF projection and source-linked citations. / 真实目录、连续阅读、页码、可读 PDF 投影及原文出处。 | Original block identities and offsets remain stable. / 原文身份和偏移保持稳定。 |
| Knowledge / 知识 | Cited answers, knowledge pages, editing and explicit updates, summaries/outlines. / 带出处问答、知识页、编辑更新及摘要提纲。 | Answers and knowledge remain source-grounded. / 问答和知识仍以资料为依据。 |
| Visual Deck | Combined/separate chapter or source scopes, parent-book context, original-image understanding, interpretation and adaptive visual direction. / 合并或分别生成、全书背景、原图理解、解读与自适应视觉。 | Image text and redrawn figures need human review. / 图片文字和重绘图表需核对。 |
| Artifact control / 产物管理 | Stop/resume/delete, checkpoints, failure details, revisions, naming, source manifest, PDF and ZIP download. / 停止继续删除、恢复点、失败详情、修改命名、来源清单与下载。 | Existing artifacts are preserved across upgrades. / 升级保留既有产物。 |
| Performance / 性能 | Bounded cross-task scheduling, shared service budgets, configurable content/OCR/image concurrency and reusable context. / 跨任务受控调度、共享额度、可配置内容识图生图并发及背景复用。 | Provider capacity determines actual speed; one process owns each data directory. / 实际速度受服务能力影响，每目录一个进程。 |
| Languages / 语言 | Twelve interface/output languages, browser defaults and Arabic RTL. / 12 种界面和输出语言、浏览器默认及 RTL。 | Changing interface language does not translate saved content. / 切换界面不会改写已有内容。 |
| Self-hosting / 自托管 | Docker, SQLite, encrypted credentials, backups and isolated verification. / Docker、SQLite、加密密钥、备份及隔离验证。 | Single-user; no built-in public-access authentication. / 单用户，无内置公网鉴权。 |

## Further work / 后续方向

See the [roadmap](../ROADMAP.md). Candidates include image-text verification,
faithful original-figure embedding and searchable text in image-page PDFs. These
remain unimplemented and require explicit design and acceptance criteria.

后续方向见路线图；图像文字校对、精确原图嵌入及图像 PDF 的可搜索文字层尚未实现，
需要明确设计及验收标准。功能任务应覆盖用户流程、持久化、失败恢复、兼容和测试；
不得通过清空用户数据或改写历史产物来验证。
