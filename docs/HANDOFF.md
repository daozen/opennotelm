> Public documentation: machine-specific paths, private example names and addresses have been removed. Historical results retain their original scope; private operational copies are not included. / 公开文档已去除本机路径、私有示例名称与地址；保留历史验证范围，私有操作记录不随仓库发布。

# Coding agent 接手手册

更新日期：2026-10-05。实现范围：`769f463` 基础及 decisions 030–038 增量；初次整理时分支 `feat/v0.1`，软件版本 `0.1.0`。
分支名、PID、模型服务和内网 IP 都是环境状态；接手先实际检查，不依赖这些快照。
本文可直接作为后续 coding agent 的仓库入口，配合根目录 [AGENTS](../AGENTS.md)。

## 1. 先建立上下文

建议按此顺序读取，通常无需先读全部历史验收或整个聊天记录：

1. [当前需求](PRD.md)：用户目标、支持范围、默认行为、硬约束与开放项。
2. [需求差异](REQUIREMENTS_CHANGES.md)：原始 v0.1 哪些已被后续要求取代。
3. [当前设计](SYSTEM_DESIGN.md)：数据、流程、模块、缓存、版本和 API。
4. [实施/验证状态](IMPLEMENTATION_PLAN.md)：已做什么、证据到哪里、剩余哪些发布门槛。
5. 本文的运行、修改入口、故障排查和数据操作。
6. 当前任务相关的 `docs/decisions/` 文档及对应测试；必要时再查 [ACCEPTANCE](ACCEPTANCE.md)。

原始 [v0.1](archive/v0.1/README.md)是归档，不是把新功能回退的依据。
新用户要求优先于默认展示偏好，仍受事实、数据、安全和明确技术契约约束。
发现当前文档与代码冲突时，核查代码、测试和决策并记录差距；不要默默选择旧口径。

当前最容易误读的四点：

- 默认 Deck 是**图片模型生成完整图文页面**，不是原生 RenderSpec 绘制文字；原生是兼容路径。
- Deck 可以用模型知识引申，Chat/Knowledge/转换没有因此获得通用知识模式。
- OCR、Deck 理解原图、最终页面生成是不同阶段，使用不同缓存和独立并发设置。
- 029已取代单重任务执行：一个服务进程持久调度多个实体，共享阶段/服务额度和资料读写预约。
  不通过多个Uvicorn workers提速。同书首次背景读取单飞，后续章节复用签名缓存。

发布准备还应读取[容器安全核查](CONTAINER_SECURITY_REVIEW.md)和[状态](RELEASE_STATUS.md)。
Docker对锁定lxml重编译底层XML库，最终uv sync后必须保留替换；不能以pip包审计通过
推断内置库或OS库安全。Compose应用删除全部额外权限，初始化仅保留CHOWN。原生
uv sync不获得镜像替换；当前生产环境未升级。038补充准确厂商补丁、CPU服务及条件化
安全核查。原始扫描记录不删除；仅已核查的准确版本/运行条件可归类，代码/锁文件/
包版本变化或2026-11-04到期需要重新审查，不得仅重算哈希绕过。云端及双架构的真实
状态以RELEASE_STATUS为准，不能把本地门禁通过等同于已发布。

## 2. 工作前检查

```sh
git status --short
git branch --show-current
git log -5 --oneline
```

保留其他人的未提交改动；围绕当前分支的任务继续，必要的新分支默认 `codex/` 前缀。
不要重置现有用户数据，不把 `.env`、密钥、原文、生成图片或数据库提交进 Git。
本工作区 `data/` 有真实用户资料，曾由独立本地服务在 `127.0.0.1:3000` 使用。
先检查端口/启动方式/任务状态；不要为了测试停掉或接管这个实例。

`data/instance.lock` 是 flock 锁，文件存在不等于正在运行，删除它也不是安全解锁方法。
同一目录不可用多个进程、多个 Uvicorn workers、原生和 Docker 双开。

## 3. 启动和测试环境

### 3.1 依赖与隔离实例

需要 Python 3.12、uv、Node.js 24；锁文件为 `uv.lock` 和 `frontend/package-lock.json`。
从仓库根目录：

```sh
uv sync --locked
uv run playwright install chromium
```

前端：

```sh
cd frontend
npm ci
npm run build
```

回到仓库根，启动自己的独立数据实例（不会读取用户 `data/`）：

