# 026 · Deck 来源清单、名称与 PDF 文件名

日期：2026-10-04。增量于025，不改变整页生成、队列与原文引用规则。
后续[027](027-chapter-deck-source-names.md)细化新建单章节的来源命名格式；其余契约保留。

## 行为

- 创建时冻结资料名、选定章节及目录路径、知识页名与修订版本。
  整份资料显示真实章节目录；知识页来源还列出引用所指向的原始资料与章节。
  来源清单按需展开，资料与章节可跳转阅读，知识页可打开当前页面。
- 默认名称仍由模型拟定；可选沿用资料或单章节名称。限制按每份Deck校验，
  不是按整个批次：合并多份来源不允许，分别生成允许各自命名。
  选中父目录含子树算一个范围；知识页不是该名称选项的资料/章节。
- 所有闲置Deck可重命名；排队/生成/修改中的Deck需先停止或等待完成。
  名称修改不改变页面标题、图像、引用、修订号或已有PDF字节。
- 下载文件名使用当前Deck名称，保留Unicode，替换路径/控制字符、处理系统保留名和长度；
  下载与浏览器预览均采用标准Content-Disposition，预览使用inline。

## 数据与兼容

migration019新增 `title_mode`（auto/source/custom）、`export_title`、`source_manifest_json`。
名称策略不放在会被生成阶段替换的generation_metadata内。创建先验证冻结scope，
再在原事务内记录manifest、Deck/job。模型brief只在auto模式更新显示与导出标题。
副本保留名称策略与来源快照；重写内容副本也尊重用户改名。

`export_title`在升级时复制原title，保留image-aligned-text-v2签名计算结果。
重命名后仍用该稳定值校验已生成PDF；HTTP文件名从当前显示title读取，
不触发模型调用或重制文件。仍未规划且无导出记录的停止任务改名时同步export_title。
实际页面修订仍正常使PDF过期，不因标题分离跳过产物校验。

GET `/api/decks/{id}/sources` 返回冻结名称以及当前available标记；
PATCH `/api/decks/{id}` 接受trim后非空、最多1000字符的title。
新标题必须在实体锁及BEGIN IMMEDIATE下检查jobs，防止恢复/删除竞态。
manifest不是引用事实层；CitationSpan offsets与ContentBlock身份没有改动。
章节背景标记来自实际保存的whole_work_readings，不声称模型引用了书中所有章节。

旧Deck没有manifest：从保存scope、knowledge_snapshot及理解evidence、仍保留资料还原，
标记historical并在界面说明，不写回数据库、不假装还原生成时的旧资料名称。
原资料或知识页不再可用时保留已冻结名称，禁用跳转。知识页按钮打开当前版本，
清单明确记录生成时的版本。无书签PDF不把页面当目录。
旧批量回执没有title_mode时等价auto，避免升级后原请求重试误报冲突。

## 验证入口

`test_deck_identity.py`覆盖名称策略、批量限制、冻结路径/版本、旧回执、
停止改名继续、来源不可用、副本、019迁移和PDF字节/签名/Unicode文件名。
CreateDeck/Deck/DeckSources单测覆盖选项限制、按需加载、失败重试、语言切换草稿和改名。
Deck batches浏览器流程覆盖PDF书签、跳转阅读、刷新保留名称、平板布局及真实下载文件名。
验证结果与本地升级证据见[ACCEPTANCE](../ACCEPTANCE.md)最新阶段。
