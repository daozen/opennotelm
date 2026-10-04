import Modal from './Modal';
import { t, useI18n } from './i18n';
import { useEffect, useState } from 'react';
import { ArrowUpRight, BookOpen, Ellipsis, Plus, Settings2, Trash2, X } from 'lucide-react';
import { api, type ModelSettings, type Notebook } from './api';
import Setup from './Setup';
import LanguageSettings, { LanguagePreferencesProvider } from './LanguageSettings';
import Workspace from './Workspace';
import { NavigationGuardProvider } from './NavigationGuard';
import { NavigationProvider, routeUrl, useNavigation } from './Navigation';

function NotebookEditor({
  notebook,
  onClose,
  onSave,
}: {
  notebook?: Notebook;
  onClose: () => void;
  onSave: (title: string, description: string) => Promise<void>;
}) {
  useI18n();
  const [title, setTitle] = useState(notebook?.title ?? '');
  const [description, setDescription] = useState(notebook?.description ?? '');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  return (
    <Modal onClose={onClose} busy={busy}>
      <form
        className="small-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="notebook-title"
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true);
          try {
            await onSave(title, description);
          } catch (e) {
            setError((e as Error).message);
          } finally {
            setBusy(false);
          }
        }}
      >
        <div className="dialog-top">
          <h2 id="notebook-title">{notebook ? t('编辑笔记本') : t('创建笔记本')}</h2>
          <button
            type="button"
            className="icon-button"
            disabled={busy}
            onClick={onClose}
            aria-label={t('关闭')}
          >
            <X size={20} />
          </button>
        </div>
        <label>
          {t('笔记本名称')}
          <input
            autoFocus
            data-modal-focus
            required
            maxLength={200}
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder={t('例如：哲学阅读、产品调研')}
          />
        </label>
        <label>
          {t('描述（可选）')}
          <textarea
            maxLength={2000}
            rows={3}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder={t('简要说明这个笔记本的主题或用途')}
          />
        </label>
        {error && (
          <p className="error" role="alert">
            {t(error)}
          </p>
        )}
        <button className="button primary" disabled={busy || !title.trim()}>
          {busy ? t('保存中…') : t('保存笔记本')}
        </button>
      </form>
    </Modal>
  );
}

