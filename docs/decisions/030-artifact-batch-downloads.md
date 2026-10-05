# 030 · 产物批量下载

日期：2026-10-04。用户要求Deck批量下载，后续其他artifact采用相同能力。

## 产品契约

演示文稿列表提供“批量下载”，进入选择模式、多选/全选已有当前PDF的Deck，再下载
一个ZIP。仅空闲、所有页面版本匹配且当前PDF已保存的Deck可选；不自动导出、重试、
生图或调用模型。不按Deck的ready状态独自判断，缺文件/修订过期不可选。
所选集合任一项已删除、属其他笔记本、忙碌、过期或损坏时整体拒绝，明确显示可操作
原因；不偷偷遗漏项目或用旧PDF凑齐。取消选择不停止生成任务。

PDF保持原字节、以打包时当前Deck名称命名，沿用单份下载的文件名安全规则。
Unicode规范化/大小写等价重名加“ (2)”等序号，不覆盖，按所选列表次序打包。
ZIP使用笔记本名称，不加入原始资料、密钥、诊断或额外说明文件。
每次1–100份、ZIP不超过512MiB；超限要求分批。界面保留未自动启动时的下载链接。
12套界面语言覆盖选择、打包、限额及错误，保留选中状态和原文标题。

## 实现与扩展

`ArtifactBatchDownload`复用选择/请求/下载交互；`ArtifactDownloadService`注册kind到
文件适配器，`SavedArtifact`只提供已保存文件的path/name/checksum。当前只有deck适配器；
未来新增产物需明确其下载格式/归属/当前版本校验，扩展ArtifactRef/UI kind并注册适配器，
其他产物、导出格式及 Knowledge 下载尚不在当前范围。

POST `/notebooks/{id}/artifacts/download`接收items[{kind,id}]，严格类型/ID/数量/去重，
完成校验和打包后返回download_url/filename。GET `/artifact-downloads/{token}/file`
由浏览器直接下载并支持Range，不让网页fetch整个ZIP并占用移动设备内存。
列表增加download_available；复用同一SQLite连接及PDF签名读取，无每次轮询整文件哈希。
打包流式复制并验证SHA256，ZIP_STORED避免对已压缩PDF重复耗CPU；无迁移或依赖变更。

同时最多两次打包，本进程临时目录最多32个/总1GiB已完成包，最长30分钟过期、每分钟清理；
连续批次需要空间时提前回收最旧的空闲包，不让用户等待30分钟；已有下载中的包不回收。
含两次正在打包的512MiB上限，临时占用有界约2GiB。下载中不回收；关闭清理全部，
重启后临时链接失效但原PDF仍可重新打包。临时包不是持久artifact，无恢复job。
实体锁按“Notebook→排序后的产物ID”取得，打包线程取消必须join后释放/清理，
文件传输期间持锁，避免删除与读文件竞争；关闭pathsend延迟交付，确保响应退出已送完。
Deck/Notebook删除清理其所有临时包，Notebook删除也使用相同Notebook锁。
已打包包的名称/字节为请求快照，后续改名/修改不重写它；新请求读取新名称/当前版本。
原始资料、PDF/art签名、停止/继续、生成队列和模型接口保持现有契约。

验证与部署记录见[ACCEPTANCE](../ACCEPTANCE.md)。
