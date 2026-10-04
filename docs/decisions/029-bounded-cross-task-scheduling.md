# 029 · 有界跨任务调度与共享资源额度

日期：2026-10-04。基于120d5ec。用户明确接受跨任务并行优化方案，取代此前单重任务
出队执行要求；单数据目录所有者、持久SQLite队列、真实事实、停止/恢复与删除契约保留。

## 调度

一个服务进程和调度器，默认最多3个不同实体任务，界面可设1–8。无多个Uvicorn workers、
Redis/Celery、迁移或额外账号。任务仍queued/running，claim事务内预约实体/来源读写，
不同来源解析、不同Deck读同一资料可并行；source_ingest/web_images排他写，同实体操作
不交错。Deck冻结scope及Knowledge引用快照的来源参与读预约；旧scope回退Notebook来源。
更早读写/同实体队列预约阻止后续绕过；可运行任务按source/deck/interactive类别轮换，
防止100份Deck批次占用所有新空位。总额度降低不取消现有执行。

取消先持久化，execution直到join完成仍占预约；取消已在清理的task不二次打断。
shutdown join全部任务，意外中断及尚未开始协程的running恢复queued/resuming，主动停止
保持cancelled。解析使用joined_thread，文件删除不会与遗留解析线程竞争。

## 请求和准备

模型设置新增每个服务总请求额度，默认8、可设1–20；按scheme/hostname/effective-port
归组，语言/识图/Embedding/图像API及不同路径共享预算。不同DNS别名不自动合并，也
不冒充RPM/TPM配额。等待按job轮流授予；取消等待、刚获授权时取消、正常/异常返回都
释放预约。ImagesAdapter与ModelGateway共享入口，图片下载/校验完成才释放额度。
改变总请求额度对后续授予生效，已发请求不会中断。诊断耗时可能包括本地额度等待。

固定内部worker仍按任务初始三项配置限制；SharedStageBudget进一步约束跨任务的识图
解码/附图准备/分段理解/author/渲染/网页下载。每类并发不超过参与运行的快照最大值，
不相加。这样不会出现多份任务各自20张图片同时解码的内存倍增。分段理解和author共享
内容准备预算；其他独立准备类各有额度，服务总请求限制在其下游仍有效。

## 去掉多余等待

- 前端上传固定3个worker，各行成功/失败/重复/重试独立，允许后台解析与上传重叠。
- Embedding固定2批，每批32项；按原输入顺序聚合，完成校验后一次事务替换索引。
  任一批失败/取消均join兄弟，原索引保持，不发布缺失向量。
- 网页download保存原图并checkpoint后将(index,image)送入识别ready队列，下载deadline
  只覆盖下载池；识别可在后续图片仍下载时进行。队列长度受该资料图片数（最多200）
  与原有总字节预算限制，结束sentinels关闭；共同TaskGroup取消join，文章事实及原图
  重试不可重新fetch HTML或替换远端变化字节的契约保留。
- 父书read按source单飞、锁内重查签名缓存。followers独立可取消，leader取消后后续
  任务可以使用自己的持久checkpoint接续；不留下脱离job的后台模型任务。

PDFium页栅格化保留安全锁；整套art需要全部文字，最终PDF依赖全部页面，仍有真实
前后依赖。没有通过删锁、预先生图或取消整套多样性校验换速度。旧art/spec/image/PDF
及其签名冻结，所有优化都复用既有资料与成功检查点；无新增提示内容规则。

测试入口：test_parallel_jobs、test_deck_context、test_web_images、原并发/生命周期检查，
SourceImport/TaskSettings单测与model-settings/source-import/deck-batches/deck-lifecycle E2E。
实际验证、本地更新及性能结论范围见[ACCEPTANCE](../ACCEPTANCE.md)。
