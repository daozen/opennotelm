import Modal from './Modal';
import CreatePodcast, { CreateMindMap } from './CreatePodcast';
import MindMapView, { mindmapStatus } from './MindMap';
import ArtifactStudio, { kindLabel, type StudioItem } from './ArtifactStudio';
import ArtifactDeleteDialog, { artifactPath, type ArtifactKind } from './ArtifactDeleteDialog';
import PodcastView, { podcastStatus } from './Podcast';
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
  type PodcastSummary,
  type MindMap,
  type SourceNode,
} from './api';
import Reader from './Reader';
import SourceImport from './SourceImport';
import Chat from './Chat';
import Knowledge from './Knowledge';
import Transformation from './Transformation';
import DeckView, { CreateDeck, deckStatus } from './Deck';
import DeckDeleteDialog from './DeckDeleteDialog';

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
  const [podcasts, setPodcasts] = useState<PodcastSummary[]>([]);
  const [podcastCreation, setPodcastCreation] = useState(false);
  const [decks, setDecks] = useState<DeckSummary[]>([]);
  const [deletingDeck, setDeletingDeck] = useState<DeckSummary>();
  const [mindmaps, setMindmaps] = useState<MindMap[]>([]);
  const [mapCreation, setMapCreation] = useState(false);
  const [deletingArtifact, setDeletingArtifact] = useState<StudioItem>();
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
  const mindmapId = route.view === 'mindmap' ? route.itemId : undefined;
  const podcastId = route.view === 'podcast' ? route.itemId : undefined;
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
        mapNodeId: undefined,
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
    const [result, knowledgeList, deckList, podcastList, mapList] = await Promise.all([
      api<Source[]>(`/notebooks/${notebook.id}/sources`),
      api<KnowledgePage[]>(`/notebooks/${notebook.id}/knowledge`),
      api<DeckSummary[]>(`/notebooks/${notebook.id}/decks`),
      api<PodcastSummary[]>(`/notebooks/${notebook.id}/podcasts`),
      api<MindMap[]>(`/notebooks/${notebook.id}/mindmaps`),
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
    if (deckVersion === deckRefreshVersion.current) {
      setDecks(deckList);
      setPodcasts(podcastList);
      setMindmaps(mapList);
    }
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
  const artifactItems: StudioItem[] = [
    ...decks.map((d) => ({
      id: d.id,
      kind: 'deck' as const,
      title: d.title,
      status: d.status,
      jobStatus: d.job_status,
      statusLabel:
        d.job_status === 'cancelled'
          ? '已停止'
          : d.job_status === 'queued'
            ? '等待生成'
            : (deckStatus[d.status] ?? d.status),
      summary: t('{{v1}} 页', { v1: d.slide_count }),
      createdAt: d.created_at ?? d.updated_at,
      download_available: d.download_available,
      resumable: ['failed', 'cancelled'].includes(d.job_status ?? ''),
    })),
    ...podcasts.map((p) => ({
      id: p.id,
      kind: 'podcast' as const,
      title: p.title,
      status: p.status,
      jobStatus: p.job?.status,
      statusLabel: podcastStatus[p.job?.status === 'cancelled' ? 'paused' : p.status] ?? '等待生成',
      summary: t('目标约 {{minutes}} 分钟', { minutes: p.input.target_minutes }),
      createdAt: p.created_at,
      download_available: p.download_available,
      resumable:
        !!p.job && !['queued', 'running'].includes(p.job.status) && p.status !== 'completed',
    })),
    ...mindmaps.map((m) => ({
      id: m.id,
      kind: 'mindmap' as const,
      title: m.title,
      status: m.status,
      jobStatus: m.job?.status,
      statusLabel: mindmapStatus[m.job?.status === 'cancelled' ? 'paused' : m.status] ?? '等待生成',
      summary: t('{{count}} 个节点', { count: m.node_count ?? 0 }),
      createdAt: m.created_at,
      download_available: m.download_available,
      resumable: ['failed', 'cancelled'].includes(m.job?.status ?? ''),
    })),
  ];
  const creationScope: DeckScope =
    route.view === 'knowledge' && knowledgeId
      ? { kind: 'knowledge', knowledge_page_id: knowledgeId }
      : route.view === 'source' && reader
        ? route.nodeId
          ? { kind: 'node', source_id: reader.id, node_id: route.nodeId }
          : { kind: 'source', source_id: reader.id }
        : chatScope;
  const creationLabel = reader?.title ?? t('所选资料');
  const studio = (compact: boolean) => (
    <ArtifactStudio
      notebookId={notebook.id}
      items={artifactItems}
      activeKey={route.itemId ? `${route.view}:${route.itemId}` : undefined}
      filter={route.artifactKind}
      onFilter={(artifactKind) => go({ ...route, artifactKind }, { guarded: false, replace: true })}
      onOpen={(item) => show(item.kind, item.id)}
      onCreate={(kind) => {
        if (kind === 'deck') setDeckCreation({ scope: creationScope, label: creationLabel });
        else if (kind === 'podcast') setPodcastCreation(true);
        else setMapCreation(true);
      }}
      onAction={async (item, action) => {
        await api(`/${artifactPath(item.kind)}/${item.id}/${action}`, { method: 'POST' });
        await refresh();
      }}
      onDelete={(item) => {
        if (item.kind === 'deck') setDeletingDeck(decks.find((d) => d.id === item.id));
        else setDeletingArtifact(item);
      }}
      canCreate={!!sources.length || !!pages.length}
      compact={compact}
    />
  );
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
      <nav className="workspace-view-nav" aria-label={t('主要视图')}>
        <button
          className={`button ${route.view === 'chat' ? 'primary' : 'secondary'}`}
          onClick={() => show('chat')}
        >
          {t('对话')}
        </button>
        <button
          className={`button ${route.view === 'artifacts' ? 'primary' : 'secondary'}`}
          onClick={() => show('artifacts')}
        >
          {t('全部产物')}
        </button>
        {['deck', 'podcast', 'mindmap'].includes(route.view) && (
          <label>
            {t('切换产物')}
            <select
              aria-label={t('切换产物')}
              value={`${route.view}:${route.itemId}`}
              onChange={(e) => {
                const [kind, id] = e.target.value.split(':');
                show(kind as ArtifactKind, id);
              }}
            >
              {artifactItems.map((item) => (
                <option key={`${item.kind}:${item.id}`} value={`${item.kind}:${item.id}`}>
                  {kindLabel(item.kind)} · {item.title}
                </option>
              ))}
            </select>
          </label>
        )}
      </nav>
      {batchNotice > 1 && (
        <p className="help" role="status">
          {t('已创建 {{count}} 个产物，可分别查看生成进度。', { count: batchNotice })}
        </p>
      )}
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
      {route.view !== 'artifacts' && (
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
              {t({ library: '资料与知识', main: '工作区', studio: '创作空间' }[panel])}
            </button>
          ))}
        </nav>
      )}
      <div
        className="workspace-columns"
        data-panel={compactPanel}
        data-artifacts={route.view === 'artifacts'}
      >
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
          {route.view === 'artifacts' ? (
            <>
              <div className="panel-title">
                <Layers size={20} />
                <h2>{t('创作空间')}</h2>
              </div>

              {studio(false)}
            </>
          ) : mindmapId ? (
            <MindMapView
              key={mindmapId}
              id={mindmapId}
              selectedNodeId={route.mapNodeId}
              onSelectNode={(mapNodeId) =>
                go({ ...route, mapNodeId }, { guarded: false, replace: true })
              }
              onBack={() => show('artifacts')}
              onChanged={() => void refresh()}
              onDeleted={() => {
                setMindmaps((list) => list.filter((m) => m.id !== mindmapId));
                show('artifacts', undefined, {}, false);
                void refresh();
              }}
              onOpenSource={openSource}
              onOpenKnowledge={(pageId) => show('knowledge', pageId)}
            />
          ) : opening ? (
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
          ) : podcastId ? (
            <PodcastView
              key={podcastId}
              id={podcastId}
              onBack={() => show('artifacts')}
              backLabel={t('返回创作空间')}
              onChanged={() => void refresh()}
              onDeleted={() => {
                setPodcasts((current) => current.filter((podcast) => podcast.id !== podcastId));
                show('artifacts', undefined, {}, false);
                void refresh();
              }}
              onOpenSource={openSource}
              onOpenKnowledge={(pageId) => show('knowledge', pageId)}
            />
          ) : deckId ? (
            <DeckView
              key={deckId}
              id={deckId}
              onBack={() => show('artifacts')}
              backLabel={t('返回创作空间')}
              onChanged={() => void refresh()}
              onDeleted={() => {
                setDecks((current) => current.filter((deck) => deck.id !== deckId));
                show('artifacts', undefined, {}, false);
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
            <h3>{t('创作空间')}</h3>
          </div>
          {route.view !== 'artifacts' && (
            <>
              <button className="button ghost" onClick={() => show('artifacts')}>
                {t('打开完整创作空间')}
              </button>
              {studio(true)}
            </>
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
              show('artifacts', undefined, {}, false);
            setDecks((current) => current.filter((deck) => deck.id !== deletingDeck.id));
            setDeletingDeck(undefined);
            void refresh();
          }}
        />
      )}
      {deletingArtifact && (
        <ArtifactDeleteDialog
          kind={deletingArtifact.kind}
          id={deletingArtifact.id}
          title={deletingArtifact.title}
          onClose={() => setDeletingArtifact(undefined)}
          onDeleted={() => {
            if (liveRoute.current.itemId === deletingArtifact.id)
              show('artifacts', undefined, {}, false);
            setPodcasts((list) => list.filter((p) => p.id !== deletingArtifact.id));
            setMindmaps((list) => list.filter((m) => m.id !== deletingArtifact.id));
            setDeletingArtifact(undefined);
            void refresh();
          }}
        />
      )}
      {mapCreation && (
        <CreateMindMap
          notebookId={notebook.id}
          initialScope={creationScope}
          initialLabel={creationLabel}
          initialLanguage={outputLanguage}
          sources={sources}
          pages={pages}
          onClose={() => setMapCreation(false)}
          onCreated={(m, count = 1) => {
            setMapCreation(false);
            setBatchNotice(count);
            show('mindmap', m.id);
            void refresh();
          }}
        />
      )}
      {podcastCreation && (
        <CreatePodcast
          notebookId={notebook.id}
          initialScope={creationScope}
          initialLabel={creationLabel}
          initialLanguage={outputLanguage}
          sources={sources}
          pages={pages}
          onClose={() => setPodcastCreation(false)}
          onCreated={(p, count = 1) => {
            setBatchNotice(count);
            setPodcastCreation(false);
            show('podcast', p.id);
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