```sh
task_data_dir=$(mktemp -d /tmp/opennotelm-agent.XXXXXX)
DATA_DIR="$task_data_dir" uv run uvicorn opennotelm.main:app --app-dir backend \
  --host 127.0.0.1 --port 4304 --no-access-log
```

打开 `http://127.0.0.1:4304`；已有 `frontend/dist` 会由该 API 实例同源提供。
需要热更新时，在另一个前端终端：

```sh
OPENNOTELM_API_PROXY=http://127.0.0.1:4304 npm run dev -- --port 5174 --strictPort
```

打开 5174，API 仍经 Vite 同源代理，不能直接在浏览器跨 Origin 调写接口。
4304/5174 只是建议空闲端口，使用前检查占用；这套独立实例无需生产密钥。

Linux 浏览器可用 `uv run playwright install --with-deps chromium`。
默认使用各自 Playwright 版本配套的 Chromium/headless shell；Apple Silicon 使用 ARM64
版本。更新 Python/Node Playwright 后分别安装匹配浏览器，不要默认指定个人 Chrome。
确需指定其他兼容浏览器时，后端设置 `RENDER_BROWSER_EXECUTABLE`，前端设置
`PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH`；指定路径不保证与 Playwright 版本兼容。
原生 PDF 像素测试需要 Poppler `pdftoppm`，CI 会安装；缺失会显式 skip，不能报告全通过。

### 3.2 常规质量检查

按改动范围先跑有意义的定向测试，修复后完成适当的回归：

```sh
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
git diff --check
```

前端目录：

```sh
npm test
npm run build
npm run format:check
npm run test:e2e
```

`pytest` fixtures 使用临时目录与 MockTransport，不使用用户数据。
前端 browser suite 启动 4300 API、4301 mock provider、4302 Vite，使用 `.e2e-data/`；
保证端口空闲，一次只运行一组，结果在 `frontend/test-results/`。
修改 UI 时能定向 `npm run test:e2e -- e2e/<文件>.spec.ts`。
不要把 mocks 的视觉图片当成真实模型效果，也不要静默跳过失败流程。

#### macOS 浏览器启动检查（2026-10-04）

真实浏览器检查应在普通终端或允许启动进程/本地监听端口的已授权测试命令中运行。
本机曾在受限 agent 环境连续启动系统 Chrome，出现五份 `_RegisterApplication`/
`TransformProcessType` SIGABRT 报告；结合执行记录，符合 macOS 应用注册受限的启动失败，
不是 OpenNoteLM 服务退出。报告中的 Rosetta 不能单独证明架构是根因。
此指导取代历史验收记录中“先在沙盒运行、失败后改用系统 Chrome”的流程。

先检查（静态合成内容，不访问模型、生产资料或个人浏览器配置）：

```sh
uv run python tools/browser_check.py --repeat 3
```

检查本地端口权限后才启动浏览器，验证截图尺寸及 PDF 页数、尺寸、可提取文字。
失败立即停止，不自动重复启动/切换个人 Chrome。端口检查是必要条件，不能证明所有
GUI 权限均可用；若浏览器仍失败，检查执行权限、匹配浏览器及系统诊断报告。
`npm run test:e2e` 自动执行同一预检（使用后端 Playwright 环境和前端可选路径）；
实际 E2E 使用 Node Playwright 自己的配套浏览器，两个运行时都需要安装匹配版本。
macOS pytest 在收集含 `browser` 的测试时也检查本地端口权限，受限时明确报错，
不会启动浏览器或把测试记为通过。受限环境先跑 `uv run pytest -q -m 'not browser'`；
真实渲染/PDF/E2E 必须另在允许启动浏览器的环境补验，不能省略。
不需要更改个人浏览器配置、全局放宽沙盒或重启生产服务。

### 3.3 容器验收

默认部署命令会使用生产 `data/`，**不能用它启动另一实例做测试**。
专用隔离验收从根目录运行：

```sh
bash tools/docker_acceptance.sh
```

它使用 port 4303、独立 `.docker-acceptance-data.*` 和 Compose 项目，包含生产打包、
首次配置、完整浏览器流程、PDF、重启/容器重建和文件/密钥完整性比较。
运行条件、Colima 与宿主模型地址见 [DOCKER_ACCEPTANCE](DOCKER_ACCEPTANCE.md)。
原生与 Docker Playwright 默认共用输出目录，必须顺序运行或显式隔离 `--output`。
Docker 成功过不等于当前 HEAD 已复验，不能用较早验收替代新的发布门槛。

