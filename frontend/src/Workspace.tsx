import Modal from './Modal';
import { t, useI18n, errorText, errorKey, languages, type UiLanguage } from './i18n';
import { useCallback, useEffect, useRef, useState } from 'react';
import { ArrowLeft, FileText, Layers, Plus, RotateCcw, Trash2, X } from 'lucide-react';
import {
  api,
  type Notebook,
  type Source,
  type Scope,
  type KnowledgePage,
  type DeckScope,
  type DeckSummary,
  type SourceNode,
} from './api';
import Reader from './Reader';
import SourceImport from './SourceImport';
import Chat from './Chat';
import Knowledge from './Knowledge';
import Transformation from './Transformation';
import DeckView, { CreateDeck, deckStatus } from './Deck';
import DeckDeleteDialog from './DeckDeleteDialog';
import ArtifactBatchDownload from './ArtifactBatchDownload';
import { useGuardedNavigation } from './NavigationGuard';
import { useNavigation, type Route } from './Navigation';

const statusText: Record<string, string> = {
  uploaded: '等待解析',
  fetching_web: '正在读取网页',
  parsing: '正在解析',
  recognizing_images: '正在识别图片',
  parsed: '可阅读',
  indexed: '可用于问答',
  failed: '处理失败',
};

export default function Workspace({
  notebook,
  onBack,
}: {
  notebook: Notebook;
  onBack: () => void;
}) {
  const uiLanguage = useI18n();
  const [outputChoice, setOutputChoice] = useState<UiLanguage | 'interface'>('interface');
  const outputLanguage = outputChoice === 'interface' ? uiLanguage : outputChoice;
  const navigate = useGuardedNavigation();
  const [sources, setSources] = useState<Source[]>([]);
  const [pages, setPages] = useState<KnowledgePage[]>([]);
  const [decks, setDecks] = useState<DeckSummary[]>([]);
  const [deletingDeck, setDeletingDeck] = useState<DeckSummary>();
  const [deckAction, setDeckAction] = useState<string>();
  const deckRefreshVersion = useRef(0);
  const { route, go } = useNavigation();
  const liveRoute = useRef(route);
  liveRoute.current = route;
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);
  const deckId = route.view === 'deck' ? route.itemId : undefined;
  const knowledgeId = route.view === 'knowledge' ? route.itemId : undefined;
  const libraryTab = route.library ?? 'sources';
  const readerBlock = route.blockId;
  const chatScope = route.scope ?? { kind: 'selected' };
  function show(view: Route['view'], itemId?: string, extra: Partial<Route> = {}, guarded = true) {
    if (!mounted.current || liveRoute.current !== route) return false;
    return go(
      {
        ...route,
        view,
        notebookId: notebook.id,
        itemId,
        nodeId: undefined,
        blockId: undefined,
        slideId: undefined,
        ...extra,
      },
      { guarded },
    );
  }
  function setLibraryTab(library: 'sources' | 'knowledge') {
    go({ ...route, library }, { guarded: false });
  }
  const [deckCreation, setDeckCreation] = useState<{ scope: DeckScope; label: string }>();
  const [batchNotice, setBatchNotice] = useState(0);
  const [generating, setGenerating] = useState(false);
  const [transformationId, setTransformationId] = useState<string>();
  const [reader, setReader] = useState<Source | null>(null);
  const [scopeLabel, setScopeLabel] = useState<string>();
  const [opening, setOpening] = useState(false);
  const [viewError, setViewError] = useState('');
  const [error, setError] = useState('');
  const [loadError, setLoadError] = useState('');
  const [libraryLoading, setLibraryLoading] = useState(true);
  const [compactPanel, setCompactPanel] = useState<'library' | 'main' | 'studio'>('main');
  const [modalBusy, setModalBusy] = useState(false);
  const [modalError, setModalError] = useState('');
  useEffect(() => {
    setCompactPanel('main');
  }, [route.view, route.itemId]);
  const [removing, setRemoving] = useState<Source | null>(null);
  const [permanent, setPermanent] = useState(false);
  const selectionVersion = useRef(0);
  const [changing, setChanging] = useState<string[]>([]);
  const refresh = useCallback(async () => {
    const deckVersion = ++deckRefreshVersion.current;
    const version = selectionVersion.current;
    const [result, knowledgeList, deckList] = await Promise.all([
      api<Source[]>(`/notebooks/${notebook.id}/sources`),
      api<KnowledgePage[]>(`/notebooks/${notebook.id}/knowledge`),
      api<DeckSummary[]>(`/notebooks/${notebook.id}/decks`),
    ]);
    if (!mounted.current) return;
    setLoadError('');
    setLibraryLoading(false);
    if (version === selectionVersion.current) {
      setSources(result);
      setReader((current) =>
        current ? (result.find((source) => source.id === current.id) ?? current) : current,
      );
    }
    setPages(knowledgeList);
    if (deckVersion === deckRefreshVersion.current) setDecks(deckList);
  }, [notebook.id]);
  useEffect(() => {
    void refresh().catch((e) => {
      if (mounted.current) {
        setLoadError(e.message);
        setLibraryLoading(false);
      }
    });
    const timer = setInterval(() => {
      void refresh().catch((e) => {
        if (mounted.current) {
          setLoadError(e.message);
          setLibraryLoading(false);
        }
      });
    }, 1500);
    return () => clearInterval(timer);
  }, [refresh]);
  useEffect(() => {
    let active = true;
    setViewError('');
    setReader(null);
    if (route.view !== 'source' || !route.itemId) {
      setOpening(false);
      return;
    }
    setOpening(true);
    api<Source>(`/sources/${route.itemId}`)
      .then((source) => {
        if (!active) return;
        if (!source.parser_version) {
          setViewError(
            source.status === 'failed'
              ? errorKey(source.error_code)
              : '资料尚未完成解析，请稍后重新打开。',
          );
        } else setReader(source);
      })
      .catch((e) => {
        if (active) setViewError(e.message);
      })
      .finally(() => {
        if (active) setOpening(false);
      });
    return () => {
      active = false;
    };
  }, [route.view, route.itemId]);
  useEffect(() => {
    let active = true;
    setScopeLabel(undefined);
    if (chatScope.kind === 'selected' || !chatScope.source_id) return;
    api<Source>(`/sources/${chatScope.source_id}`)
      .then(async (source) => {
        let label = source.title;
        if (chatScope.kind === 'node') {
          const nodes = await api<SourceNode[]>(`/sources/${source.id}/nodes`);
          const node = nodes.find((n) => n.id === chatScope.node_id);
          if (!node) throw new Error(t('提问范围已不可用，请重新选择资料。'));
          label = node.type === 'page' ? t('第 {{v1}} 页', { v1: node.start_page }) : node.title;
        }
        if (active) setScopeLabel(label);
      })
      .catch(() => {
        if (active) setScopeLabel(t('提问范围已不可用，请重新选择资料。'));
      });
    return () => {
      active = false;
    };
  }, [chatScope.kind, chatScope.source_id, chatScope.node_id, uiLanguage]);
  const readerLocation = useCallback(
    (nodeId: string, blockId?: string, replace = false) => {
      go({ ...route, nodeId, blockId }, { replace, guarded: false });
    },
    [route, go],
  );
  const slideLocation = useCallback(
    (slideId: string, replace = false) => {
      go({ ...route, slideId }, { replace, guarded: !replace });
    },
    [route, go],
  );
  async function enable(source: Source, enabled: boolean) {
    selectionVersion.current += 1;
    setChanging((ids) => [...ids, source.id]);
    setSources((items) =>
      items.map((item) => (item.id === source.id ? { ...item, enabled } : item)),
    );
    try {
      await api(`/notebooks/${notebook.id}/sources/${source.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ enabled }),
      });
    } catch (e) {
      setError((e as Error).message);
    } finally {
      selectionVersion.current += 1;
      setChanging((ids) => ids.filter((id) => id !== source.id));
      await refresh().catch((e) => setError(e.message));
    }
  }
  const selected = sources.filter((s) => s.enabled).length;
  async function generate(scope: Scope) {
    if (!navigate(() => {})) return;
    setGenerating(true);
    setError('');
    try {
      const result = await api<{ page: KnowledgePage }>(`/notebooks/${notebook.id}/knowledge`, {
        method: 'POST',
        body: JSON.stringify({ scope, language: outputLanguage }),
      });
      show('knowledge', result.page.id, { library: 'knowledge' }, false);
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setGenerating(false);
    }
  }
  async function openSource(sourceId: string, blockId: string) {
    await api<Source>(`/sources/${sourceId}`);
    show('source', sourceId, { blockId, library: 'sources' });
  }
  return (
    <div className="workspace">
      <div className="workspace-top">
        <button className="button ghost" onClick={onBack}>
          <ArrowLeft size={17} /> {t('笔记本')}
        </button>
        <h2>{notebook.title}</h2>
        <label
          className="output-language-picker"
          title={t('用于新问答、知识页、摘要、提纲和 Deck；已有内容保持原语言。')}
        >
          {t('新内容语言')}
          <select
            aria-label={t('新内容语言')}
            value={outputChoice}
            onChange={(event) => setOutputChoice(event.target.value as UiLanguage | 'interface')}
          >
            <option value="interface">{t('跟随界面语言')}</option>
            {languages.map((item) => (
              <option key={item.code} value={item.code} lang={item.code}>
                {item.name}
              </option>
            ))}
          </select>
        </label>
      </div>
      {loadError && (
        <div className="error workspace-error" role="alert">
          {t(loadError)}
          <button
            className="button secondary"
            onClick={() => void refresh().catch((e) => setLoadError(e.message))}
          >
            {t('重试')}
          </button>
        </div>
      )}
      {error && (
        <div className="error workspace-error" role="alert">
          {t(error)}
          <button className="icon-button" aria-label={t('关闭错误')} onClick={() => setError('')}>
            <X size={15} />
          </button>
        </div>
      )}
      <nav className="workspace-sections" aria-label={t('工作区分区')}>
        {(['library', 'main', 'studio'] as const).map((panel) => (
          <button
            key={panel}
            type="button"
            aria-pressed={compactPanel === panel}
            aria-controls={`workspace-${panel}`}
            onClick={() => setCompactPanel(panel)}
            className={`button ${compactPanel === panel ? 'primary' : 'secondary'}`}
          >
            {t({ library: '资料与知识', main: '工作区', studio: '演示文稿' }[panel])}
          </button>
        ))}
      </nav>
      <div className="workspace-columns" data-panel={compactPanel}>
        <aside id="workspace-library" className="workspace-panel source-panel">
          <nav className="library-tabs" aria-label={t('笔记本内容')}>
            <button
              className={`button ghost ${libraryTab === 'sources' ? 'active' : ''}`}
              aria-pressed={libraryTab === 'sources'}
              onClick={() => setLibraryTab('sources')}
            >
              {t('资料')}
            </button>
            <button
              className={`button ghost ${libraryTab === 'knowledge' ? 'active' : ''}`}
              aria-pressed={libraryTab === 'knowledge'}
              onClick={() => setLibraryTab('knowledge')}
            >
              {t('知识')}
              <span>{pages.length}</span>
            </button>
          </nav>
          {libraryTab === 'sources' ? (
            <>
              <div className="panel-title">
                <FileText size={18} />
                <h3>{t('资料')}</h3>
                <span className="count">{sources.length}</span>
              </div>
              <SourceImport notebookId={notebook.id} onImported={refresh} />
              {!!sources.length && (
                <p className="source-scope-help">
                  {t('勾选资料用于问答和默认生成；点击名称阅读原文。')}
                </p>
              )}
              {sources.length > 0 && (
                <label className="select-all">
                  <input
                    type="checkbox"
                    ref={(element) => {
                      if (element)
                        element.indeterminate =
                          sources.some((source) => source.enabled) &&
                          !sources.every((source) => source.enabled);
                    }}
                    checked={sources.every((s) => s.enabled)}
                    disabled={changing.length > 0}
                    onChange={async (e) => {
                      const enabled = e.target.checked;
                      for (const s of sources) await enable(s, enabled);
                    }}
                  />{' '}
                  {t('选择全部')}
                  <span>{t('{{v1}} 已选', { v1: selected })}</span>
                </label>
              )}
              <div className="source-list">
                {libraryLoading && <p role="status">{t('正在打开你的工作台…')}</p>}
                {sources.map((source) => (
                  <div
                    className={`source-item ${reader?.id === source.id ? 'active' : ''}`}
                    key={source.id}
                  >
                    <input
                      type="checkbox"
                      checked={source.enabled}
                      disabled={changing.includes(source.id)}
                      aria-label={t('选择 {{v1}}', { v1: source.title })}
                      onChange={(e) => void enable(source, e.target.checked)}
                    />
                    <button
                      className="source-open"
                      disabled={!source.parser_version}
                      onClick={() => {
                        show('source', source.id);
                      }}
                    >
                      <strong>{source.title}</strong>
                      <span className={`source-status status-${source.status}`}>
                        {t(
                          source.job?.type === 'source_web_images' &&
                            ['queued', 'running'].includes(source.job.status)
                            ? source.job.stage === 'fetching_images'
                              ? '正在下载网页图片'
                              : '正在识别网页图片'
                            : (statusText[source.status] ?? source.status),
                        )}
                        {source.job?.status === 'running'
                          ? ` · ${Math.round(source.job.progress * 100)}%`
                          : ''}
                      </span>
                    </button>
                    <button
                      className="icon-button remove-source"
                      aria-label={t('移除 {{v1}}', { v1: source.title })}
                      onClick={() => {
                        setModalError('');
                        setRemoving(source);
                        setPermanent(false);
                      }}
                    >
                      <Trash2 size={13} />
                    </button>
                    {['failed', 'parsed'].includes(source.status) && (
                      <div className="source-failure">
                        {(source.error_code || source.error_message) && <p>{errorText(source)}</p>}
                        <button
                          className="button ghost"
                          onClick={async () => {
                            try {
                              await api(`/sources/${source.id}/retry`, { method: 'POST' });
                              await refresh();
                            } catch (e) {
                              setError((e as Error).message);
                            }
                          }}
                        >
                          <RotateCcw size={12} />{' '}
                          {source.status === 'parsed' ? t('准备问答检索') : t('重试')}
                        </button>
                      </div>
                    )}
                  </div>
                ))}
              </div>
              {!libraryLoading && !loadError && !sources.length && (
                <div className="empty-panel">
                  <FileText size={28} />
                  <h4>{t('从原始资料开始')}</h4>
                  <p>{t('导入书籍、论文或笔记，保留每一段发现的出处。')}</p>
                </div>
              )}
            </>
          ) : (
            <>
              <div className="panel-title">
                <FileText size={18} />
                <h3>{t('知识页')}</h3>
                <span className="count">{pages.length}</span>
              </div>
              <div className="knowledge-create">
                <button
                  className="button secondary"
                  disabled={generating || !selected}
                  onClick={() => void generate({ kind: 'selected' })}
                >
                  <Plus size={15} /> {t('生成知识页')}
                </button>
                <p>
                  {t('完整阅读所选的 {{v1}} 份资料，整理概念、关系和洞见，并保留原文引用。', {
                    v1: selected,
                  })}
                </p>
              </div>
              <div className="knowledge-list">
                {pages.map((p) => (
                  <button
                    className={knowledgeId === p.id ? 'active' : ''}
                    key={p.id}
                    onClick={() => {
                      if (knowledgeId === p.id) return;
                      show('knowledge', p.id, { library: 'knowledge' });
                    }}
                  >
                    <strong>
                      {p.generation_metadata?.title_pending && !p.content_markdown
                        ? t('正在生成知识页')
                        : p.title}
                    </strong>
                    <small>
                      {p.job?.status === 'queued'
                        ? t('排队中…')
                        : p.job?.status === 'running'
                          ? t('正在生成…')
                          : p.job?.status === 'failed'
                            ? t('生成失败，请打开查看原因。')
                            : p.content_markdown
                              ? t('已保存 · 可编辑')
                              : t('等待生成')}
                    </small>
                  </button>
                ))}
              </div>
              {!libraryLoading && !loadError && !pages.length && (
                <div className="empty-panel">
                  <FileText size={28} />
                  <h4>{t('让理解留存')}</h4>
                  <p>{t('从所选资料或阅读中的章节生成知识页。')}</p>
                </div>
              )}
            </>
          )}
        </aside>
        <main id="workspace-main" className="workspace-panel chat-panel">
          {opening ? (
            <p className="loading-state" role="status">
              {t('正在打开正文…')}
            </p>
          ) : viewError ? (
            <div className="empty-panel">
              <p role="alert">{t(viewError)}</p>
              <button className="button secondary" onClick={() => show('chat')}>
                {t('返回对话')}
              </button>
            </div>
          ) : deckId ? (
            <DeckView
              key={deckId}
              id={deckId}
              onBack={() => show('chat')}
              onChanged={() => void refresh()}
              onDeleted={() => {
                setDecks((current) => current.filter((deck) => deck.id !== deckId));
                show('chat', undefined, {}, false);
                void refresh();
              }}
              selectedSlideId={route.slideId}
              onSelectSlide={slideLocation}
              onOpenSource={openSource}
              onOpenKnowledge={(pageId) => show('knowledge', pageId)}
              onGeneratedCopy={(deck) => {
                show('deck', deck.id);
                void refresh();
              }}
            />
          ) : knowledgeId ? (
            <Knowledge
              key={knowledgeId}
              pageId={knowledgeId}
              selectedCount={selected}
              onBack={() => show('chat')}
              onChanged={refresh}
              onOpenSource={openSource}
              onGenerateDeck={() =>
                setDeckCreation({
                  scope: { kind: 'knowledge', knowledge_page_id: knowledgeId },
                  label: t('当前知识页'),
                })
              }
            />
          ) : reader ? (
            <Reader
              key={reader.id}
              source={reader}
              initialBlockId={readerBlock}
              initialNodeId={route.nodeId}
              onLocationChange={readerLocation}
              onClose={() => show('chat')}
              onGenerate={(scope) => void generate(scope)}
              generating={generating}
              onGenerateDeck={(scope, label) => setDeckCreation({ scope, label })}
              onTransform={async (kind, scope) => {
                setGenerating(true);
                setError('');
                try {
                  const result = await api<{ id: string }>(
                    `/notebooks/${notebook.id}/transformations`,
                    {
                      method: 'POST',
                      body: JSON.stringify({ kind, scope, language: outputLanguage }),
                    },
                  );
                  setTransformationId(result.id);
                } catch (e) {
                  setError((e as Error).message);
                } finally {
                  setGenerating(false);
                }
              }}
              onAsk={(scope, label) => {
                setScopeLabel(label);
                show('chat', undefined, { scope });
              }}
            />
          ) : (
            <Chat
              language={outputLanguage}
              notebookId={notebook.id}
              selectedCount={selected}
              scope={chatScope}
              scopeLabel={scopeLabel}
              onResetScope={() => {
                show('chat', undefined, { scope: { kind: 'selected' } });
              }}
              onOpenSource={openSource}
              onSaveKnowledge={async (messageId) => {
                const page = await api<KnowledgePage>(
                  `/notebooks/${notebook.id}/knowledge/from-message`,
                  {
                    method: 'POST',
                    body: JSON.stringify({ message_id: messageId, title: t('保存的理解') }),
                  },
                );
                show('knowledge', page.id, { library: 'knowledge' });
                await refresh();
              }}
            />
          )}
        </main>
        <aside id="workspace-studio" className="workspace-panel studio-panel">
          <div className="panel-title">
            <Layers size={18} />
            <h3>{t('演示文稿')}</h3>
          </div>
          <div className="studio-create">
            {!sources.length && !pages.length && (
              <p className="help">{t('先添加资料，再生成演示文稿。')}</p>
            )}
            <button
              className="button secondary"
              disabled={!sources.length && !pages.length}
              onClick={() => setDeckCreation({ scope: { kind: 'selected' }, label: t('所选资料') })}
            >
              <Plus size={15} /> {t('生成 Visual Deck')}
            </button>
          </div>
          <div className="deck-library">
            {batchNotice > 1 && (
              <p className="help" role="status">
                {t('已创建 {{count}} 份 Deck，可分别查看生成进度。', { count: batchNotice })}
              </p>
            )}
            <ArtifactBatchDownload
              notebookId={notebook.id}
              items={decks.map((deck) => ({ ...deck, kind: 'deck' as const }))}
              renderItem={(deck, selection) => {
                const active = ['queued', 'running'].includes(deck.job_status ?? '');
                const stopped =
                  !active && (deck.status === 'paused' || deck.job_status === 'cancelled');
                return (
                  <div key={deck.id} className={`deck-card${deckId === deck.id ? ' active' : ''}`}>
                    {selection}
                    <button className="deck-open" onClick={() => show('deck', deck.id)}>
                      <strong>{deck.title}</strong>
                      {deck.batch_label && (
                        <small className="deck-origin">{deck.batch_label}</small>
                      )}
                      <small>
                        {t('{{v1}} 页 · {{v2}}', {
                          v1: deck.slide_count,
                          v2: t(
                            stopped
                              ? '已停止'
                              : deck.job_status === 'queued'
                                ? '等待生成'
                                : (deckStatus[deck.status] ?? deck.status),
                          ),
                        })}
                      </small>
                    </button>
                    <div className="deck-card-actions">
                      {(active || stopped) && (
                        <button
                          className="button ghost"
                          disabled={deckAction === deck.id}
                          onClick={async () => {
                            setDeckAction(deck.id);
                            setError('');
                            try {
                              await api(`/decks/${deck.id}/${active ? 'stop' : 'resume'}`, {
                                method: 'POST',
                              });
                              await refresh();
                            } catch (e) {
                              setError((e as Error).message);
                            } finally {
                              setDeckAction(undefined);
                            }
                          }}
                        >
                          {t(active ? '停止生成' : '继续生成')}
                        </button>
                      )}
                      <button
                        className="button ghost danger-text"
                        disabled={deckAction === deck.id}
                        aria-label={t('删除 Deck · {{title}}', { title: deck.title })}
                        onClick={() => setDeletingDeck(deck)}
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
          {!decks.length && (
            <div className="empty-panel">
              <Layers size={28} />
              <h4>{t('将理解变成表达')}</h4>
              <p>{t('基于资料沉淀知识，再生成用于理解与分享的 Visual Deck。')}</p>
            </div>
          )}
        </aside>
      </div>
      {deletingDeck && (
        <DeckDeleteDialog
          id={deletingDeck.id}
          title={deletingDeck.title}
          onClose={() => setDeletingDeck(undefined)}
          onDeleted={() => {
            if (liveRoute.current.view === 'deck' && liveRoute.current.itemId === deletingDeck.id)
              show('chat', undefined, {}, false);
            setDecks((current) => current.filter((deck) => deck.id !== deletingDeck.id));
            setDeletingDeck(undefined);
            void refresh();
          }}
        />
      )}
      {deckCreation && (
        <CreateDeck
          initialLanguage={outputLanguage}
          notebookId={notebook.id}
          initialScope={deckCreation.scope}
          initialLabel={deckCreation.label}
          sources={sources}
          pages={pages}
          onClose={() => setDeckCreation(undefined)}
          onCreated={(deck, count = 1) => {
            setDeckCreation(undefined);
            setBatchNotice(count);
            show('deck', deck.id);
            void refresh();
          }}
        />
      )}
      {transformationId && (
        <Transformation
          id={transformationId}
          onClose={() => setTransformationId(undefined)}
          onOpenSource={openSource}
          onSaved={(page) => {
            setTransformationId(undefined);
            show('knowledge', page.id, { library: 'knowledge' });
            void refresh();
          }}
        />
      )}
      {removing && (
        <Modal onClose={() => setRemoving(null)} busy={modalBusy}>
          <section
            className="small-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="remove-title"
          >
            <h2 id="remove-title">{t('移除「{{v1}}」？', { v1: removing.title })}</h2>
            <p>
              {permanent
                ? t('将永久删除原文件与索引。已有对话、知识与 Deck 会保留，引用会标记原文不可用。')
                : t('仅从此笔记本移除，原始资料仍保留在本地。')}
            </p>
            <label className="checkbox-line">
              <input
                type="checkbox"
                checked={permanent}
                disabled={modalBusy}
                onChange={(e) => setPermanent(e.target.checked)}
              />{' '}
              {t('从本地资料库永久删除')}
            </label>
            {modalError && (
              <p className="error" role="alert">
                {t(modalError)}
              </p>
            )}
            <div className="dialog-actions">
              <button
                className="button secondary"
                disabled={modalBusy}
                onClick={() => setRemoving(null)}
              >
                {t('取消')}
              </button>
              <button
                className="button danger-button"
                disabled={modalBusy}
                onClick={async () => {
                  if (modalBusy) return;
                  setModalBusy(true);
                  setModalError('');
                  try {
                    await api(
                      permanent
                        ? `/sources/${removing.id}`
                        : `/notebooks/${notebook.id}/sources/${removing.id}`,
                      { method: 'DELETE' },
                    );
                    if (reader?.id === removing.id) show('chat');
                    await refresh();
                    setRemoving(null);
                  } catch (e) {
                    setModalError((e as Error).message);
                  } finally {
                    setModalBusy(false);
                  }
                }}
              >
                {permanent ? t('永久删除资料') : t('从笔记本移除')}
              </button>
            </div>
          </section>
        </Modal>
      )}
    </div>
  );
}
