# 028 · 多语言布局校验与精确局部修复

日期：2026-10-04。基于021/027，修复art_layouts误判与修复反馈，保留事实与表达先决条件。

用户报告的15页Deck已全部authored，三轮任务、共六次DeckArt调用都因art_layouts失败，
每次同一问题重复记录两次，修复路径只有pages。报告不保存原始模型输出，不能证明
该实例的具体布局文字是什么，也不能把“描述重复”当成已生成图片重复（生图尚未开始）。

可确定的代码缺陷：原归一化仅保留a-z，把十个不同的中文布局都清空，合成复现触发
相同art_layouts。数字也全部被删除，实际列数/空间比例可能丢失。

采用Unicode NFKC/casefold，保留字母、数字和组合字符，以标点/空白分隔；
去掉明确的Page/本地页码标签，使换页号不能掩盖重复。正文空间数字保持区别。
不新增模型调用、Embedding或固定布局模板；这是描述层启发式，不能验证最终bitmap质量。

真实重复仍受ceil(count/3)上限约束。分组后保留允许数量的页面，只把超限成员的
pages[i].layout作为修复字段，反馈组内页号、次数与上限；不要求重写全部pages、
场景、媒介、配色、内容、出处。新诊断按影响页展开安全字段/数字，不导出布局原文。

structured_completion过滤validate和diagnose产生的相同FieldValidationError；
签名纳入业务reason，识别同字段的新问题。最多三次，局部有进展才进入第三次，
原样失败两次停止；不无限重试、不放松表达内容支持和原始引用约束。

已保存style/art/page/image/PDF保持冻结，旧报告不写回、不补录；未保存art的失败任务
可重试进入新校验，并复用原有15页内容。无迁移、无界面语言键或依赖变更。
验证入口：test_deck_art、test_structured、test_generation_attempts及generated-pages E2E。
具体测试、本地升级与实际模型复验边界见[ACCEPTANCE](../ACCEPTANCE.md)。
