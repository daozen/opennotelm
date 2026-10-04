# Open-source AI Knowledge Workspace — V0.1 PRD

## 1. 产品定义

构建一个开源、本地优先、可自托管的 AI 知识工作台。

用户可以导入 PDF、EPUB、Markdown/TXT，通过基于原始资料的 AI 问答理解内容，将有价值的理解沉淀为 Knowledge Page，并进一步生成高质量、视觉化、便于理解吸收的 PDF Slide Deck。

产品不是通用 RAG 平台、Agent 平台或 AI PPT 模板工具。

核心价值链：

```text
Source
→ Understand
→ Chat
→ Knowledge
→ Visualize
→ PDF
```

V0.1 的首要目标是验证：

> 用户是否愿意持续把长文档放进系统，通过“结构化阅读 + 可追溯 AI 问答 + Knowledge + Visual Deck”完成知识理解和再表达。

---

# 2. 核心设计原则

1. Source 是事实来源。
2. AI 生成内容不能替代 Source。
3. 所有 Citation 最终必须回到原始 Source。
4. Chunk / Embedding 属于可重建的检索层，不是事实层。
5. Knowledge 是长期积累的理解。
6. Artifact 是面向具体任务生成的产物。
7. V0.1 唯一 Artifact 为 Visual Deck。
8. Visual Deck 不使用固定 PPT 模板。
9. 内容结构、视觉风格和页面布局由模型根据内容自主设计。
10. 整套 Deck 必须保持统一视觉语言。
11. Self-host V0.1 不要求注册账号。
12. 用户自带 AI API，系统本身不承担模型 Token 成本。

---

# 3. V0.1 用户主流程

完整成功路径：

```text
安装 Docker
↓
启动应用
↓
首次 Setup Wizard
↓
配置 Language / Embedding / Image Model
↓
创建 Notebook
↓
导入 EPUB / PDF / Markdown
↓
系统解析结构并建立索引
↓
阅读 Source
↓
选择 Sources
↓
Chat
↓
查看 Citation 并跳转原文
↓
生成 / 编辑 Knowledge Page
↓
Generate Visual Deck
↓
选择 10 / 15 / 20 页
↓
模型规划内容和整体视觉语言
↓
生成视觉页面
↓
AI 修改指定页面
↓
导出 PDF
```

---

# 4. 核心信息架构

Notebook 是用户唯一的顶层工作对象。

```text
Notebook
├── Sources
├── Knowledge
├── Chat
└── Studio
     └── Visual Deck
```

V0.1 不提供：

- Workspace
- Project
- Folder
- Team
- Organization

避免多层级对象。

---

# 5. Notebook 首页

应用启动后展示 Notebook 列表。

支持：

- Create Notebook
- Rename Notebook
- Delete Notebook
- Open Notebook

Notebook Card 可展示：

- Notebook title
- Source count
- Knowledge page count
- Visual Deck count
- Updated time

不做 Dashboard Analytics。

---

# 6. Notebook UI

桌面端参考 NotebookLM 的三栏思想。

默认布局：

```text
┌─────────────────┬────────────────────────────┬─────────────────┐
│ Sources /       │                            │ Studio          │
│ Knowledge       │           Chat             │                 │
│                 │                            │ Visual Deck     │
│ ☑ Source A      │                            │                 │
│ ☑ Source B      │ grounded Q&A + citations   │ + Generate      │
│ ☐ Source C      │                            │                 │
│                 │                            │ Generated decks │
│ + Add source    │                            │                 │
└─────────────────┴────────────────────────────┴─────────────────┘
```

左栏包含两个视图：

```text
Sources
Knowledge
```

Sources 的 checkbox 同时承担 AI Context 选择功能。

不额外设计独立的 Context Manager。

---

# 7. Source 支持范围

V0.1 支持：

### PDF

仅支持存在文本层的 PDF。

支持：

- 正文
- 页码
- 原生 Outline
- 基础 heading detection
- paragraph extraction

暂不支持：

- OCR
- 扫描 PDF
- 复杂图表识别
- 复杂图片理解

如果 PDF 基本不存在文本层，应明确提示：

```text
This PDF appears to be scanned or image-based.
OCR is not supported in this version.
```

不得悄悄解析为低质量文本。

### EPUB

EPUB 是 V0.1 重点体验。

应尽可能保留：

- TOC
- Spine
- Chapter
- Section
- heading
- paragraph
- quote
- list

用户可按章节浏览。

### Markdown / TXT

Markdown：

- H1/H2/H3 等转换为结构节点
- paragraph/list/code/table 等转换为 block

TXT：

- 以段落为基础组织

---

# 8. 明确不支持的 Source

