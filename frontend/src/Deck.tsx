import Modal from './Modal';
import { languages, t, useI18n, errorText } from './i18n';
import { useCallback, useEffect, useRef, useState } from 'react';
import {
  ArrowLeft,
  ChevronLeft,
  ChevronRight,
  Maximize2,
  Minimize2,
  Layers,
  LoaderCircle,
  X,
} from 'lucide-react';
import {
  api,
  type Deck,
  type DeckScope,
  type KnowledgePage,
  type Source,
  type SlideElement,
  type Slide,
} from './api';
import { CitationPreview } from './Citations';
import SlideEditor from './SlideEditor';
import ChapterSelection from './ChapterSelection';
import DeckDeleteDialog from './DeckDeleteDialog';
import DeckDiagnostics from './DeckDiagnostics';
import DeckSources from './DeckSources';
import DeckRenameDialog from './DeckRenameDialog';
import ArtifactInstructions from './ArtifactInstructions';
import ArtifactInstructionDetails from './ArtifactInstructionDetails';

export const deckStatus: Record<string, string> = {
  understanding: '理解资料',
  planning: '规划叙事',
  styling: '定义视觉语言',
  authoring: '创作逐页内容',
  art_directing: '编排整套视觉',
  generating_assets: '生成图片',
  rendering: '渲染页面',
  exporting: '制作 PDF',
  revising: '修改页面',
  draft: '草稿',
  partial: '部分完成',
  ready: '已完成',
  failed: '生成失败',
  paused: '已停止',
  queued: '等待生成',
  resuming: '继续生成',
};

const visualForms: Record<string, string> = {
  immersive_scene: '沉浸场景',
  editorial_collage: '编辑式拼贴',
  object_annotation: '对象特写',
  cutaway_layers: '剖面展示',
  spatial_atlas: '概念地图',
  comparison_stage: '并置对照',
  sequential_panels: '分镜过程',
  branching_journey: '分支路径',
  relationship_constellation: '关系图解',
  typographic_poster: '文字重点',
  evidence_quote: '引文特写',
  numeric_evidence: '数字重点',
  synthesis_landscape: '综合全景',
};
const readingSurfaces: Record<string, string> = { light: '浅色', dark: '深色', mid_tone: '中间色' };

