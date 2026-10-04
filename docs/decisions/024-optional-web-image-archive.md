# 024 — 网页图片可选保存与后台识别

日期：2026-10-04。用户确认实现网页图片保存，并要求导入时可选。
取代 [023](023-batch-files-word-fix-and-web-import.md) 中“网页只保留图片文字说明”的限制。

## 用户路径

“导入网页”提供默认勾选的“保存正文图片”，同一批 URL 使用同一选择。取消勾选仅保存
正文和原有 alt/caption，不下载图片或调用图片识别模型。HTTP API 的 `save_images`
缺省为 false，保留旧客户端行为；前端明确提交 true/false。说明识别可能产生模型费用。

正文先解析/索引并可阅读，随后独立的 `source_web_images` 任务下载、保存和识别图片。
仍只有一个重任务 worker；图片任务并非第二个重任务执行器。队列中其他任务按现有顺序运行。
识别使用模型设置中的“图片识别并发数”（1–20，默认 4），下载另有受限 worker 池。

阅读器提供原图预览、下载原始文件、识别内容、每张失败原因和重试。纯文字网页可显式
“保存并识别网页图片”；重复导入时勾选也能补充原有快照的图片。成功任务幂等复用；
取消勾选再次导入不会删除既有图片或取消此前已授权的任务。

## 提取与出处

正文仍走原来的 `web-v1` 解析，不改变其 block ID、文字或位置。第二次只为发现图片的
提取使用本地占位 URL，让正文提取器保留 srcset、懒加载与无扩展名 CDN 图片；不向占位
地址发请求。图片来自被提取的正文范围，不抓整页所有资源。识别相对地址、base、picture、
srcset、data-src/data-original，优先较清晰候选；过滤明确隐藏、小尺寸及部分装饰图标。
复杂页面可能仍漏图，不能承诺完整浏览器 DOM 采集效果。

图片 ID 按不可变原始 HTML 的 img 顺序稳定；附着于匹配的正文段落/章节并保持图片顺序。
补充时核对已发布正文的 ID、文字、类型、节点和位置，提取结果不同则拒绝替换正文。
图片已成功识别的文字及出处也保留，重试不重写它们。

每个成功下载保留真实原始字节、SHA-256、原/最终图片 URL、下载时间、关联位置及本地
PNG 预览。原始文件按内容去重：`media/original-<sha256>.<format>`；预览是归一化图片，
不能冒充逐字节原文件。`web-images.json` 每张原子保存 checkpoint，成功识别复用原有
`media/*.json`/共享 transcript。已保存图片不得因远程 URL 内容变化被替换；checkpoint
损坏可从发布的 metadata 恢复，原文件丢失/损坏时报告不可用而非重新抓取新版本。

正文快照 `original.html/web.json` 仍不可变，不因为补充图片或重试重新请求正文。
图片可能在正文抓取之后下载，图片时间单独记录，不能将其保证为网站同一瞬间的版本。

## 安全与资源限制

下载复用公开 URL、所有 DNS 答案验证、IP 固定连接、Host/TLS 验证和每跳重定向检查。
不携带浏览器登录态、不执行脚本、不绕过验证码/防盗链、不向浏览器输出外链 img。
支持 PNG、JPEG、WebP、GIF、AVIF，校验 MIME 和实际解码格式；拒绝 SVG/HTML 等活动内容。
GIF/动态图片保留原始文件，识别与预览取静态帧，不声称理解完整动画。

| 环境配置 | 默认值 |
|---|---|
| `MAX_WEB_IMAGES` | 每篇 50 个正文图片候选，上限可配置 200 |
| `MAX_WEB_IMAGE_BYTES` | 每张原文件 10 MiB |
| `MAX_WEB_IMAGES_BYTES` | 每篇去重后原文件合计 100 MiB |
| `WEB_IMAGE_DOWNLOAD_CONCURRENCY` | 4，可设 1–20 |
| `WEB_IMAGE_TIMEOUT` | 单张请求 20 秒，包含 DNS/跳转 |
| `WEB_IMAGES_TIMEOUT` | 一批下载 120 秒，识别不包含在此下载预算 |

归一化图片沿用 40 MP 输入上限和最长 2400px。数量超限明确提示未保存数量；超时、
过大、网站拒绝、私网 URL、坏格式、识别失败逐图记录，成功兄弟保留。失败不把已有
正文标为 source failed；metadata 的 `web_images_status=partial/failed` 与 job 状态独立。
索引配置或索引服务自身失败仍需要常规索引重试，不属于图片下载容错承诺。

## 复用与兼容

图片成为带 provenance 的 image ContentBlock，识别文字可被检索/引用；Deck 可直接读取
本地预览像素，包括没有 transcript 的图片。最终 Deck 仍是图像模型重绘页面，尚未实现
原图精确嵌入。旧资料/Deck 不自动补图、识别或重生成。

schema 保持 018；新增任务写 `jobs.source_id`，沿用删除与中断恢复语义。原图下载 API：
`GET /api/sources/{id}/media/{imageId}/original`，只按已登记内容摘要文件访问，attachment
返回原始字节，不执行内容。日志/遥测/无正文诊断只记录允许的任务类型/阶段/错误码，
不携带图片 URL、alt、原文或模型输出。

验证与生产升级证据见 [ACCEPTANCE](../ACCEPTANCE.md) 的 Optional web images。
