import { useState } from 'react';
import { Layers, Network, Headphones, Plus, Search, Trash2 } from 'lucide-react';
import ArtifactBatchDownload from './ArtifactBatchDownload';
import { type ArtifactKind } from './ArtifactDeleteDialog';
import { t, useI18n } from './i18n';
export type StudioItem = {
  id: string;
  kind: ArtifactKind;
  title: string;
  status: string;
  statusLabel: string;
  jobStatus?: string;
  summary: string;
  createdAt?: string;
  download_available?: boolean;
  resumable?: boolean;
};
export const kindLabel = (kind: ArtifactKind) =>
  kind === 'mindmap' ? t('思维导图') : kind === 'deck' ? 'Visual Deck' : 'Podcast';
const icons = { deck: Layers, podcast: Headphones, mindmap: Network };
export default function ArtifactStudio({
  notebookId,
  items,
  activeKey,
  filter,
  onFilter,
  onOpen,
  onCreate,
  onAction,
  onDelete,
  canCreate,
  compact = false,
}: {
  notebookId: string;
  items: StudioItem[];
  activeKey?: string;
  filter?: ArtifactKind;
  onFilter: (kind?: ArtifactKind) => void;
  onOpen: (item: StudioItem) => void;
  onCreate: (kind: ArtifactKind) => void;
  onAction: (item: StudioItem, action: 'stop' | 'resume') => Promise<void>;
  onDelete: (item: StudioItem) => void;
  canCreate: boolean;
  compact?: boolean;
}) {
  useI18n();
  const [query, setQuery] = useState(''),
    [state, setState] = useState('all'),
    [busy, setBusy] = useState<string>(),
    [error, setError] = useState('');
  const visible = items
    .filter(
      (i) =>
        (!filter || i.kind === filter) &&
        i.title.toLocaleLowerCase().includes(query.toLocaleLowerCase()) &&
        (state === 'all' ||
          (state === 'active'
            ? ['queued', 'running'].includes(i.jobStatus ?? '')
            : state === 'attention'
              ? i.jobStatus === 'failed' || i.jobStatus === 'cancelled' || i.status === 'partial'
              : ['ready', 'completed', 'script_ready'].includes(i.status))),
    )
    .sort(
      (a, b) => (b.createdAt ?? '').localeCompare(a.createdAt ?? '') || a.id.localeCompare(b.id),
    );
  return (
    <section className={`artifact-studio${compact ? ' compact' : ''}`} aria-label={t('产物列表')}>
      <div className="artifact-create-grid">
        {(['deck', 'podcast', 'mindmap'] as const).map((kind) => {
          const Icon = icons[kind];
          return (
            <button
              key={kind}
              className="button secondary"
              aria-label={t(
                kind === 'deck'
                  ? '生成 Visual Deck'
                  : kind === 'podcast'
                    ? '生成 Podcast'
                    : '生成思维导图',
              )}
              disabled={!canCreate}
              onClick={() => onCreate(kind)}
            >
              <Icon size={compact ? 17 : 24} />
              <span>
                <strong>
                  {t(
                    kind === 'deck'
                      ? '生成 Visual Deck'
                      : kind === 'podcast'
                        ? '生成 Podcast'
                        : '生成思维导图',
                  )}
                </strong>
                {!compact && (
                  <small>
                    {t(
                      kind === 'deck'
                        ? '将核心内容变成完整图文演示页。'
                        : kind === 'podcast'
                          ? '把资料变成可收听的解说与对话。'
                          : '梳理概念层级，展开查看关系和出处。',
                    )}
                  </small>
                )}
              </span>
              <Plus size={15} />
            </button>
          );
        })}
      </div>
      {!canCreate && <p className="help">{t('先添加资料，再开始创作。')}</p>}
      <div className="artifact-filters">
        <label className="artifact-search">
          <Search size={15} />
          <input
            type="search"
            value={query}
            aria-label={t('搜索产物')}
            placeholder={t('搜索产物')}
            onChange={(e) => setQuery(e.target.value)}
          />
        </label>
        <label>
          {t('类型')}
          <select
            aria-label={t('产物类型')}
            value={filter ?? 'all'}
            onChange={(e) =>
              onFilter(e.target.value === 'all' ? undefined : (e.target.value as ArtifactKind))
            }
          >
            <option value="all">{t('全部类型')}</option>
            {(['deck', 'podcast', 'mindmap'] as const).map((kind) => (
              <option key={kind} value={kind}>
                {kindLabel(kind)}
              </option>
            ))}
          </select>
        </label>
        <label>
          {t('状态')}
          <select
            aria-label={t('产物状态')}
            value={state}
            onChange={(e) => setState(e.target.value)}
          >
            <option value="all">{t('全部状态')}</option>
            <option value="active">{t('生成中与排队中')}</option>
            <option value="ready">{t('可查看成品')}</option>
            <option value="attention">{t('已停止或需要处理')}</option>
          </select>
        </label>
      </div>
      {error && (
        <p role="alert" className="error">
          {t(error)}
        </p>
      )}
      <p className="help">{t('{{count}} 个产物', { count: visible.length })}</p>
      <div className="artifact-grid">
        <ArtifactBatchDownload
          notebookId={notebookId}
          items={visible}
          renderItem={(item, selection) => {
            const active = ['queued', 'running'].includes(item.jobStatus ?? '');
            const Icon = icons[item.kind];
            return (
              <div
                key={`${item.kind}:${item.id}`}
                className={`deck-card artifact-card${activeKey === `${item.kind}:${item.id}` ? ' active' : ''}`}
              >
                {selection}
                <button
                  className="deck-open"
                  onClick={() => onOpen(item)}
                  aria-current={activeKey === `${item.kind}:${item.id}` ? 'page' : undefined}
                >
                  <span className="artifact-kind">
                    <Icon size={16} />
                    {kindLabel(item.kind)}
                  </span>
                  <strong dir="auto">{item.title}</strong>
                  <small>{item.summary}</small>
                  <small className={item.jobStatus === 'failed' ? 'error' : ''}>
                    {t(item.statusLabel)}
                  </small>
                </button>
                <div className="deck-card-actions">
                  {(active || item.resumable) && (
                    <button
                      className="button ghost"
                      disabled={!!busy}
                      onClick={async () => {
                        setBusy(`${item.kind}:${item.id}`);
                        setError('');
                        try {
                          await onAction(item, active ? 'stop' : 'resume');
                        } catch (e) {
                          setError((e as Error).message);
                        } finally {
                          setBusy(undefined);
                        }
                      }}
                    >
                      {t(active ? '停止生成' : item.jobStatus === 'failed' ? '重试' : '继续生成')}
                    </button>
                  )}
                  <button
                    className="button ghost danger-text"
                    disabled={!!busy}
                    aria-label={t('删除产物 · {{title}}', { title: item.title })}
                    onClick={() => onDelete(item)}
                  >
                    <Trash2 size={14} />
                    {t('删除')}
                  </button>
                </div>
              </div>
            );
          }}
        />
      </div>
      {!visible.length && (
        <div className="empty-panel">
          <Layers size={30} />
          <h4>{t(items.length ? '没有匹配的产物' : '将理解变成表达')}</h4>
          <p>
            {t(
              items.length
                ? '调整搜索或筛选条件。'
                : '选择一种产物开始创作；生成任务会在后台继续。',
            )}
          </p>
        </div>
      )}
    </section>
  );
}