### 3.4 真实模型验收

自动 tests 默认不需真实凭据。真实验收才会调用外部端点并可能消耗费用。
使用合成/公开小样本先验证协议；真实用户文档只能在已授权的资料/端点范围内使用，
本会话已有的同范围授权有效，无需重复问同一件事。
记录页数/范围、模型能力、尝试、结果与实际限制，不在仓库保存提示/响应/凭据。
私有快照和诊断可放 `/tmp`，路径仅作临时定位，不作为未来唯一运行依赖。

## 4. 从哪里修改

下表文件均相对仓库根目录；测试名可以用 `rg --files backend/tests frontend/e2e` 查找。

| 任务 | 主要代码入口 | 最相关验证 |
|---|---|---|
| 上传/格式/安全 | `backend/opennotelm/source_service.py`, `epub.py`, `pdf_parser.py`, `docx_parser.py`, `text_parsers.py`, `web_fetch.py`, `web_parser.py` | `test_sources`, `test_epub`, `test_pdf_parser`, `test_text_parsers`, `test_docx`, `test_source_vision`; `formats`, `epub`, `document-images` E2E |
| 识别与原图 | `source_vision.py`, `source_visuals.py`, `image_recognition_settings.py` | `test_source_vision_concurrency`, `test_source_vision`, `test_deck_source_visuals`, `test_image_recognition_settings`; `document-images`, `model-settings` E2E |
| 单字/断行/引用段落 | `reading.py`, `pdf_text.py`, `passages.py`, `retrieval.py`, `citations.py`, `frontend/src/Citations.tsx` | `test_reading`, `test_passages`, `test_chat`, `test_deck_evidence_quality`; `reading`, `citation-paragraphs` E2E |
| URL/阅读切换/草稿保护 | `frontend/src/Navigation.tsx`, `NavigationGuard.tsx`, `Reader.tsx`, `readingNavigation.ts` | 前端 Navigation/Reader/Guard tests；`navigation`, `reading` E2E |
| Knowledge/问答范围 | `chat.py`, `knowledge.py`, `transformations.py`, `synthesis.py` | `test_chat`, `test_knowledge`, `test_synthesis`; 对应 E2E |
| 章节树/分别生成 | `frontend/src/ChapterSelection.tsx`, `chapterTree.ts`, `Deck.tsx`; `decks.py`, `retrieval.py`, `deck_schemas.py` | `test_deck_batches`, `test_chapter_selection`, ChapterSelection/CreateDeck tests；`deck-batches` E2E |
| 解读深度/硬标签/用户指令 | `deck_content.py`, `DeckService.preferences/understand/plan/author`, `synthesis.py` | `test_deck_interpretation`, `test_deck_content`, `test_deck_context` |
| 全书背景 | `deck_context.py`, `decks.py`, `synthesis.py` | `test_deck_context`, `test_deck_source_visuals` |
| 视觉风格/重复表达 | `deck_style.py`, `deck_art.py`, `generated_pages.py` | `test_deck_style`, `test_deck_art`, `test_generated_pages`; 真实跨题材图像检查 |
| 模型结构输出失败 | `structured.py`, `output_repair.py`, `deck_validation.py`, `generation_attempts.py`, `deck_diagnostics.py` | `test_structured`, `test_output_repair`, `test_generation_attempts`, `test_synthesis` |
| 并发/停止/继续 | `concurrency.py`, `request_limits.py`, `jobs.py`, `task_settings.py`, 三项 `*_settings.py`, `decks.py`, `source_vision.py` | `test_parallel_jobs`, `test_deck_content_concurrency`, `test_deck_lifecycle`, `test_source_vision_concurrency`; `deck-lifecycle`, `model-settings` E2E |
| 删页/改单页/导出 | `revisions.py`, `pdf_export.py`, `generated_pages.py`, `maintenance.py` | `test_revisions`, `test_generated_pages`, `test_pdf_export`, `test_lifecycle`; `revisions`, `generated-pages` E2E |
| PDF体积/无损压缩 | `pdf_images.py`, `PDFExportService` | `test_pdf_compression`像素/Poppler/旧新签名/失败回退/ZIP；旧PDF显式重新导出才保存压缩版，见031 |
| 批量下载 | `artifact_downloads.py`, `PDFExportService.downloadable`, `ArtifactBatchDownload.tsx`, `Workspace.tsx` | `test_artifact_downloads`、ArtifactBatchDownload单测、`deck-batches` E2E；临时链接重启过期，原PDF不变 |
| Deck预览翻页 | `frontend/src/Deck.tsx`, `styles.css` | Deck单测；`deck-lifecycle`、`navigation` E2E，边界/弹窗/稳定URL/图片高度 |
| 原生渲染兼容 | `page_design.py`, `composition.py`, `renderer.py`, `render_schemas.py` | `test_page_design`, `test_renderer`, PDF/native 浏览器测试 |
| 多语言/设置 | `frontend/src/i18n.ts`, `locales/*.json`, `LanguageSettings.tsx`, `Setup.tsx`, `ModelConcurrencySettings.tsx` | 前端 i18n/Setup/settings tests；`i18n`, `model-settings` E2E |
| 部署/隐私 | `main.py`, `instance.py`, `secrets.py`, `telemetry.py`, `diagnostics.py`, Docker/Compose | migrations/secrets/privacy/lifecycle tests、Docker 验收 |
| 统计开关/接收配置 | `frontend/src/PrivacySettings.tsx`, `telemetry.py` | PrivacySettings单测、`privacy` E2E、`test_privacy`；033区分用户选择和接收服务，未接入可保存但不发送 |