V0.1 不做：

- Web URL
- YouTube
- DOCX
- PPTX
- Google Drive
- Notion
- Zotero
- Dropbox
- OneDrive
- OCR

---

# 9. Source Reader

点击 Source 后打开 Reader。

EPUB Reader 应展示：

- TOC / Chapter list
- 当前 Chapter
- 正文
- Chapter title
- Section hierarchy

Reader 顶部主要动作：

```text
Ask
Summarize
Create Knowledge
Generate Deck
```

不要提供大量额外 AI Buttons。

PDF 第一版可优先展示 Normalized Text Reader。

原始 PDF Viewer 可作为辅助视图，不要求 V0.1 实现精确 bbox 高亮。

---

# 10. Source Context

Source checkbox 代表 Chat / Studio 当前可使用的资料。

例如：

```text
☑ Book A
☑ Paper B
☐ Paper C
```

则 Notebook Chat 默认只能检索 Book A + Paper B。

支持以下 Scope：

- Current node / chapter
- Current source
- Selected sources
- All selected notebook sources

从 Reader 中点击 Ask 时默认使用 Current Node 或 Current Source。

---

# 11. Chat

Chat 必须 Grounded。

默认规则：

> 只依据用户当前选中的 Source 回答。

模型不应使用自身知识补全 Source 未包含的事实。

如果证据不足，应明确回复：

```text
The selected sources do not contain enough information to answer this question.
```

V0.1 不提供：

- Web Search
- General Knowledge mode
- Deep Research
- Agent Tools

---

# 12. Chat Follow-up

对于短 follow-up：

```text
那第二个原因呢？
```

Retrieval Query 默认拼接最近一次 user message：

```text
previous_user_message
+
current_user_message
```

V0.1 不增加额外 Query Rewrite LLM Call。

---

# 13. Citation

Citation 是 V0.1 的核心验收项。

LLM 只能引用系统提供的 Evidence ID，例如：

```text
[[E1]]
[[E2]]
```

模型禁止自行生成：

- 页码
- Chapter 名
- Source 名
- quote location

服务器根据 Evidence 映射到真实 Source。

最终关系：

```text
Answer
→ Citation
→ CitationSpan
→ Source ContentBlock
→ Original Source
```

Citation 禁止指向 Chunk。

---

# 14. Citation UX

Chat 中：

```text
长期复利最大的优势来自时间跨度。[1]
```

点击 `[1]` 后：

- 展示 Source title
- Chapter / Section
- Page（若有）
- 原文 quote
- Open in Source

Open in Source 应跳转 Reader 并定位相关原文。

Citation Preview 内容必须来自原始 Source，不得由 LLM 重新生成。

---

# 15. Knowledge

Knowledge 是长期知识层。

用户应明确理解：

```text
Source = 外部原始事实
Knowledge = 用户与 AI 逐渐形成的理解
```

V0.1 Knowledge 采用通用 `KnowledgePage`。

支持：

- Generate Knowledge Page
- Edit
- Update with Source
- Citation
- Generate Visual Deck from Knowledge

默认使用 Markdown 存储。

---

# 16. Knowledge 生成

入口：

```text
Generate Knowledge
```

输入 Scope 可以是：

- Current chapter
- Current source
- Selected sources

生成 Knowledge 时不能只依赖普通 Top-K RAG。

应尽可能读取完整 Scope。

长内容采用 hierarchical processing：

```text
segments / chapters
↓
local synthesis
↓
global synthesis
```

必须保留对原 Source 的 provenance。

---

# 17. Update Knowledge

已有 KnowledgePage 可以：

```text
Update with Source
```

要求模型：

1. 保留已有且仍被 Source 支持的信息。
2. 加入新 Source 的有价值内容。
3. 只有存在明确冲突时才修正旧信息。
4. 不因为新 Source 没提到旧知识就删除它。
5. 保留和更新 Citation。

V0.1 不自动运行该行为。

必须由用户主动触发。

---

# 18. V0.1 不做自动 LLM Wiki

明确不做：

- Auto concept extraction
- Auto Knowledge creation
- Auto merge
- Auto backlinks
- Auto cross-link
- Knowledge Graph
- Background knowledge maintenance
- Knowledge Agent

这些属于 V0.2。

---

# 19. Summary / Outline

Summary 和 Outline 默认是临时 AI Transformation。

例如：

```text
Summarize Chapter
```

生成结果不自动保存。

用户可以：

```text
Save as Knowledge
```

避免 Notebook 出现大量无意义 Summary 对象。

---

# 20. Studio

Studio 是 Artifact 区域。

V0.1 Studio 只包含：

```text
Visual Deck
```

展示：

