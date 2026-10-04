# 隐私与诊断数据

[English](PRIVACY.md)

资料和产物存于本地数据目录。AI 功能向部署者配置的模型地址发送所需证据、
说明和相关已存内容；完全离线需要本地模型。

## 诊断

设置下载报告含应用/系统/解析器版本、资料类型计数、模型 ID、最多100条任务和
100条生成尝试，以及最近50个回答的检索汇总分数。尝试记录包含阶段、耗时、结果/
次数、白名单校验分类/字段、图片数和安全 token/结束元数据，未知字段和拒绝值排除。
Deck失败详情/生成记录仅包含该 Deck 的任务、页状态和最多500条尝试，界面显示50条；
可刷新和下载，旧记录中未保存的细节无法补录，不是完整服务请求追踪。

不含文件名、标题、正文、问题、提示词、模型响应、服务 URL、密钥、原始日志或数据库。
未知错误变为 UNKNOWN_ERROR，分享前仍请检查；下载不会自动上传支持服务。
本地任务日志仅记录事件、阶段、随机实体 ID、安全错误码、耗时和版本。
自动框架追踪/指标/日志出口和 OTLP 环境自动设置已禁用；生产关闭访问日志，
无浏览器分析 SDK、回放、自动采集或提示追踪。

## 可选匿名统计

默认关闭。用户可在设置保存参与选择；关闭清空待发事件并阻止后续发送，
已开始发送的请求可能已到接收端。模型配置与统计独立。

事件白名单：app_started、source_import_started/completed/failed、chat_message_sent、
chat_response_completed/failed、knowledge_generated/updated、deck_generation_started/
completed/failed、slide_regenerated/revised、pdf_exported、model_connection_tested。
业务字段仅资料类型、文件大小分桶、页数、耗时分桶和已知错误码，发送端补版本/系统族。
耗时按1秒/10秒/1分/5分/1小时/1天分桶，大小按小于1MiB/1–10/10–50/50MiB以上。
不发资料、笔记本、页或任务 ID。随机安装 UUID 只在本地生成，非硬件/邮箱/IP/密钥派生。

入队和发送均校验，最多1000事件/7天，每批50条，重试1分钟至1小时且 UUID 保持；
关闭期间不补采，网络失败不影响业务，模型凭据/Cookie不共用，拒绝重定向。

## 自托管接收配置

没有内置项目 token。希望接收统计的部署者自行提供 PostHog
`TELEMETRY_PROJECT_TOKEN`，可指定 `TELEMETRY_HOST`（默认 https://us.i.posthog.com）。
支持 EU/自托管 HTTPS，测试允许回环 HTTP。修改后重启并明确开启用户选择。
无 token 也可保存参与选择，但不会发送，队列仅有界本地暂存；使用应用无需 PostHog。
使用项目公开 ingestion token，不是个人管理 API Key。

发送遵循 [PostHog batch API](https://posthog.com/docs/api/capture)，
设置 `$process_person_profile: false` 与 `$geoip_disable: true`，不发 identify/group/alias。
接收端必然看到网络请求，不承诺网络层匿名。英文版提供完整技术链接。