测试文件名为入口方向，新增或重命名时同步表格；不要据表名猜测测试实际覆盖。

## 5. 调试 Deck 时的判断顺序

1. 看该 Deck 的 job、stage 和各 slide 的状态/error_code。Job completed 可能是 Deck partial。
2. 看真实 `generation_metadata`，区分整页/native、内容 policy、风格版本、是否 restyled。
3. 看已保存 scope、plan、understanding 和每页 spec。发现老文字/老风格先排查复用，
   不先假定最新 prompt 已执行或模型不遵循。
4. 先在 Deck 查看失败详情/生成记录，或读取 `/api/decks/{id}/diagnostics`：
   最多 500 条，只属于本 Deck，含已知规则/字段/HTTP/页号/耗时；UI 显示 50 条。
   全局 `/api/diagnostics` 仍限制 100 条。旧记录缺失的具体规则无法补录。
5. 在私有数据库副本重现问题；避免删除生产 checkpoint、清空成功 spec 或强制升级原 Deck。
6. 修复校验/提示契约后验证有效字段/旧图片/原始出处仍保留，再考虑授权的真实重试。

| 症状 | 常见原因 / 对应修复边界 |
|---|---|
| Deck 报知识页校验失败 | 旧共用 synthesis 错误；现在 Deck 分别有 UNDERSTANDING/PLAN/PAGE 错误码，检查实际失败阶段 |
| 合法全书引用被拒 | planner 目录与验证范围曾不一致；检查提供的 registered catalog，不放开任意 ID |
| 图片理解反复重试 | 引用格式、截断/预算、vision 不支持或模型服务容量；不能只提高重试次数 |
| 中文完成输出超长 | 估算 bytes/3 不等于实际 completion tokens；保留 fallback、字节限制和截断检查 |
| 字数修复后仍失败 | 层级/关系引用已删除 element、分类/引用约束或坏 patch；看所有 preflight 反馈 |
| 9 页有文字，缺一页导致整体失败 | 保留成功页，Deck partial，bulk retry 作者只补缺页，再全套生图/导出 |
| 新副本仍是旧风格 | 内容重写是否 restyle、是否继承旧 style/art；检查 copy operation metadata |
| 视觉编排反复art_layouts | 旧英文-only归一化会清空中文并误判重复；028保留Unicode/空间数字，真正重复只修复多出页面layout字段；旧报告不含原描述，不能仅凭规则码断言语言误判 |
| 插图像原图却细节丢失 | 读图有分辨率/附图上限，最终是重绘，不是原图嵌入 |
| 每次第一章很慢 | 首次父书阅读 + 多图识别/理解；后续 map/checkpoint/cache 才能复用 |
| 提高并发不变快 | endpoint 限流/串行后端或 PDFium 锁；三项并发对应不同阶段 |
| 多份Deck未全部同时运行 | 任务总上限、同资料写入预约、同书首次read锁或共享阶段/服务额度；这些等待保护资源/事实，同来源读任务本身可并行 |
| 不再生成“已完成”Deck | 正常冻结/复用；新算法用视觉优化或重写内容副本，不自动改历史稿 |

