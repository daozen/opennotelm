# Verification guide / 验证指南

Release checks are available in [GitHub Actions](https://github.com/daozen/opennotelm/actions).
Use the checks for the commit or tag being evaluated; an older successful run does
not verify a newer revision. / 发布检查见 GitHub Actions，必须对应待验证的提交或标签，
不能用旧版本结果替代当前检查。

## Required checks / 必须完成的检查

| Check / 检查 | Coverage / 验证范围 |
|---|---|
| Backend / 后端 | Unit and integration tests, source identity and citation offsets, scopes, validation, cancellation, recovery, privacy; Ruff check and format. / 单测与集成测试，资料身份和引用偏移、范围、校验、取消、恢复、隐私及代码规范。 |
| Frontend / 前端 | Component tests, build, formatting, language catalogs and interpolation. / 组件测试、构建、格式、语言目录和插值。 |
| Browser / 浏览器 | Imports, reader and citation navigation, drafts, knowledge, Deck creation/editing/controls, downloads, responsive layouts and RTL. / 导入、阅读和出处导航、草稿、知识、Deck 生成编辑与控制、下载、响应式和 RTL。 |
| Container / 容器 | Fresh setup, production frontend/API, original files and encrypted keys, restart/recreation recovery, native parser/runtime versions and security gate. / 首次配置、生产前后端、原文件和加密密钥、重启重建、底层解析器及安全门禁。 |
| Release contract / 发布规范 | Public file inventory, secret scanning, DCO, locked dependency licenses, version consistency, documentation links and release assets. / 公开文件范围、密钥扫描、DCO、锁定依赖许可、版本一致、文档链接和发布附件。 |

Run the commands in [HANDOFF](HANDOFF.md) and the isolated
[Docker procedure](DOCKER_ACCEPTANCE.md). Keep runtime data, raw test outputs,
diagnostics and private cases outside Git. Record a change's verification in its
pull request: what passed, what was skipped and the relevant limitations.

执行命令见接手手册和 Docker 隔离流程。运行数据、原始输出、诊断及私有案例不提交到
仓库；在对应 PR 中说明通过的检查、跳过项目和适用限制。

## Quality and safety boundaries / 质量与安全边界

- Synthetic providers verify protocols and user flows, not the correctness, depth,
  style or image text of real model output. / 模拟模型验证协议和用户流程，不代表真实解读深度、风格或图像文字质量。
- For real-model acceptance, compare saved drafts, citations, images and exported
  PDF against authorized source material. Test provider capability and capacity
  within the authorized endpoint/document scope. / 真实模型验收须对照授权资料检查文字稿、出处、图片和 PDF，并在授权端点及资料范围内进行。
- Report browser or rendering skips explicitly. macOS requires the browser
  preflight; do not repeatedly launch a blocked browser. / 浏览器与渲染跳过须明确报告；macOS 先预检，失败后不反复启动。
- Container security decisions apply to the exact supported runtime. See
  [the review](CONTAINER_SECURITY_REVIEW.md); Python/npm audits alone do not cover
  embedded native libraries or OS packages. / 容器安全结论仅适用准确受支持配置，包审计不能代替底层库和系统包核查。

## Documentation and demo review / 文档与演示检查

Public documentation must match implemented behavior and disclose relevant product
limits. README images use the local Demo notebook in English; inspect screenshots
for credentials and unrelated user content before publication. Documentation-only
changes require link, source-scope and formatting checks; they do not require model
calls or a production restart.

公开文档须与实际功能一致并说明相关限制。README 使用本地 Demo 笔记本英文界面，发布
前检查截图中没有密钥及无关用户内容。纯文档改动检查链接、公开范围和格式，不调用模型
或重启生产服务。

Deck language regression checks cover explicit language propagation through source
understanding, brief, narrative, authoring and structural repairs, with unchanged
citations and original quotations. Backend, frontend and related browser checks
pass. Actual provider language accuracy requires authorized model verification;
there is no automatic language-identification call or script-based save gate.

Deck 语言回归覆盖理解、规划、写作和结构修复的语言传递，并保留原文和引用；
后端、前端和相关浏览器检查通过。实际服务语言准确性须在授权范围内调用模型验证，
不增加语言识别调用或以文字体系作为保存门槛。
