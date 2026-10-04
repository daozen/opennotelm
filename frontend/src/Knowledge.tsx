import { t, useI18n, errorText } from './i18n';
import { useCallback, useEffect, useState } from 'react';
import { ArrowLeft, LoaderCircle, Pencil, RotateCcw, Save } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { api, type KnowledgePage } from './api';
import { CitationPreview } from './Citations';
import { useUnsavedChanges } from './NavigationGuard';

export function KnowledgeMarkdown({
  page,
  onCitation,
}: {
  page: KnowledgePage;
  onCitation: (id: string) => void;
}) {
  useI18n();
  const labels = Object.keys(page.citations);
  const text = page.content_markdown.replace(/\[\[([^\[\]\n]+)\]\]/g, (_, marker: string) =>
    page.citations[marker]
      ? `[${labels.indexOf(marker) + 1}](#citation-${page.citations[marker]})`
      : '',
  );
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      skipHtml
      components={{
        a: ({ href, children }) =>
          href?.startsWith('#citation-') &&
          Object.values(page.citations).includes(href.slice(10)) ? (
            <button
              className="citation-marker"
              aria-label={t('查看引用 {{v1}}', { v1: children })}
              onClick={() => onCitation(href.slice(10))}
            >
              {children}
            </button>
          ) : (
            <span>{children}</span>
          ),
        img: ({ alt }) => <span>{alt}</span>,
      }}
    >
      {text}
    </ReactMarkdown>
  );
}

export default function Knowledge({
  pageId,
  selectedCount,
  onBack,
  onChanged,
  onOpenSource,
  onGenerateDeck,
}: {
  pageId: string;
  selectedCount: number;
  onBack: () => void;
  onChanged: () => Promise<void>;
  onOpenSource: (sourceId: string, blockId: string) => Promise<void>;
  onGenerateDeck: () => void;
}) {
  useI18n();
  const [page, setPage] = useState<KnowledgePage | null>(null);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState({ title: '', content_markdown: '', revision: 0 });
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [citation, setCitation] = useState<string | null>(null);
  useUnsavedChanges(
    editing &&
      (submitting ||
        draft.title !== page?.title ||
        draft.content_markdown !== page?.content_markdown),
  );
  const refresh = useCallback(
    async () => setPage(await api<KnowledgePage>(`/knowledge/${pageId}`)),
    [pageId],
  );
  useEffect(() => {
    let active = true;
    const load = async () => {
      try {
        const value = await api<KnowledgePage>(`/knowledge/${pageId}`);
        if (active) setPage(value);
      } catch (e) {
        if (active) setError((e as Error).message);
      }
    };
    void load();
    const timer = setInterval(() => void load(), 1000);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [pageId]);
  const busy = submitting || (!!page?.job && ['running', 'queued'].includes(page.job.status));
  async function action(run: () => Promise<unknown>) {
    setSubmitting(true);
    setError('');
    try {
      await run();
      await refresh();
      await onChanged();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSubmitting(false);
    }
  }
  return (
    <section className="knowledge-view" aria-label={t('知识页')}>
      <div className="reader-header">
        <button className="button ghost" onClick={onBack} disabled={editing}>
          <ArrowLeft size={16} /> {t('返回对话')}
        </button>
        <span className="reader-format">{t('知识页')}</span>
      </div>
      {!page && !error && <p role="status">{t('正在打开知识页…')}</p>}
      {error && (
        <p className="error" role="alert">
          {t(error)}
        </p>
      )}
      {page && (
        <>
          <div className="knowledge-title">
            <p className="eyebrow">{t('沉淀理解 · 保留出处')}</p>
            <h2>
              {page.generation_metadata?.title_pending && !page.content_markdown
                ? t('正在生成知识页')
                : page.title}
            </h2>
          </div>
          <div className="knowledge-actions">
            {editing ? (
              <>
                <button
                  className="button primary"
                  disabled={submitting}
                  onClick={() =>
                    void action(async () => {
                      await api(`/knowledge/${pageId}`, {
                        method: 'PATCH',
                        body: JSON.stringify(draft),
                      });
                      setEditing(false);
                    })
                  }
                >
                  <Save size={14} /> {t('保存知识页')}
                </button>
                <button className="button ghost" onClick={() => setEditing(false)}>
                  {t('取消编辑')}
                </button>
              </>
            ) : (
              <>
                <button
                  className="button secondary"
                  disabled={!page.content_markdown || submitting}
                  onClick={() => {
                    setDraft({
                      title: page.title,
                      content_markdown: page.content_markdown,
                      revision: page.revision,
                    });
                    setEditing(true);
                  }}
                >
                  <Pencil size={14} /> {t('编辑')}
                </button>
                <button
                  className="button secondary"
                  disabled={busy || !page.content_markdown || selectedCount === 0}
                  onClick={() =>
                    void action(() =>
                      api(`/knowledge/${pageId}/update`, {
                        method: 'POST',
                        body: JSON.stringify({ scope: { kind: 'selected' } }),
                      }),
                    )
                  }
                >
                  <RotateCcw size={14} /> {t('用所选资料更新')}
                </button>
                <button
                  className="button secondary"
                  disabled={busy || !page.content_markdown}
                  onClick={onGenerateDeck}
                >
                  {t('生成 Visual Deck')}
                </button>
              </>
            )}
          </div>
          {busy && (
            <p className="chat-progress" role="status">
              <LoaderCircle className="spin" size={15} />
              {page.job?.stage === 'updating_knowledge'
                ? t('正在整合新资料，保留已有理解')
                : page.job?.stage === 'synthesizing_sections'
                  ? t('正在逐段理解资料')
                  : t('正在生成知识页')}
              …
            </p>
          )}
          {page.job?.status === 'failed' && (
            <div className="error">
              <p>{errorText(page.job)}</p>
              <button
                className="button ghost"
                disabled={busy}
                onClick={() =>
                  void action(() => api(`/jobs/${page.job!.id}/retry`, { method: 'POST' }))
                }
              >
                {t('重试生成')}
              </button>
            </div>
          )}
          {editing ? (
            <div className="knowledge-editor">
              <label>
                {t('知识页标题')}
                <input
                  aria-label={t('知识页标题')}
                  value={draft.title}
                  maxLength={200}
                  onChange={(e) => setDraft({ ...draft, title: e.target.value })}
                />
              </label>
              <label>
                {t('正文（Markdown）')}
                <textarea
                  aria-label={t('知识页正文')}
                  value={draft.content_markdown}
                  maxLength={200000}
                  onChange={(e) => setDraft({ ...draft, content_markdown: e.target.value })}
                  rows={20}
                />
              </label>
              <p className="help">
                {t('保留正文中的引用标记，即可继续打开原文。个人笔记可以自由补充。')}
              </p>
            </div>
          ) : (
            <article className="knowledge-content" dir="auto">
              <KnowledgeMarkdown page={page} onCitation={setCitation} />
            </article>
          )}
          <p className="knowledge-footnote">
            {t('知识页记录你的理解；引用来自原始资料。更新由你主动发起。')}
          </p>
        </>
      )}
      {citation && (
        <CitationPreview id={citation} onClose={() => setCitation(null)} onOpen={onOpenSource} />
      )}
    </section>
  );
}