增量（021）当时：354 后端、47 前端测试和两个相关 browser flow 通过。
按 Deck 报告、art 多规则反馈与作者 auto repair 入口已更新；后续完整容器复验见阶段40。

最近修复案例与证据在 [decision 020](decisions/020-deck-generation-reliability.md)、
[decision 021](decisions/021-deck-art-repair-and-failure-details.md)
和 ACCEPTANCE 的 `Deck generation reliability — 2026-10-03`。
`private-example-A` 两章的规划及六个样本页验证通过；`private-example-B` 的 69 图/18 分段理解、最后一页修复、
10 页整套生图与 PDF 下载成功。它们是样本证据，不是总体失败率承诺。

## 6. 缓存和兼容性：不要随便清空

Embedding切换：032的`embedding_identity.py/index_rebuild.py`维护兼容签名和专用
`source_reindex`任务；ModelService在保存配置的同一事务内排队，Setup内展示进度和
失败重试。不再通过source_ingest重跑解析/OCR；升级不自动失效旧向量。发布前检查
当前签名，连续切换更新同一活动job目标；重新关联曾移除的资料会补排该资料的缺失/过期
索引，只重建索引不解析/OCR。不要移除活动任务唯一索引或把旧模型向量用于
新模型检索。原文和CitationSpan不随重建改变，全部重算是明确手动操作。

- `media/*.json`：成功 OCR/图示识别事实；更换模型/并发不主动改写已发布 transcript。
- `work_context_cache`：同书章节共享的可重建全书 map；包含 source/model/prompt 签名，
  不包含章节特有用户指令。清它会重新读整本书。
- `visual-readings/*.json`：可重建的 compact 原图理解；按模型/用户意图/材料/版本缓存，
  跨 job 的 canonical ID 需正确映射；不能直接拿旧 job ID 当当前引用。
- `synthesis_checkpoints`：job/step 的分层理解恢复点；父书/章节命名空间不能互相覆盖。
- style/art/spec/assets/render/PDF：已完成的用户产物及版本签名；升级不得静默改写。

版本选择不是全局“最新数字最大就强行升级”。
当前参考：`deck-content-v5`、`source-interpretation-v2`、`content-adaptive-style-v1`、
`deck-art-v2`（自适应）、`whole-page-v6`（自适应）、`source-originals-v1`、
`whole-work-context-v2`；实际 prompt_version 按 metadata 分支。旧版本仍兼容。
完整逻辑在对应代码，版本变更需新增兼容与签名测试。

“继续”复用原任务/输入/风格；“重写内容副本”才刷新标准长度的研究/规划；
非标准删页长度保留既有 dossier/顺序。视觉副本无法恢复旧 dossier 从未读过的信息。

## 7. 生产数据升级、回退与删除

文档任务本身无需停止或重启生产。若后续任务需要更新服务，按以下次序：

1. 检查当前启动方式/监听端口/有效 `DATA_DIR`，确认是否有 source/Deck job 正在工作。
2. 给当前版本和完整数据备份命名；数据库在线备份使用 SQLite backup API，
   不能简单复制活动 `app.db` 忽略 WAL。完整一致备份优先在正常停止服务后复制整个目录。
3. 正常停止目标进程/Compose，等待 worker、模型请求与受保护文件写入退出。
4. 复制完整数据、`secrets/master.key` 和密钥文件；可记录资料/产物 checksum 和表数量。
5. 启动新版本一个进程，自动迁移，核验原 Notebook/Source/引用/旧 PDF/密钥解密。
6. 区分主动 stopped 与意外 interrupted：主动取消不自动排队；意外中断可从保存阶段恢复。
7. 记录实际版本、验证结果和已知限制；不要把 PID 写成永久启动入口。

回退时恢复**对应代码版本 + 完整旧数据备份**；旧程序不能直接打开较新 schema。
现有迁移最大编号 019；新增从后续编号开始，先查是否有其他开发已新增。

资料 unlink 不同于永久 delete。永久资料删除保留历史内容/引用身份但标不可用；
Deck delete 先取消任务，事务删除其自有数据，持久文件清理由 maintenance 恢复。

