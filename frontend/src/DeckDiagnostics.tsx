import { useState } from 'react';
import { api } from './api';
import { t, useI18n, errorText } from './i18n';

type Issue = {
  code: string;
  path: (string | number)[];
  max_length?: number;
  min_length?: number;
  actual_length?: number;
};
type Attempt = {
  id: number;
  job_id: string;
  stage: string;
  created_at: string;
  subject_id?: string;
  outcome: string;
  attempt: number;
  elapsed_ms: number;
  error_code?: string;
  http_status?: number;
  finish_reason?: string;
  completion_tokens?: number;
  issues: Issue[];
  field_paths: (string | number)[][];
};
type Report = {
  jobs: { id: string; status: string; stage: string; error_code?: string; retry_count: number }[];
  slides: { id: string; page: number; error_code?: string }[];
  attempts: Attempt[];
  omitted_attempts: number;
};
const stages: Record<string, string> = {
  MindMapTree: '梳理概念关系',
  mindmap: '理解资料',
  mindmap_reading: '理解资料',
  mindmap_mapping: '梳理概念关系',
  mindmap_exporting: '准备导出',
  DeckPreferences: '理解生成要求',
  DeckBrief: '确定内容目标',
  DeckPlan: '规划叙事',
  DeckStyleManifest: '定义视觉语言',
  AdaptiveDeckStyle: '定义视觉语言',
  SlideSpec: '创作逐页内容',
  DeckArt: '编排整套视觉',
  deck: '理解资料',
  work_context: '理解全书背景',
  image_generation: '生成图片',
  understanding: '理解资料',
  planning: '规划叙事',
  styling: '定义视觉语言',
  authoring: '创作逐页内容',
  art_directing: '编排整套视觉',
  generating_assets: '生成图片',
  rendering: '渲染页面',
  exporting: '制作 PDF',
  revising: '修改页面',
};
const reasons: Record<string, string> = {
  citation_basis: '背景知识或类比错误地附带原文出处',
  source_only: '内容超出用户限定的原文范围',
  literal_error: '模型使用了不支持的选项值',
  missing: '缺少必要字段',
  extra_forbidden: '包含不支持的字段',
  string_too_long: '文字字段超过长度限制',
  string_too_short: '文字字段过短',
  too_long: '条目数量超过限制',
  too_short: '条目数量不足',
  copy_budget: '页面文字超过阅读预算',
  evidence: '引用了未提供的原文出处',
  json_invalid: '模型返回的 JSON 不完整或格式错误',
  element_items: '列表或对比缺少结构化条目',
  element_text: '内容元素缺少文字',
  element_ids: '内容元素编号重复',
  hierarchy_reference: '视觉层级引用了不存在的内容元素',
  relationship_reference: '关系指向不存在的内容元素',
  relationship_cycle: '关系不允许指向自身',
  asset_ids: '图片请求编号重复',
  relationship_ids: '关系编号重复',
  citation_missing: '原文事实或解读缺少出处',
  quote_basis: '引文没有标记为原文',
  editorial_notes: '包含未要求的解释性标签',
  art_order: '视觉编排的页数或顺序不正确',
  art_unsupported_form: '页面内容不支持选用的视觉表达',
  art_variety: '视觉表达种类不足',
  art_adjacency: '相邻页面的视觉表达重复',
  art_frequency: '同一种视觉表达使用过多',
  art_viewpoints: '观察角度变化不足',
  art_placements: '文字布局变化不足',
  art_framing: '连续多页构图重复',
  art_layouts: '空间布局描述重复',
  semantic: '内容规则未通过校验',
  field_constraint: '字段内容未满足约束',
};
export default function DeckDiagnostics({
  deckId,
  failed = true,
  kind = 'deck',
}: {
  deckId: string;
  kind?: 'deck' | 'mindmap';
  failed?: boolean;
}) {
  const uiLanguage = useI18n();
  const [open, setOpen] = useState(false);
  const [report, setReport] = useState<Report>();
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  async function load() {
    setLoading(true);
    setError('');
    try {
      setReport(
        await api<Report>(`/${kind === 'deck' ? 'decks' : 'mindmaps'}/${deckId}/diagnostics`),
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }
  return (
    <section className="deck-diagnostics">
      <button
        className="button secondary"
        aria-expanded={open}
        onClick={() => {
          setOpen(!open);
          if (!open) void load();
        }}
      >
        {t(open ? '收起生成记录' : failed ? '查看失败详情' : '查看生成记录')}
      </button>
      {open && (
        <div className="diagnostic-report" role="region" aria-label={t('失败详情')}>
          <p className="help">
            {t(
              kind === 'deck'
                ? '包含本 Deck 的历史尝试；校验失败后修复成功的记录也会保留。报告不含原文、提示词或密钥。'
                : '包含本导图的生成记录，不含原文、自定义说明或密钥。',
            )}
          </p>
          <div className="button-row">
            <button className="button secondary" disabled={loading} onClick={() => void load()}>
              {t('刷新详情')}
            </button>
            <a
              className="button secondary"
              href={`/api/${kind === 'deck' ? 'decks' : 'mindmaps'}/${deckId}/diagnostics?download=true`}
              download={`${kind}-diagnostics.json`}
            >
              {t(kind === 'deck' ? '下载本 Deck 诊断报告' : '下载导图诊断报告')}
            </a>
          </div>
          {loading && <p role="status">{t('正在读取诊断记录…')}</p>}
          {error && <p role="alert">{t(error)}</p>}
          {report && (
            <>
              {report.jobs
                .filter((j) => j.error_code)
                .map((j) => (
                  <p key={j.id}>
                    <strong>{t(stages[j.stage] ?? '任务处理')}</strong> · {errorText(j)}{' '}
                    <code>{j.error_code}</code>
                    {' · '}
                    {t('手动重试 {{count}} 次', { count: j.retry_count })}
                  </p>
                ))}
              {(report.slides ?? [])
                .filter((s) => s.error_code)
                .map((s) => (
                  <p key={s.id}>
                    {t('第 {{page}} 页', { page: s.page })} · {errorText(s)}{' '}
                    <code>{s.error_code}</code>
                  </p>
                ))}
              {!report.attempts.length && (
                <p>{t('该任务没有详细尝试记录。旧任务无法补录；再次重试后会记录新的失败详情。')}</p>
              )}
              <ol className="diagnostic-attempts">
                {report.attempts.slice(0, 50).map((a) => {
                  const slide = (report.slides ?? []).find((s) => s.id === a.subject_id);
                  return (
                    <li key={a.id}>
                      <strong>
                        {t(stages[a.stage] ?? '任务处理')}
                        {slide && ` · ${t('第 {{page}} 页', { page: slide.page })}`}
                      </strong>
                      <p>
                        {t(
                          a.outcome === 'valid'
                            ? '校验通过'
                            : a.outcome === 'visual_cache_hit'
                              ? '复用已保存理解'
                              : a.outcome === 'request_failed'
                                ? '模型请求失败'
                                : '校验失败',
                        )}
                        {' · '}
                        {t('第 {{attempt}} 次尝试 · {{seconds}} 秒', {
                          attempt: a.attempt,
                          seconds: new Intl.NumberFormat(uiLanguage, {
                            minimumFractionDigits: 1,
                            maximumFractionDigits: 1,
                          }).format(a.elapsed_ms / 1000),
                        })}
                      </p>
                      <small>
                        {a.created_at ? new Date(a.created_at).toLocaleString(uiLanguage) : ''}
                      </small>
                      {a.error_code && (
                        <p>
                          {errorText(a)} <code>{a.error_code}</code>
                          {a.http_status && ` · HTTP ${a.http_status}`}
                        </p>
                      )}
                      {a.finish_reason === 'length' && <p>{t('模型输出达到上限，可能被截断')}</p>}
                      {a.issues?.map((issue, i) => (
                        <p key={i}>
                          {t(reasons[issue.code] ?? '返回字段的类型或取值不符合要求')}
                          {issue.path.length > 0 && (
                            <>
                              {' '}
                              {['pages', 'slides'].includes(String(issue.path[0])) &&
                                typeof issue.path[1] === 'number' &&
                                ` · ${t('第 {{page}} 页', { page: issue.path[1] + 1 })}`}
                              · <code>{issue.path.join('.')}</code>
                            </>
                          )}
                          {issue.actual_length !== undefined &&
                            ` · ${t('实际 {{count}}', { count: issue.actual_length })}`}
                          {issue.max_length !== undefined &&
                            ` · ${t('上限 {{limit}}', { limit: issue.max_length })}`}
                          {issue.min_length !== undefined &&
                            ` · ${t('下限 {{limit}}', { limit: issue.min_length })}`}
                        </p>
                      ))}
                      {a.outcome === 'invalid' && !a.issues?.length && (
                        <p>
                          {t('旧记录仅保存了校验类别，未保存具体规则。')}
                          {a.field_paths?.map((p, i) => (
                            <code key={i}> {p.join('.')} </code>
                          ))}
                        </p>
                      )}
                    </li>
                  );
                })}
              </ol>
              {(report.attempts.length > 50 || report.omitted_attempts > 0) && (
                <p className="help">{t('页面显示最近 50 次，下载报告最多包含最近 500 次尝试。')}</p>
              )}
            </>
          )}
        </div>
      )}
    </section>
  );
}