function Application() {
  const uiLanguage = useI18n();
  const { route, go } = useNavigation();
  const [notebooks, setNotebooks] = useState<Notebook[]>([]);
  const [models, setModels] = useState<ModelSettings>({ setup_complete: false, models: {} });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [setup, setSetup] = useState(false);
  const [editor, setEditor] = useState<Notebook | 'new' | null>(null);
  const current = notebooks.find((n) => n.id === route.notebookId);
  const [menu, setMenu] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<Notebook | null>(null);
  const [deleteBusy, setDeleteBusy] = useState(false);
  const [deleteError, setDeleteError] = useState('');
  useEffect(() => {
    if (!menu) return;
    const dismiss = (event: PointerEvent) => {
      if (!(event.target instanceof Element) || !event.target.closest('.card-top')) setMenu(null);
    };
    const escape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setMenu(null);
    };
    document.addEventListener('pointerdown', dismiss);
    document.addEventListener('keydown', escape);
    return () => {
      document.removeEventListener('pointerdown', dismiss);
      document.removeEventListener('keydown', escape);
    };
  }, [menu]);

  async function refresh() {
    setNotebooks(await api<Notebook[]>('/notebooks'));
  }
  async function load() {
    setLoading(true);
    setError('');
    try {
      const [items, settings] = await Promise.all([
        api<Notebook[]>('/notebooks'),
        api<ModelSettings>('/settings/models'),
      ]);
      setNotebooks(items);
      setModels(settings);
      setSetup((open) => open || !settings.setup_complete);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    void load();
  }, []);

  useEffect(() => {
    if (route.view === 'home' && !loading) void refresh().catch((e) => setError(e.message));
  }, [route.view]);

  useEffect(() => {
    document.title = current ? `${current.title} · OpenNoteLM` : `OpenNoteLM · ${t('知识工作台')}`;
  }, [current?.title, uiLanguage]);

  return (
    <div className="app-shell">
      <header className="app-header">
        <button className="brand" onClick={() => go({ view: 'home' })}>
          <span className="brand-mark">
            <BookOpen size={23} strokeWidth={1.8} />
          </span>
          <span>
            OpenNoteLM<span className="brand-sub">{t('知识工作台')}</span>
          </span>
        </button>
        <div className="header-actions">
          <LanguageSettings />
          <span className="local-status" title={t('本地保存资料；AI 请求发送到已配置的模型服务。')}>
            <span /> {t('本地优先')}
          </span>
          <button className="button secondary" disabled={loading} onClick={() => setSetup(true)}>
            <Settings2 size={16} /> {t('模型设置')}
          </button>
        </div>
      </header>
      {error && (
        <div className="global-error" role="alert">
          {t(error)}
          <button className="button ghost" onClick={load}>
            {t('重试')}
          </button>
        </div>
      )}
      {route.view === 'missing' || (!loading && route.notebookId && !current && !error) ? (
        <main className="home">
          <p role="alert">{t('此页面不存在，或笔记本已被删除。')}</p>
          <button className="button secondary" onClick={() => go({ view: 'home' })}>
            {t('返回笔记本列表')}
          </button>
        </main>
      ) : loading && route.notebookId ? (
        <p className="loading-state" role="status">
          {t('正在打开你的工作台…')}
        </p>
      ) : current ? (
        <Workspace key={current.id} notebook={current} onBack={() => go({ view: 'home' })} />
      ) : route.notebookId ? (
        <main className="home">
          <button className="button secondary" onClick={() => go({ view: 'home' })}>
            {t('返回笔记本列表')}
          </button>
        </main>
      ) : (
        <main className="home">
          <div className="hero">
            <div>
              <p className="eyebrow">{t('A PLACE FOR DEEPER UNDERSTANDING')}</p>
              <h1>{t('把资料，变成你的理解。')}</h1>
              <p className="hero-description">
                {t('阅读、提问、沉淀知识。让每一个想法，都有出处。')}
              </p>
            </div>
            <div className="hero-art" aria-hidden="true">
              <span className="art-orbit" />
              <BookOpen size={58} strokeWidth={1} />
              <span className="art-dot" />
            </div>
          </div>
          <div className="section-header">
            <div>
              <h2>
                {t('我的笔记本')}
                <span className="count">{notebooks.length}</span>
              </h2>
              <p>{t('一个笔记本，一次深入探索。')}</p>
            </div>
            <button className="button primary" onClick={() => setEditor('new')} disabled={loading}>
              <Plus size={17} /> {t('创建笔记本')}
            </button>
          </div>
          {loading ? (
            <p className="loading-state" role="status">
              {t('正在打开你的工作台…')}
            </p>
          ) : (
            <div className="notebook-grid">
              <button className="create-card" onClick={() => setEditor('new')}>
                <span className="create-icon">
                  <Plus size={25} />
                </span>
                <strong>{t('创建笔记本')}</strong>
                <span>{t('从好奇心开始')}</span>
              </button>
              {notebooks.map((n, index) => (
                <article className="notebook-card" key={n.id}>
                  <div className="card-top">
                    <span className={`notebook-symbol shade-${index % 4}`}>
                      <BookOpen size={22} strokeWidth={1.6} />
                    </span>
                    <button
                      className="icon-button"
                      aria-label={t('管理 {{v1}}', { v1: n.title })}
                      aria-expanded={menu === n.id}
                      onClick={() => setMenu(menu === n.id ? null : n.id)}
                    >
                      <Ellipsis size={20} />
                    </button>
                    {menu === n.id && (
                      <div className="card-menu">
                        <button
                          onClick={() => {
                            setEditor(n);
                            setMenu(null);
                          }}
                        >
                          {t('编辑名称与描述')}
                        </button>
                        <button
                          className="danger"
                          onClick={() => {
                            setDeleteError('');
                            setDeleting(n);
                            setMenu(null);
                          }}
                        >
                          <Trash2 size={14} /> {t('删除笔记本')}
                        </button>
                      </div>
                    )}
                  </div>
                  <a
                    className="card-open"
                    href={routeUrl({ view: 'chat', notebookId: n.id })}
                    onClick={(event) => {
                      if (
                        event.button ||
                        event.metaKey ||
                        event.ctrlKey ||
                        event.shiftKey ||
                        event.altKey
                      )
                        return;
                      event.preventDefault();
                      go({ view: 'chat', notebookId: n.id });
                    }}
                  >
                    <h3>{n.title}</h3>
                    <p>{n.description || t('在这里，收集资料与新的发现。')}</p>
                    <span className="card-counts">
                      {t('{{v1}} 份资料 · {{v2}} 篇知识 ·  {{v3}} 份 Deck', {
                        v1: n.source_count ?? 0,
                        v2: n.knowledge_count ?? 0,
                        v3: n.deck_count ?? 0,
                      })}
                    </span>
                  </a>
                  <div className="card-bottom">
                    <time>
                      {t('{{v1}}  更新', {
                        v1: new Date(n.updated_at).toLocaleDateString(uiLanguage, {
                          month: 'short',
                          day: 'numeric',
                        }),
                      })}
                    </time>
                    <button
                      className="icon-button"
                      aria-label={t('打开 {{v1}}', { v1: n.title })}
                      onClick={() => go({ view: 'chat', notebookId: n.id })}
                    >
                      <ArrowUpRight size={18} />
                    </button>
                  </div>
                </article>
              ))}
            </div>
          )}
          {notebooks.length === 0 && !loading && (
            <p className="home-hint">
              {t('你的 EPUB、研究论文和阅读笔记，都可以成为下一段探索的起点。')}
            </p>
          )}
          <footer className="home-footer">
            <span>{t('OPEN SOURCE. OPEN POSSIBILITIES.')}</span>
            <span>{t('你的资料 · 你的模型 · 你的知识')}</span>
          </footer>
        </main>
      )}
      {setup && <Setup settings={models} onSaved={setModels} onClose={() => setSetup(false)} />}
      {editor && (
        <NotebookEditor
          notebook={editor === 'new' ? undefined : editor}
          onClose={() => setEditor(null)}
          onSave={async (title, description) => {
            await api(editor === 'new' ? '/notebooks' : `/notebooks/${editor.id}`, {
              method: editor === 'new' ? 'POST' : 'PATCH',
              body: JSON.stringify({ title, description }),
            });
            await refresh();
            setEditor(null);
          }}
        />
      )}
      {deleting && (
        <Modal onClose={() => setDeleting(null)} busy={deleteBusy}>
          <section
            className="small-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="delete-title"
          >
            <h2 id="delete-title">{t('删除「{{v1}}」？', { v1: deleting.title })}</h2>
            <p>{t('笔记本中的对话、知识与产物将被删除。原始资料会保留在本地资料库中。')}</p>
            <p>{t('删除后无法恢复。')}</p>
            {deleteError && (
              <p className="error" role="alert">
                {t(deleteError)}
              </p>
            )}
            <div className="dialog-actions">
              <button
                className="button secondary"
                disabled={deleteBusy}
                onClick={() => setDeleting(null)}
              >
                {t('取消')}
              </button>
              <button
                className="button danger-button"
                disabled={deleteBusy}
                onClick={async () => {
                  if (deleteBusy) return;
                  setDeleteBusy(true);
                  setDeleteError('');
                  try {
                    await api(`/notebooks/${deleting.id}`, { method: 'DELETE' });
                    await refresh();
                    setDeleting(null);
                  } catch (e) {
                    setDeleteError((e as Error).message);
                  } finally {
                    setDeleteBusy(false);
                  }
                }}
              >
                {t(deleteBusy ? '正在删除…' : '删除笔记本')}
              </button>
            </div>
          </section>
        </Modal>
      )}
    </div>
  );
}

export default function App() {
  useI18n();
  return (
    <LanguagePreferencesProvider>
      <NavigationGuardProvider>
        <NavigationProvider>
          <Application />
        </NavigationProvider>
      </NavigationGuardProvider>
    </LanguagePreferencesProvider>
  );
}
