# 相对于原始 v0.1 的需求与设计变更

更新日期：2026-10-04；代码范围：`769f463` 基础及 decisions 030–035 增量。
这里汇总用户的后续要求与实际设计调整，避免把增量决策散落在聊天或历史 ADR 中。
当前完整契约为 [PRD](PRD.md) 和 [SYSTEM_DESIGN](SYSTEM_DESIGN.md)，
原始文本保存在 [archive/v0.1](archive/v0.1/README.md)，阶段记录见 [IMPLEMENTATION_PLAN](IMPLEMENTATION_PLAN.md)。

## 1. 文档与决策优先级

1. 当前任务中的明确用户要求与本会话已接受的约束。
2. 当前 PRD（产品行为）和当前系统设计（实现契约）；有差距要记录，不能假装实现。
3. 已接受的增量 decisions；后来的明确 supersession 优先于早期同主题决策。
4. 实施/验收记录用于证明具体版本实际做过哪些验证。
5. 原始 v0.1 文档及旧阶段是历史基线，不覆盖后续授权的变更。

此更新不增加云账户、Agent、PPTX 等未授权范围，不自动宣布正式发布或变更软件版本。
既有原稿保留；新行为原则上用于新建/明确的副本操作，停止后继续不自动升级历史产物。

## 2. 变更矩阵

“已实现”表示有代码与对应测试，不表示真实模型内容/视觉质量已穷尽验收。

