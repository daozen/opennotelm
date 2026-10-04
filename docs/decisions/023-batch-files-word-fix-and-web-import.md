# 023 — 多文件上传、Word 继承样式修复与网页导入

日期：2026-10-03。用户明确新增单个/批量 URL 资料入口，取代原始 v0.1 排除 Web URL 的范围；不增加 Web Search、自动爬站或 Chrome 扩展产品。

## 行为

文件选择器可多选，每批最多 50 项。前端逐项流式上传，显示成功、失败、已有资料；单项失败不阻断后续上传。失败的本地 File 可直接重试；重复资料逐项确认，不能被后一项覆盖。文件上传成功与后台解析成功是不同状态，正文解析/索引仍由现有单重任务队列完成。

网页入口提供逐行 URL 输入（最多 50），先去掉空行与完全相同的行。后端逐项规范化（去 fragment、默认端口、主机大小写），每项返回回执。有效 URL 先创建资料和持久化 source_ingest，再异步下载/解析；不在 POST 请求内等所有网页完成。网络、网站拒绝、非 HTML、超时/过大、无正文有明确错误码与重试。

正文作为普通 Source，可阅读、引用、选择生成范围及生成 Deck。标题成为 heading 树；来源链接打开原网页，界面说明阅读的是导入时快照。原始 HTML 不在浏览器中执行或直接渲染。

## Word 故障

用户报告的失败 Word（实际位于 test2）含 `basedOn` 继承样式。原实现为了查父样式调用 `defusedxml.ElementTree.Element/SubElement`，这些构造接口不存在，触发 AttributeError，再被资料任务包装成 SOURCE_PARSE_FAILED。

改为直接沿样式 ID 查找父样式，不构造 XML；循环继承有 seen 集合保护。仍用 defusedxml 读取 OOXML。保持旧位置/稳定身份规则，已解析资料不自动重建。真实文件本地解析得到 509 个内容块、2 个节点、无内嵌图片。回归覆盖正文普通继承、自定义标题继承与循环继承。

## 网页下载与事实身份

- migration 018 扩展 sources CHECK，保留所有旧表/身份/引用并恢复文件删除 trigger，增加 web URL 的部分唯一索引。
- 新资料 pending checksum 为 URL 的带前缀摘要；抓取后是规范 URL + NUL + 原始 HTML 的 SHA-256。另保存原始 HTML 的 `snapshot_sha256`，不能把 pending 摘要当文件校验。
- `original.html` 保存原始字节；`web.json` 保存原 URL/最终 URL/抓取时间/类型/原始字节摘要。先保存字节，再原子完成 manifest，构成下载 checkpoint；解析或索引失败后的重试读取该快照，不重新请求网站。
- 同一规范 URL 重复导入复用既有 Source，跨 Notebook 需确认添加；不会静默抓新版本替换已有引用。
- `WebParser` 用 Trafilatura 提取正文/元信息和结构，转成 DocumentNode/DocumentBlock；ID 按提取顺序稳定。引用来自保存的提取正文，location 指向 URL 和快照位置。
- 新依赖在 pyproject/uv.lock 固定解析版本；`web-v1` 保持已发布 block 身份。以后更换算法不能自动改历史事实/跨度。

## 网络边界与代理 DNS

只允许公开 HTTP(S)、端口 80/443；拒绝 userinfo、非 HTTP、私网/回环/链路本地/保留地址、IPv6 过渡地址。每跳重定向重新检查。DNS 一次解析并检查全部答案，把请求连接固定到已检查的 IP；Host 和 TLS SNI/证书校验仍对应原始域名。禁用环境代理、用户登录 Cookie 和自动重定向；总预算 30 秒、最多 5 次跳转、解压后 HTML 10 MiB。错误和日志不含 URL/HTML/异常原文；第三方正文提取日志关闭。

本机代理 DNS 把公网域名映射到 `198.18.0.0/15`。仅当**全部**系统答案都在此范围时，默认经固定公网地址 `1.1.1.1` 的 Cloudflare 加密 DNS 获取真实 A 记录，再检查全部答案并固定连接；不会直接连接虚拟 IP 或放开真实内网地址。只查询域名，不发送路径/参数。可设 `WEB_FAKE_IP_DNS_FALLBACK=0` 禁用这条兼容路径。协议参考 [Cloudflare 官方 DoH JSON 文档](https://developers.cloudflare.com/1.1.1.1/encryption/dns-over-https/make-api-requests/dns-json/)。

配置：`MAX_WEB_BYTES`（10 MiB）、`WEB_FETCH_TIMEOUT`（30 秒）、`WEB_FAKE_IP_DNS_FALLBACK`（1）；保留整个 Notebook 上限 50，不因批量入口扩大总容量。

## 从 notekitlm 借鉴的部分与差异

阅读了上级 notekitlm 的 `src/lib/utils/extractor.ts`、`src/offscreen/index.ts`、`src/lib/capture/PdfCaptureStrategy.ts` 和 `UrlCaptureStrategy.ts`：

1. Defuddle 先定位主正文、排除页面导航/边栏，避免抓整页 textContent。当前 Python 服务使用 Trafilatura 完成同类正文提取，参考 [官方正文/结构 API](https://trafilatura.readthedocs.io/en/latest/corefunctions.html)。
2. 将 URL 身份与采集内容一起保留，阅读时可以返回来源。
3. 采集/上传/处理分别反馈状态，批量保持每项结果。
4. 保留重试，不让单项失败覆盖成功项。

没有复制其 Google NotebookLM 私有上传协议、登录令牌或账号同步代码。它的 Chrome 扩展能读取已登录和脚本渲染后的 DOM、打印当前页；服务端 URL 输入不具备用户浏览器登录态，因此不承诺相同覆盖率。

## 当前限制

2026-10-04：[024](024-optional-web-image-archive.md) 新增可选网页原图保存与后台识别，
取代下文“只保留文字说明、不下载图片”的当时限制；正文快照/安全抓取契约继续适用。

不执行页面脚本、不携带用户登录态、不绕过验证码/付费墙，不抓 YouTube/视频、不自动跟随文章内链接。不是浏览器扩展或全页截图/PDF 采集。

HTML 正文保留图像的文字说明（alt/caption）；原始 HTML 留存图片引用，但不下载远程图片，也不将其宣称为已识图。这与已支持的 PDF/EPUB/DOCX 原图识别链路不同。图片密集网页、复杂布局或无服务端正文的页面可先保存为 PDF/Word 后上传。

验证细节见 ACCEPTANCE 的 `Batch source imports — 2026-10-03`。