```text
Generate Visual Deck

Generated
- Deck A
- Deck B
- Deck C
```

后续 Artifact 类型全部可进入 Studio，而不改变 IA。

---

# 21. Visual Deck 产品定义

Visual Deck 不是传统 AI PPT Template Generator。

目标：

> AI 根据 Source 内容自主规划一套高质量、视觉化、帮助理解和吸收的学习/研究 Deck。

最终输出：

```text
PDF
```

V0.1 不输出 PPTX。

---

# 22. Visual Deck 页数

固定三个档：

- 10 slides
- 15 slides
- 20 slides

用户不输入任意页数。

页数包含最终输出的全部页面。

---

# 23. Visual Deck 创建 UI

弹窗只提供：

```text
Scope
Length: 10 / 15 / 20
Language
Optional instruction
```

示例：

```text
Optional instruction:

重点解释作者对于长期复利的观点，
让没有金融背景的人也容易理解。
```

用户不选择：

- Template
- Theme
- Font
- Color
- Layout
- Image Style

这些由模型完成。

---

# 24. Deck 内容规划

模型负责：

- 整份 Deck 的 narrative
- 每页主要目的
- 每页核心结论
- 信息顺序
- 哪些内容需要更多视觉解释
- 哪些页面适合引用
- 哪些页面需要图片

系统不能简单把 Source 等分为 15 份。

---

# 25. Deck Style

模型必须先为整套 Deck 定义统一的视觉语言。

生成 `DeckStyleManifest`，包括：

- Design concept
- Color direction
- Typography direction
- Image direction
- Composition direction
- Visual motifs
- Density
- Consistency rules

视觉风格不能从固定模板列表中选择。

模型可根据内容自由定义。

要求：

> 单页布局可以不同，但整套 Deck 必须明显属于同一个视觉系统。

---

# 26. Slide Design

每一页的视觉设计也由模型根据内容决定。

模型可决定：

- 信息层级
- 图文比例
- 视觉焦点
- 留白
- comparison / quote / number / concept 等表现方式
- 图片需求
- 图像角色
- 页面氛围

不能要求所有页面套固定模板。

---

# 27. Visual Deck 图片生成

模型判断每页是否需要图片。

图片必须服务于：

- 理解
- 概念解释
- 视觉隐喻
- 情绪节奏
- 信息记忆

而不只是装饰。

整套 Deck 的图片必须继承 Deck-level image style。

Image Prompt 应结合：

```text
DeckStyleManifest
+
Slide visual intent
```

生成。

---

# 28. Deck 页面输出

每个 Slide 最终渲染为完整视觉页面。

最终 PDF 页面：

```text
Visual Image Layer
+
Selectable/Searchable Text Layer
```

用户看到的视觉效果接近完整图片页面。

但 PDF 中主要文字应尽可能：

- 可选择
- 可复制
- 可搜索

---

# 29. Deck Citation

Slide 内容可以绑定 Citation。

后台必须保存 Slide Claim → Citation → Original Source 的关系。

为了保持视觉干净，不强制所有 Citation 都以明显 `[1][2]` 形式占据页面。

Preview 中用户应能查看：

```text
Sources used on this slide
```

PDF 可以使用：

- 小型 source markers
- reference page
- footer

具体视觉由 Deck design 控制。

---

# 30. Deck 编辑

V0.1 不做 Canva / PowerPoint 编辑器。

支持：

- Reorder slide
- Delete slide
- Edit text
- Regenerate content
- Regenerate visual
- Regenerate image
- Revise with AI

自然语言修改示例：

```text
这一页内容太密了，减少文字，
用更直观的视觉方式解释。
```

```text
不要人物插画，
改成抽象的时间积累隐喻。
```

修改某一页不能重新生成整个 Deck。

---

# 31. Visual Deck 生成过程

用户应看到阶段性状态：

```text
Understanding sources
Planning narrative
Defining visual language
Creating slide content
Generating visuals
Rendering slides
Building PDF
```

如果 DeckPlan 已完成，可提前显示各页标题/计划。

禁止只显示长时间 Spinner。

---

# 32. AI 模型配置

用户可以选择三个全局模型：

### Language Model

负责：

- Chat
- Knowledge
- Deck Planning
- Slide Authoring
- Visual Design Planning

### Embedding Model

负责：

- Chunk Embedding
- Retrieval

### Image Model

负责：

- Visual Deck image generation

V0.1 不做 per-Notebook model override。

---

# 33. AI Endpoint

Language / Embedding 使用 OpenAI-compatible API。

不单独开发：

- OpenRouter adapter
- Ollama adapter
- Anthropic adapter
- Gemini adapter