2026-10-04 用户另行授权清理批量无损优化后被替代的37份旧 Deck PDF；只删除私有批次
清单中的旧 `pdf_exports` 行及对应目录，不是自动回收策略，也不包括资料原件或页图。
这37份旧下载/预览链接已返回404，新版继续可用。停服清理前的完整当前数据与逐项清单在
`<private-verification-path>`，恢复时须先检查当前业务变更，不能直接
用清理前全库覆盖后续工作。执行与校验证据见[验收记录](ACCEPTANCE.md) Stage47。
不要手动删除共享 source 文件、用 SQL cascade 模拟产品删除或替换 secret 主密钥。

## 8. 发布状态与下一步可选工作

已实现的范围和历史验证见 [IMPLEMENTATION_PLAN](IMPLEMENTATION_PLAN.md)。
阶段 37 验证：354 后端、47 前端和两条相关 browser flow；
真实失败 Deck 重试 185.6 秒完成剩余生成，保留 20 页文字并导出 20 页 PDF。
此前 private-example-B 及六个相关 flow 的证据仍按自身日期和版本保留。
阶段40已通过415后端、59前端测试及完整生产镜像验收：首次配置、27条浏览器流程、
进程重启与容器重建完整性检查。末次下载缓存/顺序调整另通过52项相关后端回归，
并在最终镜像通过正向图片保存测试。真实网页下载验证不包含真实模型识别质量；
详细范围见ACCEPTANCE最新记录。软件仍为0.1.0，未由此宣称正式版本已发布。

后续候选（需由具体用户任务确定，不自动扩范围）：

- 图片中文字/数字/引用与文字稿自动校对：必须明确复验与不通过行为，不能只跑 OCR 就宣称准确。
- 精确保留原图：设计可追溯原图嵌入或混合排版，避免图表重绘误差。
- 默认图片 PDF 搜索/复制：必须真实定位，不能覆盖错误/凭空隐形文字层。
- 真实跨题材风格和解读深度评估，提供小而可重复的质量样本。
- 单页 retry 与尚未生图的已写作兄弟页协作行为；当前 bulk retry 已有覆盖。
- 完整容器/真实模型/安全及发布门槛审计；不以 mock 数量代替产品质量判断。

明确尚无：旧 `.doc`、账户/鉴权、内置安全公网访问、PPTX、Web Search/连接器/自动 Agent。

## 9. 完成一项任务应交付什么

相关用户路径、持久化、错误/部分成功、恢复与回退兼容一起完成，不以“接口存在”结束。
测试针对真实边界和数据风险，不写只复制实现的低价值断言。
功能变更同步当前 PRD/设计/差异表，必要时新增有序 decision，更新实施和验收证据。
翻译变更维护12种语言键与插值一致；UI 用面向用户的术语，不泄露内部 ID/basis。

提交前检查 diff 与敏感文件，使用清晰的 `feat/fix/test/docs` commit。

## 10. 网页图片增量（024）

入口为 `SourceImport.tsx` 可选勾选、`source_service.py` 的 `source_web_images` 和
`web_images.py` 下载器。测试 `test_web_images.py`、Reader/SourceImport tests 和 source-import
browser flow。正文先 parsed/indexed，图片排队/下载/识别不应让阅读器不可用。图片状态
在 metadata 和 job，不能按 source.status=failed 判断图片是否完成。

HTML、web.json、原始图片字节、成功 transcript 都保留；网页正文解析仍 web-v1，图片扩展
web-images-v1。不能为了提取新图片重排旧正文身份；两个提取阶段只后者发现图片。
原图下载和归一化 PNG 预览不同，Deck 理解仍读取内部预览，最终整页仍重绘。
重试按已登记原图/cache恢复，不重新请求正文；原图丢失不能从变化的外链补一张冒充原图。
新增任务必须写 source_id，删除/重启必须覆盖它。尚无登录浏览器采集、SVG安全转换、
动画逐帧识别或最终Deck精确原图嵌入。默认限额与修改入口见 decision024。
只在授权范围发布/重试真实任务；普通文档整理不用重跑全套模型或重启服务。
最后说明改了什么、如何验证、仍有什么实际限制，让下一位 agent 能继续而不是重新猜。

## UI 与12语言维护

首次自动匹配见[035](decisions/035-browser-default-language.md)：GET preferences中的
ui_language可以null，表示没有保存选择，前端浏览器检测。保存选择优先，已有值不迁移；
仅改统计偏好不得顺便保存默认locale。languages.test.ts验证地区/文字匹配，i18n及
automatic-language E2E检查检测/缓存/手动选择。服务器OS语言不是用户系统语言。

