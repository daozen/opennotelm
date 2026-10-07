# 参与 OpenNoteLM

[English](CONTRIBUTING.md)

欢迎问题反馈、文档、翻译和聚焦的代码贡献。较大的范围调整请先通过 Issue 讨论。
复现请使用自编资料和安全错误码；漏洞走[安全报告](SECURITY.zh-CN.md)，
社区遵循[行为准则](CODE_OF_CONDUCT.zh-CN.md)。

## 授权与签署

贡献按 MIT 接收，作者保留版权，目前不要求 CLA 或版权转让。
每个贡献提交应带 [DCO 1.1](https://developercertificate.org/) 签署，确认有权提交：

```sh
git commit -s -m "fix: explain the concrete change"
```

签署行是 `Signed-off-by: Your Name <your-email>`。使用你愿意公开的姓名和邮箱。
DCO 是权利确认，不是版权转让；纯依赖机器人提交豁免，但维护者仍核对许可变化。
详见[许可与商业使用](docs/LICENSING.zh-CN.md)。

## 开发与验证

支持 Python 3.12、uv、Node.js 24。先检查 Git 状态，保留他人改动，使用聚焦分支；
coding agent 新分支使用 `codex/` 前缀。从根目录：

```sh
uv sync --locked
uv run playwright install chromium
```

在 `frontend/` 执行 `npm ci` 和 `npm run build`。回到根目录启动隔离实例：

```sh
task_data_dir=$(mktemp -d)
DATA_DIR="$task_data_dir" uv run uvicorn opennotelm.main:app \
  --app-dir backend --host 127.0.0.1 --port 4304 --no-access-log
```

打开 http://127.0.0.1:4304。需要前端热更新时，另一个终端在 `frontend/`：

```sh
OPENNOTELM_API_PROXY=http://127.0.0.1:4304 npm run dev -- --port 5174 --strictPort
```

自动测试使用临时数据和 `backend/tests/` 的测试模型，不使用真实资料或付费服务。
根目录检查：

```sh
uv run ruff check .
uv run ruff format --check .
uv run pytest -q
git diff --check
```

`frontend/` 检查：

```sh
npm test
npm run build
npm run format:check
npx playwright install chromium
npm run test:e2e
```

Linux 浏览器/PDF 检查需要系统库、Poppler 和 Noto 字体。macOS 先运行
`uv run python tools/browser_check.py`，失败立即停止，不反复启动个人浏览器。
受限环境先跑 `pytest -m 'not browser'`，随后在允许浏览器启动的环境补验。
打包变更必须跑 `bash tools/docker_acceptance.sh`，使用隔离数据和 4303 端口；
不要重叠执行共用输出目录的原生与容器浏览器检查。诚实记录跳过项与限制，
模拟服务验证协议和用户流程，不验证真实模型的内容和视觉质量。

## 提交要求

- 描述具体问题、修改后的行为和验证结果，不用测试通过代替人工评审。
- 保留原文件、ContentBlock 身份、精确出处偏移、旧产物签名和成功检查点。
- 对行为、安全或数据完整性补充有意义的回归；迁移有序新增，不修改已应用迁移。
- 保持锁文件、12 种翻译及插值对齐，保留用户草稿。
- 不记录或提交真实资料、密钥、数据库、原始提示/响应、私有地址。
- 行为变更同步相关公开使用/部署说明，在 PR 中提供验证结果；内部调研与操作记录不要公开。

新 Deck 默认整页图片，旧原生 Deck 保持兼容。资料与模型输出是非可信数据。
同一数据目录只能由一个进程持有，并发使用已有有界调度器，不增加服务 workers。
账户、Agent、PPTX 等不作为顺带扩展的范围。

维护者按范围、出处、恢复、许可和验证评审；支持为尽力而为，不承诺 SLA。