export function CreateDeck({
  notebookId,
  initialScope,
  initialLabel,
  initialLanguage,
  sources,
  pages,
  onClose,
  onCreated,
}: {
  notebookId: string;
  initialScope: DeckScope;
  initialLabel: string;
  initialLanguage?: string;
  sources: Source[];
  pages: KnowledgePage[];
  onClose: () => void;
  onCreated: (deck: Deck, count?: number) => void;
}) {
  const uiLanguage = useI18n();
  const options: { key: string; label: string; scope: DeckScope }[] = [
    {
      key: 'selected',
      label: t('所选资料（{{v1}} 份）', { v1: sources.filter((s) => s.enabled).length }),
      scope: { kind: 'selected' },
    },
    ...(initialScope.kind === 'node'
      ? [{ key: 'chapter', label: initialLabel, scope: initialScope }]
      : []),
    ...sources
      .filter((s) => s.parser_version)
      .map((source) => ({
        key: `source:${source.id}`,
        label: t('资料 · {{v1}}', { v1: source.title }),
        scope: { kind: 'source' as const, source_id: source.id },
      })),
    ...pages
      .filter((p) => p.content_markdown)
      .map((page) => ({
        key: `knowledge:${page.id}`,
        label: t('知识 · {{v1}}', { v1: page.title }),
        scope: { kind: 'knowledge' as const, knowledge_page_id: page.id },
      })),
  ];
  const initial =
    initialScope.kind === 'knowledge'
      ? `knowledge:${initialScope.knowledge_page_id}`
      : initialScope.kind === 'source' || initialScope.kind === 'nodes'
        ? `source:${initialScope.source_id}`
        : initialScope.kind === 'node'
          ? 'chapter'
          : 'selected';
  const [selection, setSelection] = useState(initial);
  const [count, setCount] = useState(15);
  const [language, setLanguage] = useState<string>(initialLanguage ?? uiLanguage);
  const [instruction, setInstruction] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [mode, setMode] = useState<'merged' | 'separate'>('merged');
  const [titleMode, setTitleMode] = useState<'auto' | 'source'>('auto');
  const [sourceChoices, setSourceChoices] = useState(
    initialScope.source_ids ??
      sources.filter((source) => source.enabled).map((source) => source.id),
  );
  const submitted = useRef<{ body: string; key: string } | undefined>(undefined);
  const [chapterChoice, setChapterChoice] = useState<{ scope?: DeckScope; valid: boolean }>({
    valid: true,
  });
  const option = options.find((o) => o.key === selection);
  const chapterSource = sources.find((s) => s.id === option?.scope.source_id);
  const selectedSources = sources.filter(
    (source) => source.enabled && sourceChoices.includes(source.id),
  );
  const scope =
    selection === 'selected'
      ? { kind: 'selected' as const, source_ids: selectedSources.map((source) => source.id) }
      : (chapterChoice.scope ?? option?.scope);
  const separateCount =
    scope?.kind === 'selected'
      ? selectedSources.length
      : scope?.kind === 'nodes'
        ? (scope.node_ids?.length ?? 0)
        : 1;
  const deckCount = mode === 'separate' ? separateCount : 1;
  const sourceNaming =
    scope?.kind !== 'knowledge' &&
    (mode === 'separate' ||
      (scope?.kind === 'selected'
        ? selectedSources.length === 1
        : scope?.kind === 'nodes'
          ? scope.node_ids?.length === 1
          : !!scope));
  const invalid =
    !option ||
    !chapterChoice.valid ||
    (selection === 'selected' &&
      (!selectedSources.length || selectedSources.some((source) => !source.parser_version))) ||
    (mode === 'separate' && deckCount > 100);
  return (
    <Modal onClose={onClose} busy={busy}>
      <form
        className="small-dialog deck-create"
        role="dialog"
        aria-modal="true"
        aria-labelledby="deck-create-title"
        onSubmit={async (event) => {
          event.preventDefault();
          setBusy(true);
          setError('');
          try {
            if (invalid) return;
            const payload = {
              scope,
              slide_count: count,
              language,
              instruction,
              title_mode: sourceNaming ? titleMode : 'auto',
            };
            if (mode === 'separate') {
              const body = JSON.stringify(payload);
              if (submitted.current?.body !== body)
                submitted.current = {
                  body,
                  // getRandomValues also works on the user's HTTP LAN origin.
                  key: [...crypto.getRandomValues(new Uint8Array(16))]
                    .map((v) => v.toString(16).padStart(2, '0'))
                    .join(''),
                };
              const batch = await api<{ batch_id: string; decks: Deck[] }>(
                `/notebooks/${notebookId}/decks/batch`,
                {
                  method: 'POST',
                  body: JSON.stringify({ ...payload, request_key: submitted.current.key }),
                },
              );
              onCreated(batch.decks[0], batch.decks.length);
            } else {
              const deck = await api<Deck>(`/notebooks/${notebookId}/decks`, {
                method: 'POST',
                body: JSON.stringify(payload),
              });
              onCreated(deck, 1);
            }
          } catch (e) {
            setError((e as Error).message);
          } finally {
            setBusy(false);
          }
        }}
      >
        <div className="dialog-top">
          <h2 id="deck-create-title">{t('生成 Visual Deck')}</h2>
          <button
            type="button"
            className="icon-button"
            aria-label={t('关闭 Deck 创建')}
            disabled={busy}
            onClick={onClose}
          >
            <X size={19} />
          </button>
        </div>
        <p className="help">{t('从资料出发，由 AI 规划内容与视觉表达。')}</p>
        <p className="help">{t('每页由图像模型统一生成文字、插画与图解。')}</p>
        <fieldset className="deck-options" disabled={busy}>
          <fieldset className="deck-generation-mode">
            <legend>{t('生成方式')}</legend>
            <label>
              <input
                type="radio"
                name="generation-mode"
                checked={mode === 'merged'}
                onChange={() => setMode('merged')}
              />
              {t('合并生成一份 Deck')}
            </label>
            <label>
              <input
                type="radio"
                name="generation-mode"
                checked={mode === 'separate'}
                onChange={() => setMode('separate')}
              />
              {t('每份资料 / 章节分别生成')}
            </label>
          </fieldset>
          <label>
            {t('内容范围')}
            <select
              aria-label={t('Deck 内容范围')}
              value={selection}
              onChange={(e) => {
                setSelection(e.target.value);
                setChapterChoice({ valid: true });
              }}
            >
              {options.map((option) => (
                <option key={option.key} value={option.key}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          {selection === 'selected' && (
            <fieldset className="generation-sources">
              <legend>{t('选择参与生成的资料')}</legend>
              <div className="generation-source-options">
                {sources
                  .filter((source) => source.enabled)
                  .map((source) => (
                    <label key={source.id}>
                      <input
                        type="checkbox"
                        aria-label={t('资料 · {{v1}}', { v1: source.title })}
                        checked={sourceChoices.includes(source.id)}
                        onChange={(event) =>
                          setSourceChoices((ids) =>
                            event.target.checked
                              ? [...ids, source.id]
                              : ids.filter((id) => id !== source.id),
                          )
                        }
                      />
                      <span>
                        {source.title}
                        {!source.parser_version && ` · ${t('等待解析')}`}
                      </span>
                    </label>
                  ))}
              </div>
              <p className="help">
                {t('从笔记本中已勾选的资料选择；单份资料的章节可在内容范围中选择。')}
              </p>
            </fieldset>
          )}
          {chapterSource && ['epub', 'pdf', 'docx'].includes(chapterSource.type) && (
            <ChapterSelection
              key={selection}
              source={chapterSource}
              initialNode={option?.scope.node_id}
              initialNodes={
                initialScope.kind === 'nodes' && chapterSource.id === initialScope.source_id
                  ? initialScope.node_ids
                  : undefined
              }
              mode={mode}
              onChange={(scope, valid) => setChapterChoice({ scope, valid })}
            />
          )}
          <fieldset className="deck-generation-mode">
            <legend>{t('Deck 名称')}</legend>
            <label>
              <input
                type="radio"
                name="deck-title-mode"
                checked={!sourceNaming || titleMode === 'auto'}
                onChange={() => setTitleMode('auto')}
              />
              {t('由 AI 拟定名称')}
            </label>
            <label>
              <input
                type="radio"
                name="deck-title-mode"
                checked={sourceNaming && titleMode === 'source'}
                disabled={!sourceNaming}
                onChange={() => setTitleMode('source')}
              />
              {t('使用资料 / 章节名称')}
            </label>
            <p className="help">
              {t('每份 Deck 仅使用一份资料或一个章节时可用；分别生成时按各自来源命名。')}{' '}
              {t('章节命名格式：资料名称-目录序号-章节名称（子章节如 1.2）。')}
            </p>
          </fieldset>
          <fieldset className="deck-length">
            <legend>{t('页数')}</legend>
            {[10, 15, 20].map((length) => (
              <label key={length}>
                <input
                  type="radio"
                  name="slide-count"
                  value={length}
                  checked={count === length}
                  onChange={() => setCount(length)}
                />
                {length} {t('页')}
              </label>
            ))}
          </fieldset>
          <label>
            {t('语言')}
            <select
              aria-label={t('Deck 语言')}
              value={language}
              onChange={(e) => setLanguage(e.target.value)}
            >
              {languages.map((item) => (
                <option key={item.code} value={item.code} lang={item.code}>
                  {item.name}
                </option>
              ))}
            </select>
          </label>
        </fieldset>
        <p className="help deck-generation-summary" role="status">
          {t('将生成 {{count}} 份 Deck，每份 {{pages}} 页，共 {{total}} 页。', {
            count: deckCount,
            pages: count,
            total: deckCount * count,
          })}
        </p>
        {mode === 'separate' && (
          <p className="help">{t('每份 Deck 独立排队生成，可分别查看和重试；每批最多 100 份。')}</p>
        )}
        <ArtifactInstructions
          kind="deck"
          value={instruction}
          onChange={setInstruction}
          disabled={busy}
        />
        {error && (
          <p className="error" role="alert">
            {t(error)}
          </p>
        )}
        <div className="dialog-actions">
          <button type="button" className="button secondary" onClick={onClose} disabled={busy}>
            {t('取消')}
          </button>
          <button className="button primary" disabled={busy || invalid}>
            {busy ? t('正在创建…') : t('开始生成')}
          </button>
        </div>
      </form>
    </Modal>
  );
}

function Element({ element }: { element: SlideElement }) {
  if (element.type === 'headline') return <h2>{element.text}</h2>;
  if (element.type === 'subheadline') return <h3>{element.text}</h3>;
  if (element.type === 'quote') return <blockquote>{element.text}</blockquote>;
  if (element.type === 'number')
    return (
      <div className="semantic-number">
        <strong>{element.text}</strong>
        <span>{element.label}</span>
      </div>
    );
  if (element.type === 'comparison')
    return (
      <div className="semantic-comparison">
        {element.items.map((item, i) => (
          <div key={i}>
            <h4>{item.label}</h4>
            <p>{item.text}</p>
          </div>
        ))}
      </div>
    );
  if (element.type === 'bullet_list')
    return (
      <ul>
        {element.items.map((item, i) => (
          <li key={i}>
            {item.label && <strong>{item.label} · </strong>}
            {item.text}
          </li>
        ))}
      </ul>
    );
  return <p className={`semantic-${element.type}`}>{element.text}</p>;
}

const slideTitle = (slide: Slide) =>
  slide.spec?.content_elements.find((e) => e.type === 'headline')?.text || slide.plan.title;

export default function DeckView({
  id,
  onBack,
  backLabel,
  onOpenSource,
  onOpenKnowledge,
  selectedSlideId,
  onSelectSlide,
  onGeneratedCopy,
  onChanged,
  onDeleted,
}: {
  id: string;
  onBack: () => void;
  backLabel?: string;
  onOpenSource: (sourceId: string, blockId: string) => Promise<void>;
  onOpenKnowledge?: (pageId: string) => void;
  selectedSlideId?: string;
  onSelectSlide?: (slideId: string, replace?: boolean) => void;
  onGeneratedCopy?: (deck: Deck) => void;
  onChanged?: () => void;
  onDeleted?: () => void;
}) {
  const uiLanguage = useI18n();
  const [deck, setDeck] = useState<Deck>();
  const [selected, setSelected] = useState<string>();
  const [error, setError] = useState('');
  const [citation, setCitation] = useState<string>();
  const [actionBusy, setActionBusy] = useState(false);
  const [editor, setEditor] = useState<{ slide: Slide; mode: 'text' | 'revise' }>();
  const [deleting, setDeleting] = useState<Slide>();
  const [deleteDeck, setDeleteDeck] = useState(false);
  const [renameDeck, setRenameDeck] = useState(false);
  const mutationVersion = useRef(0);
  const [focused, setFocused] = useState(false);
  const previewStageRef = useRef<HTMLDivElement>(null);
  const focusButtonRef = useRef<HTMLButtonElement>(null);
  const deletingRef = useRef(false);
  const focusWasOpen = useRef(false);
  useEffect(() => {
    if (!focused) {
      if (focusWasOpen.current) focusButtonRef.current?.focus({ preventScroll: true });
      return;
    }
    focusWasOpen.current = true;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    previewStageRef.current?.focus();
    const escape = (event: KeyboardEvent) => {
      if (document.querySelector('.modal-backdrop')) return;
      if (event.key === 'Escape') setFocused(false);
      // Keep keyboard focus in the preview while it covers the workspace.
      if (event.key === 'Tab') {
        const buttons = previewStageRef.current?.querySelectorAll<HTMLElement>(
          'button:not(:disabled), a[href], summary, input:not(:disabled), textarea:not(:disabled)',
        );
        if (!buttons?.length) return;
        const first = buttons[0],
          last = buttons[buttons.length - 1];
        if (
          event.shiftKey &&
          (document.activeElement === first || document.activeElement === previewStageRef.current)
        ) {
          event.preventDefault();
          last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first.focus();
        }
      }
    };
    document.addEventListener('keydown', escape);
    return () => {
      document.body.style.overflow = overflow;
      document.removeEventListener('keydown', escape);
    };
  }, [focused]);
  const previewRef = useRef<HTMLElement>(null);
  const slideListRef = useRef<HTMLElement>(null);
  useEffect(() => {
    setEditor(undefined);
    setCitation(undefined);
    setDeleting(undefined);
  }, [selectedSlideId]);
  useEffect(() => {
    let active = true;
    const load = async () => {
      const version = mutationVersion.current;
      try {
        const value = await api<Deck>(`/decks/${id}`);
        if (active && !deletingRef.current && version === mutationVersion.current) setDeck(value);
      } catch (e) {
        if (active && !deletingRef.current) setError((e as Error).message);
      }
    };
    void load();
    const timer = setInterval(() => void load(), 1000);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [id]);
  const slide = deck?.slides.find((s) => s.id === (selectedSlideId ?? selected)) ?? deck?.slides[0];
  useEffect(() => {
    const preview = previewRef.current;
    if (!preview) return;
    const fitImage = () => {
      const image = preview.querySelector<HTMLElement>('.rendered-page');
      if (image) {
        const imageTop =
          image.getBoundingClientRect().top -
          preview.getBoundingClientRect().top +
          preview.scrollTop;
        preview.style.setProperty(
          '--slide-image-height',
          `${Math.max(100, preview.clientHeight - imageTop - 20)}px`,
        );
      }
    };
    const observer = new ResizeObserver(fitImage);
    observer.observe(preview);
    fitImage();
    return () => observer.disconnect();
  }, [slide?.id, slide?.render?.id, slide?.render_current, uiLanguage]);
  useEffect(() => {
    if (previewRef.current) previewRef.current.scrollTop = 0;
    const list = slideListRef.current;
    if (!list) return;
    const revealActive = () => {
      const active = list.querySelector<HTMLElement>('.active');
      if (!active) return;
      // Scroll this rail only: scrollIntoView can also move the surrounding workspace.
      if (active.offsetTop < list.scrollTop) list.scrollTop = active.offsetTop;
      else if (active.offsetTop + active.offsetHeight > list.scrollTop + list.clientHeight)
        list.scrollTop = active.offsetTop + active.offsetHeight - list.clientHeight;
      if (active.offsetLeft < list.scrollLeft) list.scrollLeft = active.offsetLeft;
      else if (active.offsetLeft + active.offsetWidth > list.scrollLeft + list.clientWidth)
        list.scrollLeft = active.offsetLeft + active.offsetWidth - list.clientWidth;
    };
    revealActive();
    const observer = new ResizeObserver(revealActive);
    observer.observe(list);
    return () => observer.disconnect();
  }, [slide?.id]);
  useEffect(() => {
    if (slide && onSelectSlide && slide.id !== selectedSlideId) onSelectSlide(slide.id, true);
  }, [slide?.id, selectedSlideId, onSelectSlide]);
  const generating = !!deck?.job && ['queued', 'running'].includes(deck.job.status);
  const paused = !generating && (deck?.status === 'paused' || deck?.job?.status === 'cancelled');
  const busy = actionBusy || generating;
  const displayedStatus = paused
    ? 'paused'
    : deck?.job?.status === 'queued'
      ? 'queued'
      : deck?.status;
  const selectPage = useCallback(
    (slideId: string) => {
      if (onSelectSlide) onSelectSlide(slideId);
      else setSelected(slideId);
    },
    [onSelectSlide],
  );
  const slideIndex = deck?.slides.findIndex((page) => page.id === slide?.id) ?? -1;
  const previousPage = slideIndex > 0;
  const nextPage = slideIndex >= 0 && slideIndex < (deck?.slides.length ?? 0) - 1;
  const changePage = useCallback(
    (direction: -1 | 1) => {
      if (slideIndex < 0) return;
      const next = deck?.slides[slideIndex + direction];
      if (next) selectPage(next.id);
    },
    [deck, slideIndex, selectPage],
  );
  useEffect(() => {
    if (slideIndex < 0) return;
    const navigate = (event: KeyboardEvent) => {
      if (
        event.defaultPrevented ||
        event.isComposing ||
        event.altKey ||
        event.ctrlKey ||
        event.metaKey ||
        event.shiftKey ||
        editor ||
        citation ||
        deleting ||
        deleteDeck ||
        document.querySelector('.modal-backdrop') ||
        (event.target instanceof HTMLElement &&
          event.target.closest(
            'input, textarea, select, [contenteditable]:not([contenteditable="false"]), [role="textbox"], [role="combobox"], [role="slider"], [role="spinbutton"]',
          ))
      )
        return;
      if (event.key !== 'ArrowUp' && event.key !== 'ArrowDown') return;
      event.preventDefault();
      changePage(event.key === 'ArrowUp' ? -1 : 1);
    };
    document.addEventListener('keydown', navigate);
    return () => document.removeEventListener('keydown', navigate);
  }, [slideIndex, changePage, editor, citation, deleting, deleteDeck]);
  const changeGeneration = async (action: 'stop' | 'resume') => {
    setActionBusy(true);
    setError('');
    try {
      setDeck(await api<Deck>(`/decks/${id}/${action}`, { method: 'POST' }));
      onChanged?.();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setActionBusy(false);
    }
  };
  const generatedPage = deck?.render_mode === 'generated_page';
  const reload = async () => setDeck(await api<Deck>(`/decks/${id}`));
  const mutate = async (url: string, method: string, body: unknown) => {
    setActionBusy(true);
    setError('');
    try {
      await api(url, { method, body: JSON.stringify(body) });
      await reload();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setActionBusy(false);
    }
  };
  const move = async (direction: number) => {
    if (!deck || !slide) return;
    const order = deck.slides.map((s) => s.id);
    const from = order.indexOf(slide.id),
      to = from + direction;
    [order[from], order[to]] = [order[to], order[from]];
    await mutate(`/decks/${id}/order`, 'PUT', { revision: deck.revision, slide_ids: order });
  };
  const retrySlide = async (action: 'retry' | 'without-image') => {
    if (!slide) return;
    setActionBusy(true);
    setError('');
    try {
      await api(`/decks/${id}/slides/${slide.id}/${action}`, { method: 'POST' });
      setDeck(await api<Deck>(`/decks/${id}`));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setActionBusy(false);
    }
  };
  return (
    <section className="deck-view" aria-label="Visual Deck">
      <div className="reader-header">
        <button className="button ghost" onClick={onBack}>
          <ArrowLeft size={16} /> {backLabel ?? t('返回对话')}
        </button>
        <span className="reader-format">Visual Deck</span>
      </div>
      {error && (
        <p className="error" role="alert">
          {t(error)}
        </p>
      )}
      {deck ? (
        <>
          <div className="deck-heading">
            <div className="deck-name-row">
              <h2>{deck.title}</h2>
              <button
                className="button secondary"
                disabled={busy || actionBusy}
                onClick={() => setRenameDeck(true)}
              >
                {t('重命名 Deck')}
              </button>
            </div>
            <p>
              {t('{{v1}} 页 · {{v2}}', {
                v1: deck.slide_count,
                v2: t(deckStatus[displayedStatus ?? ''] ?? deck.status),
              })}
            </p>
          </div>
          <ArtifactInstructionDetails instruction={deck.instruction} />
          <DeckSources
            key={`sources:${id}`}
            id={id}
            onOpenSource={onOpenSource}
            onOpenKnowledge={onOpenKnowledge}
          />
          <div className="deck-progress" role="status">
            {busy && <LoaderCircle size={15} className="spin" />}
            <span>
              {busy
                ? t(
                    generating && deck.job?.status === 'queued'
                      ? '等待生成'
                      : (deckStatus[deck.job?.stage ?? ''] ?? '正在理解资料'),
                  )
                : paused
                  ? t('已停止，已保存的进度会保留。')
                  : deck.status === 'draft'
                    ? deck.slides.every((s) => s.render)
                      ? t('页面预览已生成')
                      : t('内容已生成，等待视觉渲染')
                    : t(deckStatus[deck.status])}
            </span>
            <span>
              {t('{{v1}} / {{v2}} 页内容已保存', {
                v1: deck.slides.filter((s) => s.spec).length,
                v2: deck.slide_count,
              })}
            </span>
            <span>
              {t('{{v1}} / {{v2}}  页预览已保存', {
                v1: deck.slides.filter((s) => s.render && s.render_current).length,
                v2: deck.slide_count,
              })}
            </span>
          </div>
          <div className="deck-export">
            {generating && (
              <button
                className="button secondary"
                disabled={actionBusy}
                onClick={() => void changeGeneration('stop')}
              >
                {t('停止生成')}
              </button>
            )}
            {paused && (
              <button
                className="button primary"
                disabled={actionBusy}
                onClick={() => void changeGeneration('resume')}
              >
                {t('继续生成')}
              </button>
            )}
            <button
              className="button ghost danger-text"
              disabled={actionBusy}
              onClick={() => {
                setFocused(false);
                setDeleteDeck(true);
              }}
            >
              {t('删除 Deck')}
            </button>
            {deck.pdf_export?.status === 'ready' && deck.pdf_export.preview_url && !busy && (
              <a
                className="button secondary"
                href={deck.pdf_export.preview_url}
                target="_blank"
                rel="noopener noreferrer"
              >
                {t('预览 PDF')}
              </a>
            )}
            {deck.pdf_export?.status === 'ready' && deck.pdf_export.download_url && !busy && (
              <a
                className="button primary"
                href={deck.pdf_export.download_url}
                download={deck.pdf_export.filename ?? true}
              >
                {t('下载 PDF · {{v1}} 页', { v1: deck.pdf_export.page_count })}
              </a>
            )}
            <details className="deck-more-actions">
              <summary>{t('更多操作')}</summary>
              <p className="help">{t('副本会作为新的演示文稿生成；原稿会保留。')}</p>
              <div className="deck-export">
                <button
                  className="button secondary"
                  disabled={
                    !!busy ||
                    !deck.slides.length ||
                    deck.slides.some((s) => s.status !== 'rendered')
                  }
                  onClick={async () => {
                    setActionBusy(true);
                    setError('');
                    try {
                      await api(`/decks/${id}/export`, { method: 'POST' });
                      setDeck(await api<Deck>(`/decks/${id}`));
                    } catch (e) {
                      setError((e as Error).message);
                    } finally {
                      setActionBusy(false);
                    }
                  }}
                >
                  {deck.pdf_export?.status === 'ready' ? t('重新生成 PDF 文件') : t('导出 PDF')}
                </button>
                {onGeneratedCopy && (
                  <>
                    <button
                      className="button secondary"
                      disabled={!!busy || !deck.slides.length || deck.slides.some((s) => !s.spec)}
                      title={t('保留文字与出处，根据内容重新选择视觉风格并生成副本，保留原稿。')}
                      onClick={async () => {
                        setActionBusy(true);
                        setError('');
                        try {
                          const copy = await api<Deck>(`/decks/${id}/generated-copy?restyle=true`, {
                            method: 'POST',
                          });
                          onGeneratedCopy(copy);
                        } catch (e) {
                          setError((e as Error).message);
                        } finally {
                          setActionBusy(false);
                        }
                      }}
                    >
                      {t(generatedPage ? '仅更新视觉，生成副本' : '生成整页副本')}
                    </button>
                    <button
                      className="button ghost"
                      disabled={!!busy || !deck.slides.length || deck.slides.some((s) => !s.spec)}
                      title={t('重新研究原资料，重写内容并重新设计视觉风格，生成副本并保留原稿。')}
                      onClick={async () => {
                        setActionBusy(true);
                        setError('');
                        try {
                          const copy = await api<Deck>(
                            `/decks/${id}/generated-copy?rewrite_content=true&restyle=true`,
                            { method: 'POST' },
                          );
                          onGeneratedCopy(copy);
                        } catch (e) {
                          setError((e as Error).message);
                        } finally {
                          setActionBusy(false);
                        }
                      }}
                    >
                      {t('重新解读并生成副本')}
                    </button>
                  </>
                )}
              </div>
            </details>
          </div>
          {generatedPage && (
            <p className="help">
              {t('PDF 为整页图片。文字稿与原文出处可在应用中查看；修改文字会重新生成本页。')}
            </p>
          )}
          {(deck.plan || deck.style || deck.art_direction) && (
            <details className="deck-visual-plan">
              <summary>{t(deck.art_direction ? '查看视觉编排' : '查看 Deck 说明')}</summary>
              {deck.plan && <p className="deck-narrative">{deck.plan.narrative}</p>}
              {deck.style && (
                <div className="deck-concept">
                  <span>{deck.style.concept}</span>
                  <div aria-label={t('AI 生成的配色')}>
                    {Object.entries(deck.style.palette).map(([name, color]) => (
                      <i key={name} style={{ backgroundColor: color }} />
                    ))}
                  </div>
                </div>
              )}
              {deck.art_direction && (
                <>
                  <p className="help">
                    {t('{{v1}} 种表达 · {{v2}} 种观察角度', {
                      v1: Object.keys(deck.art_direction.metrics.forms).length,
                      v2: Object.keys(deck.art_direction.metrics.viewpoints).length,
                    })}
                  </p>
                  <p className="help">{t('这是生成前的编排方案，实际画面仍需逐页核对。')}</p>
                  <ol>
                    {deck.slides.map((item, index) => {
                      const direction = deck.art_direction?.pages[item.id];
                      return direction ? (
                        <li key={item.id}>
                          <strong>
                            {index + 1}. {item.plan.title}
                          </strong>
                          <span>
                            {t(visualForms[direction.form] ?? direction.form)} ·{' '}
                            {t(readingSurfaces[direction.surface] ?? direction.surface)}
                          </span>
                        </li>
                      ) : null;
                    })}
                  </ol>
                </>
              )}
            </details>
          )}
          {!paused && ['partial', 'failed'].includes(deck.status) && (
            <div className="error">
              <p>
                {deck.job?.error_message
                  ? errorText(deck.job)
                  : t('部分页面未能完成，已完成的内容会保留。')}
              </p>
              <button
                className="button secondary"
                disabled={!!busy}
                onClick={async () => {
                  try {
                    await api(`/decks/${id}/retry`, { method: 'POST' });
                    setDeck(await api<Deck>(`/decks/${id}`));
                  } catch (e) {
                    setError((e as Error).message);
                  }
                }}
              >
                {t('重试未完成页面')}
              </button>
            </div>
          )}
          {deck.job && (
            <DeckDiagnostics
              key={id}
              deckId={id}
              failed={
                ['partial', 'failed'].includes(deck.status) ||
                !!deck.job.error_code ||
                deck.slides.some((slide) => !!slide.error_code)
              }
            />
          )}
          {!!deck.slides.length && (
            <div
              ref={previewStageRef}
              tabIndex={-1}
              className={`deck-preview-stage${focused ? ' is-focused' : ''}`}
              role={focused ? 'dialog' : undefined}
              aria-modal={focused || undefined}
              aria-label={t('Deck 大图预览')}
            >
              <div className="deck-preview-toolbar">
                <span>
                  {t('第 {{current}} / {{total}} 页', {
                    current: (slide?.ordinal ?? 0) + 1,
                    total: deck.slides.length,
                  })}
                </span>
                <div>
                  <button
                    className="button secondary"
                    aria-label={t('上一页')}
                    disabled={!previousPage}
                    onClick={() => changePage(-1)}
                  >
                    <ChevronLeft size={16} />
                  </button>
                  <button
                    className="button secondary"
                    aria-label={t('下一页')}
                    disabled={!nextPage}
                    onClick={() => changePage(1)}
                  >
                    <ChevronRight size={16} />
                  </button>
                  <button
                    ref={focusButtonRef}
                    className="button secondary"
                    onClick={() => setFocused(!focused)}
                  >
                    {focused ? <Minimize2 size={16} /> : <Maximize2 size={16} />}{' '}
                    {t(focused ? '退出专注预览' : '专注预览')}
                  </button>
                </div>
              </div>
              <div className="deck-content-layout">
                <nav ref={slideListRef} className="slide-list" aria-label={t('Deck 页面')}>
                  {deck.slides.map((s) => (
                    <button
                      key={s.id}
                      className={slide?.id === s.id ? 'active' : ''}
                      aria-current={slide?.id === s.id ? 'page' : undefined}
                      onClick={() => {
                        selectPage(s.id);
                      }}
                    >
                      {s.render && (
                        <img className="slide-thumbnail" src={s.render.thumbnail_url} alt="" />
                      )}
                      <span>{String(s.ordinal + 1).padStart(2, '0')}</span>
                      <strong>{slideTitle(s)}</strong>
                      <small>
                        {s.status === 'failed'
                          ? t('生成失败')
                          : s.spec
                            ? t('内容已保存')
                            : t('等待创作')}
                      </small>
                    </button>
                  ))}
                </nav>
                {slide && (
                  <article ref={previewRef} className="slide-content">
                    <p className="eyebrow">
                      {t('第 {{v1}} 页 · {{v2}}', {
                        v1: slide.ordinal + 1,
                        v2: slide.render ? t('页面预览') : t('内容草稿'),
                      })}
                    </p>
                    <div className="slide-actions" aria-label={t('本页操作')}>
                      <button
                        className="button secondary"
                        disabled={!!busy || !slide.spec}
                        onClick={() => setEditor({ slide, mode: 'text' })}
                      >
                        {t('编辑文字')}
                      </button>
                      <button
                        className="button secondary"
                        disabled={!!busy || !slide.spec}
                        onClick={() => setEditor({ slide, mode: 'revise' })}
                      >
                        {t('用 AI 修改')}
                      </button>
                      {(generatedPage
                        ? (['content', 'visual'] as const)
                        : (['content', 'visual', 'image'] as const)
                      ).map((action) => (
                        <button
                          key={action}
                          className="button ghost"
                          disabled={
                            !!busy ||
                            !slide.spec ||
                            (action === 'image' && !slide.spec.asset_requests.length)
                          }
                          onClick={() =>
                            void mutate(`/decks/${id}/slides/${slide.id}/revise`, 'POST', {
                              revision: slide.revision,
                              action,
                            })
                          }
                        >
                          {
                            {
                              content: t('重写内容'),
                              visual: t('重做视觉'),
                              image: t('重生成图片'),
                            }[action]
                          }
                        </button>
                      ))}
                      <button
                        className="button ghost"
                        disabled={!!busy || slide.ordinal === 0}
                        onClick={() => void move(-1)}
                      >
                        {t('上移本页')}
                      </button>
                      <button
                        className="button ghost"
                        disabled={!!busy || slide.ordinal === deck.slides.length - 1}
                        onClick={() => void move(1)}
                      >
                        {t('下移本页')}
                      </button>
                      <button
                        className="button ghost danger"
                        disabled={!!busy}
                        onClick={() => setDeleting(slide)}
                      >
                        {t('删除本页')}
                      </button>
                    </div>
                    {slide.spec ? (
                      <>
                        {slide.render ? (
                          <>
                            {!slide.render_current && (
                              <p className="help">
                                {t('下面保留上次完成的预览；最新文字可在“查看页面文字”中查看。')}
                              </p>
                            )}
                            <div className="deck-page-image">
                              <img
                                className="rendered-page"
                                src={slide.render.image_url}
                                alt={slideTitle(slide)}
                              />
                              <button
                                type="button"
                                className="deck-image-nav previous"
                                aria-label={`${t('上一页')} · ${t('页面预览')}`}
                                aria-keyshortcuts="ArrowUp"
                                disabled={!previousPage}
                                onClick={() => changePage(-1)}
                              />
                              <button
                                type="button"
                                className="deck-image-nav next"
                                aria-label={`${t('下一页')} · ${t('页面预览')}`}
                                aria-keyshortcuts="ArrowDown"
                                disabled={!nextPage}
                                onClick={() => changePage(1)}
                              />
                            </div>
                            <a
                              className="slide-hd-link"
                              href={slide.render.image_url}
                              target="_blank"
                              rel="noopener noreferrer"
                            >
                              {t('查看高清页')}
                            </a>
                            <details className="slide-text-details">
                              <summary>
                                {t(generatedPage ? '查看页面文字稿' : '查看页面文字')}
                              </summary>
                              {generatedPage && (
                                <p className="help">
                                  {t('这是生成页面时使用的文字稿，可据此核对图片中的文字。')}
                                </p>
                              )}
                              {slide.spec.content_elements.map((element) => (
                                <Element key={element.id} element={element} />
                              ))}
                            </details>
                          </>
                        ) : (
                          slide.spec.content_elements.map((element) => (
                            <Element key={element.id} element={element} />
                          ))
                        )}
                        {slide.assets.length > 0 && (
                          <div className="slide-asset-status" role="status">
                            <p>
                              {t('图片 {{v1}} /  {{v2}} 已生成', {
                                v1: slide.assets.filter((a) => a.status === 'ready').length,
                                v2: slide.assets.length,
                              })}
                            </p>
                            {slide.assets.some((a) => a.status === 'skipped') && (
                              <p>{t('已选择不使用失败的图片继续。')}</p>
                            )}
                            {slide.assets
                              .filter((a) => a.status === 'failed')
                              .map((a) => (
                                <p className="error" key={a.id}>
                                  {errorText(a)}
                                </p>
                              ))}
                          </div>
                        )}
                        <div className="slide-sources">
                          <h4>{t('本页使用的资料')}</h4>
                          {Object.entries(slide.citations).map(([, ref], index) => (
                            <button
                              className="button ghost"
                              key={ref}
                              onClick={() => setCitation(ref)}
                            >
                              {t('原文引用 {{v1}}', { v1: index + 1 })}
                            </button>
                          ))}
                        </div>
                      </>
                    ) : (
                      <>
                        <h2>{slide.plan.title}</h2>
                        <p>{slide.plan.purpose}</p>
                        <p className="help">
                          {slide.error_message
                            ? errorText(slide)
                            : t('计划已保存，正在等待逐页创作。')}
                        </p>
                      </>
                    )}
                    {slide.status === 'failed' && (
                      <div className="slide-retry">
                        <p className="error">{errorText(slide)}</p>
                        <button
                          className="button secondary"
                          disabled={!!busy}
                          onClick={() => void retrySlide('retry')}
                        >
                          {t('重试本页')}
                        </button>
                        {!generatedPage && slide.assets.some((a) => a.status === 'failed') && (
                          <button
                            className="button ghost"
                            disabled={!!busy}
                            onClick={() => void retrySlide('without-image')}
                          >
                            {t('不使用失败的图片继续')}
                          </button>
                        )}
                      </div>
                    )}
                  </article>
                )}
              </div>
            </div>
          )}
          {!deck.slides.length && (
            <div className="empty-panel">
              <Layers size={28} />
              <p>
                {paused
                  ? t('生成已停止，点击继续生成以接着完成。')
                  : deck.plan && !busy
                    ? t('这份 Deck 暂无页面。你可以从 Studio 创建一份新 Deck。')
                    : t('正在理解资料并规划整份 Deck，计划完成后会逐页显示。')}
              </p>
            </div>
          )}
        </>
      ) : (
        <p role="status">{t('正在打开 Deck…')}</p>
      )}
      {renameDeck && deck && (
        <DeckRenameDialog
          id={id}
          title={deck.title}
          onClose={() => setRenameDeck(false)}
          onSaved={(value) => {
            mutationVersion.current += 1;
            setDeck(value);
            setRenameDeck(false);
            onChanged?.();
          }}
        />
      )}
      {deleteDeck && deck && (
        <DeckDeleteDialog
          id={id}
          title={deck.title}
          onClose={() => setDeleteDeck(false)}
          onDeleted={() => {
            deletingRef.current = true;
            setDeleteDeck(false);
            if (onDeleted) onDeleted();
            else onBack();
          }}
        />
      )}
      {citation && (
        <CitationPreview
          id={citation}
          onClose={() => setCitation(undefined)}
          onOpen={onOpenSource}
        />
      )}
      {editor && (
        <SlideEditor
          deckId={id}
          slide={editor.slide}
          mode={editor.mode}
          generatedPage={generatedPage}
          onClose={() => setEditor(undefined)}
          onSaved={reload}
        />
      )}
      {deleting && (
        <Modal onClose={() => setDeleting(undefined)} busy={actionBusy}>
          <div
            className="small-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="delete-slide-title"
          >
            <h2 id="delete-slide-title">{t('删除第 {{v1}} 页？', { v1: deleting.ordinal + 1 })}</h2>
            <p>{t('删除后将更新页面顺序和 PDF。')}</p>
            <div className="dialog-actions">
              <button
                className="button secondary"
                disabled={actionBusy}
                onClick={() => setDeleting(undefined)}
              >
                {t('取消')}
              </button>
              <button
                className="button danger"
                disabled={actionBusy}
                onClick={async () => {
                  await mutate(`/decks/${id}/slides/${deleting.id}`, 'DELETE', {
                    revision: deleting.revision,
                  });
                  setDeleting(undefined);
                }}
              >
                {t('确认删除页面')}
              </button>
            </div>
          </div>
        </Modal>
      )}
    </section>
  );
}