任何兼容 OpenAI API 的 endpoint 均可尝试使用。

Image V0.1 实现 OpenAI Images API compatible adapter。

---

# 34. Setup Wizard

第一次启动：

```text
Language Model
- Base URL
- API Key
- Model

Embedding Model
- Same endpoint / custom endpoint
- API Key
- Model

Image Model
- Base URL
- API Key
- Model
```

支持：

```text
GET /models
```

发现模型。

如果 endpoint 不支持，则允许 Custom Model ID。

---

# 35. Capability Test

Setup Wizard 必须验证：

Language：

```text
Connection
Text generation
Structured JSON output
```

Embedding：

```text
Connection
Embedding output
Dimensions
```

Image：

```text
Connection
Image generation
```

不要等用户正式生成时才发现配置不可用。

---

# 36. 安装与运行

V0.1 面向 Self-host 用户。

主路径：

```text
Docker
↓
docker compose up -d
↓
http://localhost:3000
```

用户无需安装：

- PostgreSQL
- Redis
- standalone Vector DB
- Node
- Python

用户无需注册账号。

---

# 37. 数据持久化

全部数据存放在单个 `data/` 目录。

容器更新不得丢失数据。

重启应用后必须保留：

- Notebook
- Source
- Chat
- Knowledge
- Deck
- Images
- PDF
- Model config

---

# 38. Background Jobs

以下必须异步执行：

- parsing
- embedding
- knowledge generation
- deck planning
- slide authoring
- image generation
- rendering
- PDF export

长任务必须支持：

- progress
- retry
- partial success

不得因为单个 Slide 失败重新生成完整 Deck。

---

# 39. Partial Deck

例如：

```text
20 slides
18 ready
2 image generation failed
```

Deck 仍然可打开。

失败 Slide 提供：

```text
Retry
Continue without image
```

Artifact 状态：

```text
draft
generating
partial
ready
failed
```

---

# 40. Telemetry

Telemetry：

- Anonymous
- User-disableable
- Explicitly documented

允许收集：

- App version
- OS
- feature events
- source type
- duration buckets
- error codes
- slide count
- success/failure

禁止收集：

- Source content
- File names
- Chat content
- Knowledge content
- Deck content
- API keys
- Base URL
- prompts
- model responses

V0.1 可使用 PostHog anonymous custom events。

禁止：

- identify
- session replay
- autocapture
- prompt tracing

---

# 41. 安全要求

所有 Source 内容均视为不可信数据。

必须防止：

- Prompt injection being treated as instructions
- EPUB path traversal
- Zip bomb
- script execution
- malicious HTML
- external resource loading
- accidental secret logging

EPUB / Markdown HTML 必须 sanitize。

Source 内容只能作为 AI evidence，不能作为 system instruction。

---

# 42. V0.1 Non-goals

以下明确不属于 V0.1：

```text
Cloud
Accounts
Login
Sync
Teams
RBAC
SSO

Web source
YouTube
DOCX
PPTX import
OCR
Zotero
Google Drive

Web Search
Deep Research
Agents
MCP
Workflow Builder

Flashcards
Quiz
Audio
Video
Mindmap
Infographic

Auto Wiki
Knowledge Graph

PPTX export
Canva-like editor

Desktop app
Mobile app

Plugin Marketplace
```

发现新需求时默认进入后续版本，不进入 V0.1。

---

# 43. V0.1 Release Acceptance Criteria

必须能完整通过以下真实用户场景：

```text
1. 用户安装 Docker。
2. 一条主要启动命令启动应用。
3. 浏览器完成 Setup Wizard。
4. 用户选择 Language / Embedding / Image Model。
5. Capability Test 通过。
6. 创建 Notebook。
7. 上传一本 EPUB。
8. 正确识别章节结构。
9. 上传两份文本 PDF。
10. Sources 完成 indexing。
11. 用户选择部分 Sources。
12. 向 Chat 提问。
13. AI 返回 grounded answer。
14. 用户点击 Citation。
15. Citation 返回真实原文。
16. 用户针对某章节 Generate Knowledge。
17. Knowledge Page 正确保存并带 Citation。
18. 用户选择 Scope。
19. Generate 15-slide Visual Deck。
20. Deck 内容与视觉风格由模型自主规划。
21. 整套 Deck 视觉语言一致。
22. 部分 Slide 包含生成图片。
23. 用户用自然语言修改某一页。
24. 只重新生成该页需要变更的内容。
25. 导出 PDF。
26. PDF 页面视觉正确。
27. PDF 主要文字可搜索/复制。
28. 重启应用。
29. 所有数据依然存在。
```

以上流程达到稳定可用后即可发布 V0.1。

不要为了等待更多功能延期。