新内容语言见[034](decisions/034-content-output-languages.md)：Workspace默认跟随界面、可
独立选择同一组12语言，提交时冻结到job。后端languages.py是输出语言白名单，分层
Synthesis及checkpoint均覆盖语言；已有知识更新保留页metadata语言，旧API缺失参数兼容。
系统资料不足提示以typed status本地化，不改写历史消息/用户内容；原文引用不可翻译。
定向测试为test_output_languages.py、Chat.test.tsx及output-languages E2E。

本轮交互清单：[UI_REVIEW](UI_REVIEW.md)、decision022。重要入口为Modal.tsx、Workspace.tsx、languages.ts、i18n.ts和12套locales JSON。新模态窗口使用Modal包裹语义dialog并给出onClose/busy；保持原有未保存保护。不要把小屏幕分区改为条件卸载，否则会丢草稿。新翻译键必须同步全部语言及变量；语言目录与后端PreferencesInput保持一致。阿拉伯语检查html dir、逻辑CSS间距、原文dir=auto和图像不镜像。测试入口为ui-review E2E、Modal/i18n单测和preferences后端测试；详见INTERNATIONALIZATION。

## 资料导入增量（023）

`SourceImport.tsx` 统一文件多选、重复确认队列、逐项结果和 URL 弹窗；多语言键均在12个目录。
API `sources/urls` 只登记和排队；worker 下载快照再提正文/索引，重试不重新抓已完成快照。
测试入口：test_web_sources、test_docx、SourceImport 单测、source-import E2E。
公网被误判时检查系统 DNS 是否全部在198.18/15；默认安全 DoH 回退不允许真实私网。
保留原始 HTML/manifest，不执行脚本或继承浏览器登录态；远程图片保存现由024可选扩展。
Word basedOn 错误已修复，不再用 defusedxml 构造接口。机制/取舍见decision023。

## Deck 名称与来源增量（026）

修改入口：`deck_sources.py`（创建快照/旧数据还原）、`decks.py`（名称策略与实体检查）、
`pdf_export.py`（稳定export_title与安全下载名）、migration019；UI为DeckSources/DeckRenameDialog。
只读来源清单不能补造生成时历史名称；不要把当前知识页版本替代已冻结revision。
纯改名不能递增Deck revision或改变历史PDF hash；不要修改EXPORT_VERSION绕过旧缓存。
未应用019的旧代码不能打开新数据；回退必须恢复对应完整数据库及文件。
测试见test_deck_identity、CreateDeck/Deck/DeckSources与deck-batches浏览器流程。
027补充：来源命名的单章节使用资料名-完整目录层级序号-章节名；序号冻结于manifest的
可选number字段，不按勾选顺序或页码编号。EPUB目录名称/顺序优先，锚点复用Reader
投影，不改原始事实。旧Deck及副本保留旧名称，无迁移；PDF下载自然沿用当前名称。
生成弹窗说明同步12种语言，设计取舍见[027](decisions/027-chapter-deck-source-names.md)。

## Public release preparation (036)

README中英文和公开说明从docs/README入口进入。发布准备见RELEASING与036，
当前仍MIT/0.1.0、首个候选v0.1.0-beta.1，不增加收费/账户/公网鉴权。
维护依赖后刷新DEPENDENCIES.json并核对许可；CI校验锁文件与清单，不能仅修改版本。
测试/发布需独立环境，本轮没有修改运行中实例的venv或重启生产。GitHub首发采用干净
公开快照，原始本地历史及私有操作文档保留在发布范围之外；禁止直接推送私有开发分支。

本轮发布状态见 [RELEASE_STATUS](RELEASE_STATUS.md)：公开源码已上传 PR 1，真实云端后端、前端及 amd64 容器验收/条件化安全门禁已通过；精确校验值误报修复另需云端复验。所有者设置及版本化发布仍待完成。公开分支为 `codex/public-beta`，禁止把私有准备分支连同原历史一起推送。

密钥扫描继承 Gitleaks 全部默认规则，仅允许 `container_runtime_review.json` 中已核对的准确 secrets.py 文件 SHA-256 记录；必须同时匹配文件路径和完整记录。真实或其他疑似密钥继续拒绝，脚本在扫描前验证三个负向合成用例。仅输出失败阶段，不把检测内容写入 CI 日志；完全脱敏报告留在本地。源码校验值变化须复核，不能扩大到全文件忽略。
