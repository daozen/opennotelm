import { errorKey, t, useI18n } from './i18n';
import { useEffect, useRef, useState } from 'react';
import { ArrowLeft, ArrowRight, BookOpen, ChevronDown, LoaderCircle } from 'lucide-react';
import {
  api,
  type ContentBlock,
  type ReadingBlock,
  type Source,
  type SourceNode,
  type Scope,
} from './api';
import { readingSections, sectionForNode } from './readingNavigation';

export default function Reader({
  source,
  onClose,
  initialBlockId,
  initialNodeId,
  onLocationChange,
  onAsk,
  onGenerate,
  generating,
  onTransform,
  onGenerateDeck,
}: {
  source: Source;
  onClose: () => void;
  initialBlockId?: string;
  initialNodeId?: string;
  onLocationChange?: (nodeId: string, blockId?: string, replace?: boolean) => void;
  onAsk?: (scope: Scope, label: string) => void;
  onGenerate?: (scope: Scope) => void;
  generating?: boolean;
  onTransform?: (kind: 'summary' | 'outline', scope: Scope) => void;
  onGenerateDeck?: (scope: Scope, label: string) => void;
}) {
  useI18n();
  const [nodes, setNodes] = useState<SourceNode[]>([]);
  const [blocks, setBlocks] = useState<ReadingBlock[]>([]);
  const [node, setNode] = useState('');
  const [locating, setLocating] = useState(true);
  const [reading, setReading] = useState(true);
  const loading = locating || reading;
  const [error, setError] = useState('');
  const [expanded, setExpanded] = useState(false);
  const [fontSize, setFontSize] = useState(18);
  const [pageDraft, setPageDraft] = useState('1');
  const [recognizing, setRecognizing] = useState(false);
  const content = useRef<HTMLElement>(null);
  const moved = useRef(false);
  useEffect(() => {
    // A local move already resolved this node. Canonicalizing its URL must not
    // unmount the new article and lose its scroll position or keyboard focus.
    if (!initialBlockId && initialNodeId === node && nodes.some((n) => n.id === node)) return;
    let active = true;
    setLocating(true);
    setError('');
    api<SourceNode[]>(`/sources/${source.id}/nodes`)
      .then(async (nodes) => {
        // PDF callback fragments are not useful section navigation. Page/chapter
        // scopes retain original fact nodes, including on previously imported files.
        const choices = source.type === 'pdf' ? nodes.filter((n) => n.type !== 'heading') : nodes;
        const sections = readingSections(source.type, choices);
        let first = sections[0] ?? choices.find((n) => n.type === 'page') ?? choices[0];
        first = choices.find((n) => n.id === initialNodeId) ?? first ?? choices[0];
        if (initialBlockId) {
          const all = await api<ContentBlock[]>(`/sources/${source.id}/blocks`);
          const target = all.find((b) => b.id === initialBlockId);
          first =
            source.type === 'pdf'
              ? (choices.find((n) => n.type === 'page' && n.start_page === target?.page_start) ??
                first)
              : (choices.find((n) => n.id === target?.node_id) ?? first);
        }
        if (active) {
          setNodes(choices);
          setNode(first?.id ?? '');
          if (!first) setReading(false);
          else if (first.id !== node) setReading(true);
          setLocating(false);
          if (first && first.id !== initialNodeId)
            onLocationChange?.(first.id, initialBlockId, true);
        }
      })
      .catch((e) => {
        if (active) {
          setError(e.message);
          setLocating(false);
          setReading(false);
        }
      });
    return () => {
      active = false;
    };
  }, [source.id, source.type, initialBlockId, initialNodeId]);
  useEffect(() => {
    if (!node) return;
    let active = true;
    setReading(true);
    setError('');
    api<ReadingBlock[]>(`/sources/${source.id}/reading?node_id=${node}`)
      .then((blocks) => {
        if (active) {
          setBlocks(blocks);
          setReading(false);
        }
      })
      .catch((e) => {
        if (active) {
          setError(e.message);
          setReading(false);
        }
      });
    return () => {
      active = false;
    };
  }, [source.id, node, source.updated_at]);
  useEffect(() => {
    if (loading) return;
    if (initialBlockId)
      document.getElementById(`block-${initialBlockId}`)?.scrollIntoView({ block: 'center' });
    else if (moved.current) {
      content.current?.scrollIntoView({ block: 'start' });
      content.current?.focus({ preventScroll: true });
    }
    moved.current = false;
  }, [initialBlockId, loading, blocks]);
  const currentNode = nodes.find((n) => n.id === node);
  const sections = readingSections(source.type, nodes);
  const pages = nodes.filter((n) => n.type === 'page');
  const activeSection = sectionForNode(currentNode, sections, nodes);
  const stops = sections.length ? sections : pages;
  const position = stops.findIndex((n) => n.id === (activeSection?.id ?? node));
  const previous = position > 0 ? stops[position - 1] : undefined;
  const next = stops[position + 1];
  const currentPage = currentNode?.start_page ?? 1;
  const pagePosition = pages.findIndex((p) => p.start_page === currentPage);
  const previousPage = pages[pagePosition - 1];
  const nextPage = pages[pagePosition + 1];
  const isPage = currentNode?.type === 'page';
  const wholeDocument = currentNode?.type === 'document';
  const focusedScope: Scope = wholeDocument
    ? { kind: 'source', source_id: source.id }
    : { kind: 'node', source_id: source.id, node_id: node };
  useEffect(() => {
    setPageDraft(String(currentPage));
  }, [currentPage, node]);
  function moveTo(identity: string) {
    if (identity === node) return;
    moved.current = true;
    setReading(true);
    setNode(identity);
    onLocationChange?.(identity);
  }
  function turns(location: 'top' | 'bottom') {
    if (!stops.length) return null;
    return (
      <nav
        className={`reading-turns reading-turns-${location}`}
        aria-label={t(sections.length ? '章节导航' : '翻页导航')}
      >
        <button
          className="button secondary"
          disabled={loading || !previous}
          onClick={() => previous && moveTo(previous.id)}
        >
          <ArrowLeft size={15} />
          {t(sections.length ? '上一章' : '上一页')}
        </button>
        <span>
          {sections.length
            ? (activeSection?.title ?? t('整份资料'))
            : t('第 {{v1}} 页', { v1: currentPage })}
        </span>
        <button
          className="button secondary"
          disabled={loading || !next}
          onClick={() => next && moveTo(next.id)}
        >
          {t(sections.length ? '下一章' : '下一页')}
          <ArrowRight size={15} />
        </button>
      </nav>
    );
  }

  const seen = new Set<string>();
  const rendered = blocks.map((block) => ({
    ...block,
    content: block.parts.map((part, index) => {
      const first = !seen.has(part.block_id);
      seen.add(part.block_id);
      return (
        <span
          key={`${part.block_id}-${index}`}
          id={first ? `block-${part.block_id}` : undefined}
          data-block-id={part.block_id}
          className={part.block_id === initialBlockId ? 'citation-highlight' : undefined}
        >
          {part.text}
        </span>
      );
    }),
  }));
  return (
    <section className={`reader ${expanded ? 'reader-expanded' : ''}`} aria-label={t('资料阅读器')}>
      <div className="reader-header">
        <button className="button ghost" onClick={onClose}>
          <ArrowLeft size={16} /> {t('返回对话')}
        </button>
        <span className="reader-format">
          {source.type === 'web' ? t('网页') : source.type.toUpperCase()}
        </span>
      </div>
      <div className="reading-controls">
        <label>
          {t('正文大小')}{' '}
          <select
            aria-label={t('正文大小')}
            value={fontSize}
            onChange={(e) => setFontSize(Number(e.target.value))}
          >
            <option value={16}>{t('小')}</option>
            <option value={18}>{t('标准')}</option>
            <option value={20}>{t('大')}</option>
          </select>
        </label>
        <button
          className="button ghost"
          aria-pressed={expanded}
          onClick={() => setExpanded(!expanded)}
        >
          {expanded ? t('收起阅读') : t('展开阅读')}
        </button>
      </div>
      <div className="reader-title">
        <BookOpen size={23} />
        <div>
          <h3>{source.title}</h3>
          <p>
            {pages.length ? t('原始资料 · {{count}} 页', { count: pages.length }) : t('原始资料')}
            {sections.length > 0 ? ` · ${t('{{count}} 个章节', { count: sections.length })}` : ''}
          </p>
        </div>
      </div>
      {source.type === 'web' && source.metadata?.url && (
        <p className="web-source-origin">
          <a
            href={source.metadata.final_url ?? source.metadata.url}
            target="_blank"
            rel="noopener noreferrer"
          >
            {t('打开原网页')}
          </a>
          <span>{t('导入时保存的正文快照')}</span>
        </p>
      )}
      {source.type === 'web' &&
        source.job?.type === 'source_web_images' &&
        ['queued', 'running', 'failed'].includes(source.job.status) && (
          <p className="help" role="status">
            {source.job.status === 'queued'
              ? t('网页图片正在排队处理，正文已可阅读。')
              : source.job.status === 'running'
                ? t(
                    source.job.stage === 'fetching_images'
                      ? '正在下载网页图片，正文已可阅读。'
                      : '正在识别网页图片，正文已可阅读。',
                  )
                : source.job.status === 'failed'
                  ? t('图片处理未完成，正文仍可阅读。可重试或查看失败原因。')
                  : ''}
            {source.job.status === 'failed' && ` ${t(errorKey(source.job.error_code))}`}
          </p>
        )}
      {sections.length > 0 && (
        <label className="chapter-picker">
          {t('目录 / 章节')}
          <div>
            <select
              aria-label={t('目录 / 章节')}
              disabled={loading}
              value={activeSection?.id ?? node}
              onChange={(e) => moveTo(e.target.value)}
            >
              {nodes.find((n) => n.type === 'document') && (
                <option value={nodes.find((n) => n.type === 'document')!.id}>
                  {t('整份资料')}
                </option>
              )}
              {sections.map((n) => (
                <option
                  key={n.id}
                  value={n.id}
                >{`${'　'.repeat(Math.max(0, n.depth - 1))}${n.title}`}</option>
              ))}
            </select>
            <ChevronDown size={15} />
          </div>
        </label>
      )}
      {pages.length > 0 && (
        <form
          className="reading-pages"
          aria-label={t('页码导航')}
          onSubmit={(event) => {
            event.preventDefault();
            const page = pages.find((p) => p.start_page === Number(pageDraft));
            if (page) moveTo(page.id);
          }}
        >
          {sections.length > 0 && (
            <button
              type="button"
              className="button ghost"
              disabled={loading || !previousPage}
              onClick={() => previousPage && moveTo(previousPage.id)}
            >
              {t('上一页')}
            </button>
          )}
          <label>
            {t('页码')}
            <input
              type="number"
              aria-label={t('页码')}
              min={1}
              max={pages.length}
              value={pageDraft}
              onChange={(event) => setPageDraft(event.target.value)}
            />
          </label>
          <span>{t('/ {{count}} 页', { count: pages.length })}</span>
          <button className="button ghost" disabled={loading}>
            {t('转到')}
          </button>
          {sections.length > 0 && (
            <button
              type="button"
              className="button ghost"
              disabled={loading || !nextPage}
              onClick={() => nextPage && moveTo(nextPage.id)}
            >
              {t('下一页')}
            </button>
          )}
        </form>
      )}
      {turns('top')}
      {source.metadata?.warnings?.map((warning) => (
        <p
          className="help reader-warning"
          key={
            warning.startsWith('No extractable text on pages: ')
              ? t('无法提取以下页面的原生文字：{{pages}}。可尝试识别文档图片。', {
                  pages: warning.slice('No extractable text on pages: '.length).split('. ')[0],
                })
              : warning
          }
        >
          {warning.startsWith('No extractable text on pages: ')
            ? t('无法提取以下页面的原生文字：{{pages}}。可尝试识别文档图片。', {
                pages: warning.slice('No extractable text on pages: '.length).split('. ')[0],
              })
            : warning}
        </p>
      ))}
      {onAsk && (
        <div className="reader-vision-actions">
          {(['epub', 'pdf', 'docx'].includes(source.type) ||
            (source.type === 'web' && source.metadata?.web_images_status !== 'completed')) && (
            <>
              <button
                className="button ghost"
                disabled={
                  recognizing || source.job?.status === 'running' || source.job?.status === 'queued'
                }
                onClick={async () => {
                  setRecognizing(true);
                  setError('');
                  try {
                    await api(`/sources/${source.id}/recognize-images`, { method: 'POST' });
                  } catch (e) {
                    setError((e as Error).message);
                  } finally {
                    setRecognizing(false);
                  }
                }}
              >
                {t(
                  source.type === 'web'
                    ? source.metadata?.save_images
                      ? '重新处理网页图片'
                      : '保存并识别网页图片'
                    : source.metadata?.image_failures
                      ? '重试未识别图片'
                      : '识别文档图片',
                )}
              </button>
              <p className="help">
                {t(
                  '使用已配置的语言模型读取图片和扫描页，可能产生模型服务费用。已成功识别的内容会保留。',
                )}
              </p>
              {!!source.metadata?.image_failures && (
                <p className="error" role="status">
                  {t(
                    source.type === 'web'
                      ? '{{count}} 张图片未能完成下载或识别，可重试。'
                      : '{{count}} 张图片尚未识别，可检查语言模型的图片输入能力后重试。',
                    {
                      count: source.metadata.image_failures,
                    },
                  )}
                </p>
              )}
            </>
          )}
        </div>
      )}
      {source.type === 'web' && !!source.metadata?.web_image_limit_skipped && (
        <p className="help">
          {t('{{count}} 张图片超过数量限制，未保存。', {
            count: source.metadata.web_image_limit_skipped,
          })}
        </p>
      )}
      {onAsk && (
        <div className="reader-actions">
          <button
            className="button secondary"
            disabled={!node || loading}
            onClick={() => onAsk(focusedScope, currentNode?.title ?? source.title)}
          >
            {t(wholeDocument ? '就整份资料提问' : isPage ? '就本页提问' : '就本章节提问')}
          </button>
          {!wholeDocument && (
            <button
              className="button ghost"
              onClick={() => onAsk({ kind: 'source', source_id: source.id }, source.title)}
            >
              {t('就整份资料提问')}
            </button>
          )}
          {onGenerate && (
            <>
              <button
                className="button secondary"
                disabled={generating || !node || loading}
                onClick={() => onGenerate(focusedScope)}
              >
                {t(
                  wholeDocument
                    ? '从整份资料生成知识'
                    : isPage
                      ? '从本页生成知识'
                      : '从本章节生成知识',
                )}
              </button>
              {!wholeDocument && (
                <button
                  className="button ghost"
                  disabled={generating || loading}
                  onClick={() => onGenerate({ kind: 'source', source_id: source.id })}
                >
                  {t('从整份资料生成知识')}
                </button>
              )}
            </>
          )}
          {onTransform && (
            <>
              <button
                className="button ghost"
                disabled={generating || !node || loading}
                onClick={() => onTransform('summary', focusedScope)}
              >
                {t(wholeDocument ? '总结整份资料' : isPage ? '总结本页' : '总结本章节')}
              </button>
              <button
                className="button ghost"
                disabled={generating || !node || loading}
                onClick={() => onTransform('outline', focusedScope)}
              >
                {t(wholeDocument ? '整份资料提纲' : isPage ? '本页提纲' : '本章节提纲')}
              </button>
            </>
          )}
          {onGenerateDeck && (
            <button
              className="button secondary"
              disabled={!node || loading}
              onClick={() => onGenerateDeck(focusedScope, currentNode?.title ?? source.title)}
            >
              {t(
                wholeDocument
                  ? '从整份资料生成 Deck'
                  : isPage
                    ? '从本页生成 Deck'
                    : '从本章节生成 Deck',
              )}
            </button>
          )}
        </div>
      )}
      {loading && (
        <p className="reader-status" role="status">
          <LoaderCircle className="spin" size={17} /> {t('正在打开正文…')}
        </p>
      )}
      {error && (
        <p className="error" role="alert">
          {t(error)}
        </p>
      )}
      {!loading && !error && (
        <article
          ref={content}
          tabIndex={-1}
          className="reader-content"
          dir="auto"
          style={{ fontSize }}
        >
          <p className="eyebrow">
            {currentNode?.type === 'page' && currentNode.start_page
              ? t('第 {{v1}} 页', { v1: currentNode.start_page })
              : currentNode?.title}
          </p>
          {rendered.map((block, index) => (
            <div
              key={`${block.parts[0].block_id}-${index}`}
              className={`content-block block-${block.type}`}
            >
              {block.page_start &&
                (index === 0 || blocks[index - 1].page_start !== block.page_start) && (
                  <span className="page-marker">{t('第 {{v1}} 页', { v1: block.page_start })}</span>
                )}
              {block.type === 'heading' ? (
                <h4>{block.content}</h4>
              ) : block.type === 'code' ? (
                <pre>{block.content}</pre>
              ) : block.type === 'quote' ? (
                <blockquote>{block.content}</blockquote>
              ) : block.image ? (
                <figure className="source-image">
                  {block.image.image_url && (
                    <a href={block.image.image_url} target="_blank" rel="noreferrer">
                      <img
                        src={block.image.image_url}
                        alt={block.image.alt || t('原始文档图片')}
                        loading="lazy"
                      />
                    </a>
                  )}
                  <figcaption>
                    {t(
                      block.parts.some((part) => part.text.trim())
                        ? '图片识别内容（AI），请结合原图核对。'
                        : '原始文档图片',
                    )}
                  </figcaption>
                  {block.image.original_image_url && (
                    <a href={block.image.original_image_url}>{t('下载原图')}</a>
                  )}
                  {block.image.recognition_status !== 'ready' && (
                    <p className="error">
                      {block.image.error_code
                        ? t(errorKey(block.image.error_code))
                        : t('图片尚未识别。')}
                    </p>
                  )}
                  {block.image.uncertain && (
                    <p className="help">{t('部分内容不清晰，请核对原图。')}</p>
                  )}
                  <p>{block.content}</p>
                </figure>
              ) : (
                <p>{block.content}</p>
              )}
            </div>
          ))}
          {!blocks.length && <p className="help">{t('这一章节没有可显示的正文。')}</p>}
          {turns('bottom')}
        </article>
      )}
    </section>
  );
}
