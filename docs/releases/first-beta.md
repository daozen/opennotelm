# OpenNoteLM — first public Beta / 首个公开 Beta

## English

A self-hosted MIT workspace for reading sources, asking cited questions, saving
knowledge and generating illustrated Visual Decks. Bring your own language,
embedding and image services; no account or bundled paid keys are required.

- Batch EPUB/PDF/DOCX/Markdown/text and public web imports, optional web images and OCR.
- Real chapter trees, source-linked answers and source-grounded knowledge pages.
- Combined or separate chapter/source Decks, automatic uploaded-book context,
  content-adaptive visual direction, stop/resume and safe failure details.
- Page revision, source manifests, naming, lossless PDF optimization and batch ZIPs.
- Twelve interface/output languages and browser-derived first-use language.

[Install and back up](../DEPLOYMENT.md) · [User guide](../USER_GUIDE.md) ·
[Security](../../SECURITY.md) · [Privacy](../PRIVACY.md) · [License](../../LICENSE)

This is a single-user Beta with **no built-in authentication**. Do not expose it
directly to the internet. Relevant content goes to your configured model services.
Generated image text/charts may be wrong; inspect the draft and source. Default
image PDFs are not searchable/selectable text. Tests using synthetic providers
verify contracts and flows, not real-model quality. Back up the complete data
directory and encryption master key before upgrading; one process owns each directory.

Prebuilt images are usable after publishing and making the GHCR package public.
Use the recorded version/digest. Source, dependency notices, unmodified file-copyleft
dependency sources and checksums are attached. Container SBOM/provenance is attached
to the image manifest.

## 简体中文

采用 MIT 的自托管知识工作台：阅读资料、带出处问答、保存知识并生成图文 Deck。
自备语言、Embedding 和图片模型服务，无需账号，没有内置付费密钥。

- EPUB/PDF/DOCX/Markdown/TXT 批量导入、公开网页、可选原图和 OCR。
- 真实章节树、返回原文的问答出处，以及以资料为依据的知识页。
- 合并或逐资料/章节生成 Deck，自动全书背景、内容自适应视觉、停止/继续和失败详情。
- 单页修改、来源清单、命名、PDF 无损优化和批量 ZIP。
- 12 种界面/输出语言，首次匹配浏览器语言。

[安装与备份](../DEPLOYMENT.zh-CN.md) · [使用指南](../USER_GUIDE.zh-CN.md) ·
[安全](../../SECURITY.zh-CN.md) · [隐私](../PRIVACY.zh-CN.md) · [许可](../../LICENSE)

当前是**没有内置鉴权的单用户 Beta**，不要直接暴露公网。相关内容会发送到配置的模型。
图片中文字/图表可能错误，请核对文字稿和原文；默认图片 PDF 无可搜索/选择文字层。
测试模型验证契约和流程，不保证真实模型质量。升级前备份完整数据与主密钥，每目录一个进程。

镜像需在版本发布且 GHCR 包公开后才能使用，请固定记录的版本/digest。
附件含源码、依赖声明、原样文件级 copyleft 依赖源码与校验值；镜像清单带 SBOM/来源证明。