| ID | 原始 v0.1 / 早期行为 | 当前需求与设计 | 状态 / 依据 |
|---|---|---|---|
| C01 | PDF 仅文本层，拒绝扫描；DOCX/OCR 明确排除（PRD 7/8/42） | `.docx`、扫描 PDF、文档插图识别；原图可读、失败可重试；`.doc` 仍排除 | 已实现；[012](decisions/012-word-vision-and-chapter-scopes.md) |
| C02 | Language 只有文本/JSON 能力测试 | Language 还处理多模态 OCR/原图理解，有独立 vision-test；Image 不负责 OCR | 已实现；[012](decisions/012-word-vision-and-chapter-scopes.md)、[018](decisions/018-original-images-in-deck-reading.md) |
| C03 | PDF 阅读直接显示 normalized block，已有导入出现一行一字 | 原始 PDF 对齐的可读投影；正文 block/引用身份保持不变，不能对齐时回退 | 已实现；[003](decisions/003-readable-source-projection.md) |
| C04 | 精确 quote 可以只有一个字 | 检索以段落 evidence、引用显示精确范围 + 完整相关原文上下文 | 已实现；[004](decisions/004-paragraph-citation-context.md) |
| C05 | 笔记本/章节/Deck 存 React 状态，刷新丢位置 | URL 是已保存对象/Scope 定位来源，刷新/历史/新标签可恢复；草稿导航保护 | 已实现；[005](decisions/005-addressable-navigation.md) |
| C06 | 无便捷章节连续阅读；页或推测标题充当目录 | 上下章节、底部连续阅读、独立 PDF 前后页/页码；无书签 PDF 没有伪目录 | 已实现；[006](decisions/006-reading-navigation.md) |
| C07 | 未规定界面多语言 | 12种常用界面语言即时切换并持久化，不翻译资料/模型产物，不清草稿 | 已实现；[INTERNATIONALIZATION](INTERNATIONALIZATION.md) |
| C08 | 单个 current chapter/source/selected Scope 创建一份 Deck | 支持多选章节 union，父子范围去重，真实原文顺序；EPUB/PDF/Word 树状目录 | 已实现；[012](decisions/012-word-vision-and-chapter-scopes.md)、[013](decisions/013-separate-decks-and-chapter-tree.md) |
| C09 | 没有生成模式或批量创建回执 | 可选合并/分别；每资料/所选章节范围一份，层级选择、原子 batch 和 request-key 幂等，最多 100 份 | 已实现；[013](decisions/013-separate-decks-and-chapter-tree.md) |
| C10 | 图像只作独立资产，文字由 deterministic Renderer 绘制（设计 40–44） | 新 Deck 默认由图像模型生成完整图文页；内容/出处先保存，旧 native 路径兼容 | 已实现；[008](decisions/008-whole-page-image-generation.md) 取代默认原生渲染约束 |
| C11 | PDF 必须图像 + 可选/可搜索文字层（PRD 28/43） | 默认图像 PDF，无正文文字层；文字稿/出处在应用中；旧 native PDF 仍可选文字 | 明确取代旧验收；[008](decisions/008-whole-page-image-generation.md)。图像文字层为开放项 |
| C12 | 内容/图片各自规划，导致图文关系弱 | native 曾加持久集成页面设计；整页路径保留语义关系与读字预算，但不再叠原生文字 | native 兼容保留；[007](decisions/007-integrated-page-design.md) 后续由 [008](decisions/008-whole-page-image-generation.md) 取代默认路径 |
| C13 | 声称自由设计但页面重复同一场景 | 生图前全套 art_direction，形式先决条件/去重/多样性；13 种解释形式是语义词汇而非模板 | 已实现；[009](decisions/009-deck-visual-repertoire.md) |
| C14 | 风格 prompt 偏暖纸插画；拷贝常继承旧风格 | 模型结合内容自由提出三种方向并选择，媒介贯穿后续；UI 视觉/内容副本均 restyle | 已实现；[016](decisions/016-content-adaptive-deck-style.md)。不承诺随机让各主题不同 |
| C15 | 自动添加“作者见解”“解读边界”等；早期过度 source-only | 默认无生硬元说明，允许有内容价值的解读；原文限制仍保留；显式请求可覆盖标签默认 | 已实现；[010](decisions/010-direct-content-and-concurrent-pages.md) 的 Deck source-only 口径被 [015](decisions/015-user-directed-deck-interpretation.md) 取代 |
| C16 | 补充说明作用晚、解读只是原文换词 | 意图从首次理解进入所有 Deck 内容阶段；允许模型背景/类比，内部 basis 保证不冒充原文 | 已实现；[015](decisions/015-user-directed-deck-interpretation.md)。不扩散到 Chat/Knowledge |
| C17 | 系统展示偏好容易压过明确用户要求 | 事实/安全/显式技术契约 → 用户明确要求 → 默认表达；单页 revision 更具体 | 已实现；[015](decisions/015-user-directed-deck-interpretation.md)、[016](decisions/016-content-adaptive-deck-style.md) |
| C18 | 单章只收到本章和书名，模型凭记忆推测全书 | 自动读取实际上传的父书正文和目录，缓存 reading map，章仍主体；明确 chapter-only 可禁用 | 已实现；[017](decisions/017-automatic-parent-work-context.md) |
| C19 | Deck 只用图像 OCR/描述，空间信息易丢 | 初读和全书阅读直接看原图分批理解，相关页再对照；无 transcript 图像仍可有原图出处 | 已实现；[018](decisions/018-original-images-in-deck-reading.md)。精确原图嵌入未实现 |
| C20 | 图片生成串行/早期并发上限 4，设置在环境 | 模型设置中独立保存图片生成并发 1–20/default 2，任务内冻结、稳定页序和取消 | 已实现；[011](decisions/011-image-concurrency-model-settings.md) 取代 [010](decisions/010-direct-content-and-concurrent-pages.md) 范围 |
| C21 | 文档图片逐个识别，慢且不可配置 | 语言模型卡独立识别并发 1–20/default 4；重复图 single-flight、checkpoint/顺序/取消；PDFium 保留锁 | 已实现；[019](decisions/019-controlled-image-recognition.md) 取代 [012](decisions/012-word-vision-and-chapter-scopes.md) 串行描述 |
| C22 | Deck 分段理解和页写作串行，成功识图读数跨任务难复用 | 独立内容并发 1–20/default 2，compact 原图理解可按输入/model/意图缓存、跨 job remap 引用 | 已实现；[020](decisions/020-deck-generation-reliability.md) |
| C23 | 重试完整输出，通用错误遮盖阶段；合法 ID/中文长度误拒 | 注册出处目录、确切 ID 格式规范、实际 token/字节约束；多问题反馈与字段合并，作者第三次仅有进展时 | 已实现；[020](decisions/020-deck-generation-reliability.md)。不放松真实性校验 |
| C24 | author 失败后 art 的“缺内容”错误盖掉原始原因 | Deck partial 保留有效 spec/原始页错误，bulk retry 仅补缺页后生图导出 | 已实现；[020](decisions/020-deck-generation-reliability.md) |
| C25 | 有队列 retry，但用户不能稳定停止/继续与删除所有 Deck | queued/running 停止、原 job/payload 恢复、停止状态跨重启；任意 Deck 删除、文件归属清理和 batch tombstone | 已实现；[014](decisions/014-deck-controls-and-preview.md) |
| C26 | 缩略图长列表推走大图；剩余高度在平板过小 | 独立滚动、约一屏高/520px 下限、响应式全宽、专注预览与焦点/Escape/前后页 | 已实现；[010](decisions/010-direct-content-and-concurrent-pages.md)、[014](decisions/014-deck-controls-and-preview.md) |
| C27 | 新规则容易直接影响历史产物，旧副本复用不明确 | 老产物冻结；视觉副本保留文字出处而重选风格，标准重写副本刷新理解；非标准删页保护序列 | 已实现；[008](decisions/008-whole-page-image-generation.md)、[015](decisions/015-user-directed-deck-interpretation.md)、[016](decisions/016-content-adaptive-deck-style.md)、[017](decisions/017-automatic-parent-work-context.md) |
| C28 | Docker 目标已定义但开发环境最初缺 runtime；访问只给本地链接 | Colima/Docker 环境与生产容器验收工具；可信 LAN 可配置 bind/Host，公网远程访问仍无内置认证方案 | 已实现部署工具与历史验收；[DOCKER_ACCEPTANCE](DOCKER_ACCEPTANCE.md)。026 增量的完整 Docker 复验已通过，见 ACCEPTANCE |
| C29 | 一般 job/error diagnostics | 每次生成的安全阶段/attempt/耗时/字段路径/token metadata，并行 ContextVar 隔离；全局 100 次、单 Deck 500 次，UI 支持失败详情/历史/刷新/下载 | 已实现；[020](decisions/020-deck-generation-reliability.md)、[021](decisions/021-deck-art-repair-and-failure-details.md)。不导出原文/提示/响应/凭据 |
| C30 | art 仅反馈首个失败，作者修复总是整页输出 | art 多规则预检、有路径局部修复/无路径完整修复；布局归一化支持各语言，重复定位超限页面、保留有效编排，诊断去重并显示安全计数；作者按修改范围选择 patch 或完整单页 | 已实现；[021](decisions/021-deck-art-repair-and-failure-details.md)、[028](decisions/028-multilingual-art-layout-validation.md)，严格出处与表达支持约束保留 |
| C31 | 桌面三栏与两种语言 | 小屏幕分区、弹窗键盘、操作层级、清楚状态、12种语言与RTL | 已实现；[UI_REVIEW](UI_REVIEW.md)、[022](decisions/022-ui-review-and-common-languages.md) |
| C32 | 单文件上传，Web URL 排除 | 多选文件与单个/批量 URL 网页正文导入，逐项回执/失败/重复处理，快照/安全公网抓取；修复 Word 继承样式 | 已实现；[023](decisions/023-batch-files-word-fix-and-web-import.md) |
| C33 | 网页只保留图片说明 | 导入可选保存正文原图，后台下载/受控识别、原始字节下载、逐图失败重试、旧网页显式补图，正文与成功图片事实保留 | 已实现；[024](decisions/024-optional-web-image-archive.md) |
| C34 | Deck依靠缩略图/工具栏翻页，点击大图打开高清页 | 普通/专注预览大图左右透明点击区域与↑/↓切页，首尾不循环，输入/弹窗保护，稳定URL与缩略图同步；独立高清链接 | 已实现；[025](decisions/025-deck-preview-navigation.md) |
| C35 | Deck 没有整体来源清单，名称只能由模型生成；PDF 以随机 ID 命名 | 冻结资料/章节/知识页版本；单来源可沿用来源名，章节采用资料名称-目录层级序号-章节名称；闲置 Deck 可改名，PDF 下载使用当前名称且保留已有产物 | 已实现；[026](decisions/026-deck-names-and-source-manifest.md)、[027](decisions/027-chapter-deck-source-names.md) |
| C36 | 全局单重任务、上传/索引批次串行，网页先全下载再识别 | 单进程持久有界调度（1–8/default3），同实体/原资料读写预约，任务类别轮换；按服务共享请求总限额（1–20/default8）、同类准备阶段共享额度；上传三并发、索引两批并发且原子发布、网页下载识别流水线、同书初读单飞 | 已实现；[029](decisions/029-bounded-cross-task-scheduling.md)，取代单重任务执行要求，保留单目录所有者及停止恢复 |
| C37 | 产物只能逐份下载PDF | Deck列表多选/全选当前PDF并打包ZIP，保留名称/字节，重名编号、失效整体拒绝，不触发模型或自动导出；通用选择/适配器供未来扩展，当前仅Deck | 已实现；[030](decisions/030-artifact-batch-downloads.md) |
| C38 | PDF展开RGB后直接压缩并套ASCII85，典型20页约70MB | 无损像素预测与更紧凑PDF流，新PDF默认；既有PDF显式重新导出独立压缩版，旧字节/签名保留，单份/批量优先新版本，无需生图 | 已实现；[031](decisions/031-lossless-pdf-encoding.md) |
| C39 | 保存Embedding后重试全部已解析source_ingest，无专用进度/失败重试，地址不进入索引身份 | 事务排队专用索引重建，区分服务/模型/维度；设置内整体及逐份进度、失败重试与显式全部重算，原文/引用不变，连续切换与重启恢复 | 已实现；[032](decisions/032-embedding-model-index-rebuild.md) |
| C40 | 未配置接收服务时匿名统计开关不能启用 | 用户选择与部署配置分开；无接收服务也可保存/关闭，明确本地暂存不发送、保存反馈及失败回滚；默认关闭保持 | 已实现；[033](decisions/033-statistics-consent-and-receiver.md)，统一统计接入/商业化未实现 |
| C41 | 问答按问题语言、知识/转换按源语言，部分系统提示和模型标签固定英文、日期按浏览器locale | 新内容语言默认跟随界面，可独立选择同一组12语言；提交冻结，知识更新保留页语言，引用不翻译；系统提示/标签/诊断日期与时长本地化 | 已实现；[034](decisions/034-content-output-languages.md)，旧产物不自动改写 |
| C42 | 首次默认简体中文，隐式默认可能随统计更新写成固定语言 | 首次匹配浏览器/系统偏好，地区/文字变体映射12目录，未匹配回退英文；保存选择优先，自动选择不持久化 | 已实现；[035](decisions/035-browser-default-language.md)，取代022固定默认与034跟随界面时的初始语言 |

## 3. 未被修改的原则

单用户自托管、Notebook 顶层、用户带模型 API、无固定 PPT 主题模板、
Source/CitationSpan 是事实追溯、索引可重建、API 密钥加密/环境引用、原始资料不被 AI 改写、
用户触发 Knowledge 更新、长任务持久化、失败保留完成结果、遥测可关闭且不采用户内容。

普通 Chat 的原文约束仍存在。Embedding 仍用于索引/检索，没有落地新的全文 Chat 模式。
全书背景是 uploaded Source，不是互联网搜索；vision 理解不意味着最终精确嵌图。
“可在手机上用网页”也不意味着已实现移动 App 或公网认证。

## 4. 不能宣称已完成的项目

- 默认图片 PDF 的可选/可搜索文字层：已从当前发布验收移除，未来实现仍需真实定位。
- 原图精确嵌入/图表保真：当前最终页重绘。
- 自动检查图片中文字与文字稿、数字、图表一致性：尚未实现。
- 真实解读深度、跨主题风格和模型幻觉的全面质量验证：只有具体样本，需持续评价。
- 后续改动仍需对应容器复验；本次026已通过完整Docker、重启与重建验收，证据见ACCEPTANCE。
- `.doc`、鉴权/公网共享、PPTX、联网研究与自动 Agent：仍在范围外，不能借文档更新实现。

## 5. 后续如何更新

变更需求时同时修改 PRD 对应行为、SYSTEM_DESIGN 实际契约和本矩阵；
关键取舍新增有序 decision，写明哪些旧口径被取代、兼容策略和验证。
IMPLEMENTATION_PLAN 只记录实施/发布状态；ACCEPTANCE 记录具体版本和真实证据。
原始归档不要改，避免丢失最初需求；旧 ADR 保留历史正文，在文件顶部加入取代提示。
如果是未来建议，单列 pending，不混入已完成行为。HANDOFF 的测试/入口/运行步骤应随代码维护。

## C43 — Public MIT Beta (036)

用户选择先以MIT公开，完善全部发布准备，并要求发布相关说明中英文。
已准备公开文档/规则/合成演示、许可清单与原文、版本和镜像草稿流程、安全/版本/隐私
文件检查；运行与数据契约不扩展。公开snapshot接续远程LICENSE-only main，私有原历史
保留。平台设置、实际GitHub CI、镜像公开和Release发布需要独立确认与验证，不因本地
准备或旧验收视为已完成。详见RELEASING与ACCEPTANCE Stage52。

## C44 — Native XML and container release review (037)

沿用用户授权的发布准备，纠正Python包审计未覆盖内置底层库的缺口。Docker重建锁定
lxml并固定新XML/XSLT源码哈希、核对实际加载版本，许可与对应源码进入附件；应用
权限删除、初始化只保留CHOWN。原生uv sync、现有应用和用户数据不变，系统包高危/
严重项仍严格阻止发布，详见037、CONTAINER_SECURITY_REVIEW与ACCEPTANCE Stage53。

## C45 — Hosted checks and exact container applicability (038)

用户进一步授权完成上传、实际GitHub检查及通过后的首个中英文Beta发布。公开PR接续
原LICENSE提交，不上传私有开发祖先。后端/前端/容器分别检查；只将测试等待5秒扩大到
30秒，不放松产品校验。容器固定兼容厂商补丁、限制CPU绘制并移除管理工具，准确版本、
运行代码、权限及组件条件由探针核查；原始漏洞记录保留，新记录/版本漂移/复核到期和
未解决高危仍失败。账号登录是仓库设置/发布页面的实际前置条件，不再泛泛重复询问
发布授权。详见038和ACCEPTANCE Stage54。
