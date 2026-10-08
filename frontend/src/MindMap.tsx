import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ArrowLeft, Maximize, Minus, Plus, Download, X } from 'lucide-react';
import { api, type MindMap as MapData, type MindMapNode } from './api';
import { t, useI18n, errorText } from './i18n';
import { CitationPreview } from './Citations';
import Modal from './Modal';
import ArtifactInstructionDetails from './ArtifactInstructionDetails';
import DeckSources from './DeckSources';
import DeckDiagnostics from './DeckDiagnostics';
import ArtifactDeleteDialog from './ArtifactDeleteDialog';
import { mapLayout, mapSvg, branchColors, labelDirection } from './mindmapLayout';
import { useUnsavedChanges } from './NavigationGuard';

export const mindmapStatus: Record<string, string> = {
  queued: '等待生成',
  mindmap_reading: '理解资料',
  mindmap_mapping: '梳理概念关系',
  mindmap_exporting: '准备导出',
  completed: '已完成',
  failed: '生成失败',
  paused: '已停止',
};
function Canvas({
  nodes,
  selected,
  onSelect,
}: {
  nodes: MindMapNode[];
  selected?: string;
  onSelect: (id: string) => void;
}) {
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
  const layout = useMemo(() => mapLayout(nodes, collapsed), [nodes, collapsed]);
  const host = useRef<HTMLDivElement>(null);
  const surface = useRef<SVGSVGElement>(null);
  const [view, setView] = useState({ x: 0, y: 0, scale: 1 });
  const drag = useRef<
    { pointer: number; x: number; y: number; vx: number; vy: number } | undefined
  >(undefined);
  const fit = useCallback(() => {
    const box = host.current?.getBoundingClientRect();
    if (!box) return;
    const scale = Math.min(
      1.3,
      Math.max(0.08, Math.min(box.width / layout.width, box.height / layout.height) * 0.94),
    );
    setView({
      scale,
      x: (box.width - layout.width * scale) / 2,
      y: (box.height - layout.height * scale) / 2,
    });
  }, [layout]);
  useEffect(() => {
    fit();
    const observer = new ResizeObserver(fit);
    if (host.current) observer.observe(host.current);
    return () => observer.disconnect();
  }, [fit]);
  const zoomAt = useCallback((factor: number, point?: { x: number; y: number }) => {
    const box = surface.current?.getBoundingClientRect();
    if (!box || !Number.isFinite(factor) || factor <= 0) return;
    const x = point ? point.x - box.left : box.width / 2;
    const y = point ? point.y - box.top : box.height / 2;
    setView((old) => {
      const scale = Math.min(2.5, Math.max(0.08, old.scale * factor));
      return {
        scale,
        x: x - ((x - old.x) * scale) / old.scale,
        y: y - ((y - old.y) * scale) / old.scale,
      };
    });
  }, []);
  useEffect(() => {
    const svg = surface.current;
    if (!svg) return;
    let gestureScale: number | undefined;
    const wheel = (event: WheelEvent) => {
      if (!event.cancelable || !Number.isFinite(event.deltaY) || !event.deltaY) return;
      // A non-passive listener is required to stop browser zoom for trackpad pinch.
      event.preventDefault();
      if (gestureScale !== undefined) return;
      drag.current = undefined;
      const unit = event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? svg.clientHeight : 1;
      const delta = Math.max(-100, Math.min(100, event.deltaY * unit));
      zoomAt(Math.exp(-delta * (event.ctrlKey ? 0.01 : 0.002)), {
        x: event.clientX,
        y: event.clientY,
      });
    };
    type Gesture = Event & { scale: number; clientX: number; clientY: number };
    const start = (event: Event) => {
      event.preventDefault();
      gestureScale = 1;
      drag.current = undefined;
    };
    const change = (event: Event) => {
      event.preventDefault();
      const gesture = event as Gesture;
      if (gestureScale === undefined || !Number.isFinite(gesture.scale) || gesture.scale <= 0)
        return;
      const box = svg.getBoundingClientRect();
      const point =
        gesture.clientX >= box.left &&
        gesture.clientX <= box.right &&
        gesture.clientY >= box.top &&
        gesture.clientY <= box.bottom
          ? { x: gesture.clientX, y: gesture.clientY }
          : undefined;
      zoomAt(gesture.scale / gestureScale, point);
      gestureScale = gesture.scale;
    };
    const end = (event: Event) => {
      event.preventDefault();
      gestureScale = undefined;
    };
    svg.addEventListener('wheel', wheel, { passive: false });
    // Safari reports native trackpad pinches as gesture events instead of Ctrl+wheel.
    svg.addEventListener('gesturestart', start, { passive: false });
    svg.addEventListener('gesturechange', change, { passive: false });
    svg.addEventListener('gestureend', end, { passive: false });
    return () => {
      svg.removeEventListener('wheel', wheel);
      svg.removeEventListener('gesturestart', start);
      svg.removeEventListener('gesturechange', change);
      svg.removeEventListener('gestureend', end);
    };
  }, [zoomAt]);
  const focusNode = () => {
    const n = layout.nodes.find((n) => n.node.id === selected);
    if (!n) return;
    const box = host.current!.getBoundingClientRect();
    setView({ scale: 1, x: box.width / 2 - n.x - 112, y: box.height / 2 - n.y - n.h / 2 });
  };
  return (
    <div className="mindmap-canvas-shell">
      <div className="mindmap-tools">
        <button className="button secondary" aria-label={t('缩小')} onClick={() => zoomAt(0.8)}>
          <Minus size={16} />
        </button>
        <span>{Math.round(view.scale * 100)}%</span>
        <button className="button secondary" aria-label={t('放大')} onClick={() => zoomAt(1.25)}>
          <Plus size={16} />
        </button>
        <button className="button secondary" onClick={fit}>
          {t('适应画布')}
        </button>
        <button
          className="button secondary"
          disabled={!layout.nodes.some((n) => n.node.id === selected)}
          onClick={focusNode}
        >
          {t('定位选中节点')}
        </button>
        <button className="button ghost" onClick={() => setCollapsed(new Set())}>
          {t('展开全部')}
        </button>
        <button
          className="button ghost"
          onClick={() =>
            setCollapsed(new Set(nodes.filter((n) => n.parent_id !== null).map((n) => n.id)))
          }
        >
          {t('收起分支')}
        </button>
      </div>
      <p className="help">{t('拖动画布移动，点击节点查看解释与出处。')}</p>
      <div ref={host} className="mindmap-canvas">
        <svg
          ref={surface}
          role="group"
          aria-label={t('思维导图画布')}
          width="100%"
          height="100%"
          onPointerDown={(e) => {
            if (e.button !== 0 || (e.target as Element).closest('[data-map-node]')) return;
            drag.current = {
              pointer: e.pointerId,
              x: e.clientX,
              y: e.clientY,
              vx: view.x,
              vy: view.y,
            };
            e.currentTarget.setPointerCapture(e.pointerId);
          }}
          onPointerMove={(e) => {
            const d = drag.current;
            if (d?.pointer === e.pointerId)
              setView((v) => ({ ...v, x: d.vx + e.clientX - d.x, y: d.vy + e.clientY - d.y }));
          }}
          onPointerUp={() => {
            drag.current = undefined;
          }}
          onPointerCancel={() => {
            drag.current = undefined;
          }}
        >
          <g transform={`translate(${view.x} ${view.y}) scale(${view.scale})`}>
            {layout.nodes.map((n) => {
              const p = layout.nodes.find((p) => p.node.id === n.node.parent_id);
              return (
                p && (
                  <path
                    key={`edge:${n.node.id}`}
                    d={`M${p.x + 224},${p.y + p.h / 2} C${p.x + 252},${p.y + p.h / 2} ${n.x - 28},${n.y + n.h / 2} ${n.x},${n.y + n.h / 2}`}
                    fill="none"
                    stroke="#c1cfbf"
                    strokeWidth="2"
                  />
                )
              );
            })}
            {layout.nodes.map((n) => (
              <g key={n.node.id} data-map-node={n.node.id} transform={`translate(${n.x} ${n.y})`}>
                <g
                  role="button"
                  tabIndex={0}
                  aria-label={n.node.label}
                  aria-pressed={selected === n.node.id}
                  onClick={() => onSelect(n.node.id)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      onSelect(n.node.id);
                    }
                  }}
                >
                  <rect
                    width="224"
                    height={n.h}
                    rx="12"
                    fill={selected === n.node.id ? '#eaf1e0' : '#fff'}
                    stroke={branchColors[n.branch % branchColors.length]}
                    strokeWidth={selected === n.node.id ? 3 : 1.5}
                  />
                  <text
                    x={labelDirection(n.node.label) === 'rtl' ? 210 : 14}
                    y="28"
                    fill="#263b30"
                    fontSize="14"
                    direction={labelDirection(n.node.label)}
                    textAnchor="start"
                  >
                    {n.lines.map((line, i) => (
                      <tspan
                        x={labelDirection(n.node.label) === 'rtl' ? 210 : 14}
                        dy={i ? 20 : 0}
                        key={i}
                      >
                        {line}
                      </tspan>
                    ))}
                  </text>
                </g>
                {n.children > 0 && (
                  <g
                    role="button"
                    tabIndex={0}
                    aria-label={t(collapsed.has(n.node.id) ? '展开 {{title}}' : '收起 {{title}}', {
                      title: n.node.label,
                    })}
                    aria-expanded={!collapsed.has(n.node.id)}
                    onClick={() =>
                      setCollapsed((old) => {
                        const next = new Set(old);
                        if (next.has(n.node.id)) next.delete(n.node.id);
                        else next.add(n.node.id);
                        return next;
                      })
                    }
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        e.currentTarget.dispatchEvent(new MouseEvent('click', { bubbles: true }));
                      }
                    }}
                  >
                    <circle cx="224" cy={n.h / 2} r="12" fill="#fff" stroke="#91a487" />
                    <text x="224" y={n.h / 2 + 5} textAnchor="middle" fill="#315b48">
                      {collapsed.has(n.node.id) ? '+' : '−'}
                    </text>
                  </g>
                )}
              </g>
            ))}
          </g>
        </svg>
      </div>
    </div>
  );
}
export default function MindMapView({
  id,
  selectedNodeId,
  onSelectNode,
  onBack,
  onChanged,
  onDeleted,
  onOpenSource,
  onOpenKnowledge,
}: {
  id: string;
  selectedNodeId?: string;
  onSelectNode: (id: string) => void;
  onBack: () => void;
  onChanged: () => void;
  onDeleted: () => void;
  onOpenSource: (sourceId: string, blockId: string) => Promise<void>;
  onOpenKnowledge: (id: string) => void;
}) {
  useI18n();
  const [map, setMap] = useState<MapData>(),
    [error, setError] = useState(''),
    [loadError, setLoadError] = useState(''),
    [busy, setBusy] = useState(false),
    [focus, setFocus] = useState(false),
    [deleting, setDeleting] = useState(false),
    [renaming, setRenaming] = useState(false),
    [title, setTitle] = useState(''),
    [citation, setCitation] = useState<string>(),
    [outline, setOutline] = useState(false);
  useUnsavedChanges(renaming && title !== map?.title);
  const saveMap = useCallback((value: MapData) => {
    // Polling updates task state without resetting a user's canvas viewport.
    setMap((previous) =>
      previous && JSON.stringify(previous.tree) === JSON.stringify(value.tree)
        ? { ...value, tree: previous.tree }
        : value,
    );
  }, []);
  const refresh = useCallback(
    async () => saveMap(await api<MapData>(`/mindmaps/${id}`)),
    [id, saveMap],
  );
  useEffect(() => {
    let active = true;
    const load = () =>
      api<MapData>(`/mindmaps/${id}`).then(
        (value) => {
          if (active) {
            saveMap(value);
            setLoadError('');
          }
        },
        (e) => {
          if (active) setLoadError(e.message);
        },
      );
    void load();
    const timer = setInterval(() => void load(), 1500);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [id, saveMap]);
  const node =
    map?.tree?.nodes.find((n) => n.id === selectedNodeId) ??
    map?.tree?.nodes.find((n) => n.parent_id === null);
  const active = !!map?.job && ['queued', 'running'].includes(map.job.status);
  const action = async (path: string, init: RequestInit = { method: 'POST' }) => {
    setBusy(true);
    setError('');
    try {
      saveMap(await api<MapData>(`/mindmaps/${id}${path}`, init));
      onChanged();
      return true;
    } catch (e) {
      setError((e as Error).message);
      return false;
    } finally {
      setBusy(false);
    }
  };
  const detail = (
    <aside className="mindmap-node-detail">
      <h3 dir="auto">{node?.label}</h3>
      {node?.detail && <p dir="auto">{node.detail}</p>}
      {node && ['background', 'analogy'].includes(node.basis) && (
        <p className="help">{t(node.basis === 'background' ? '背景补充' : '说明性类比')}</p>
      )}
      {node?.evidence_ids.map(
        (ref, i) =>
          map?.citations[ref] && (
            <button
              className="button ghost"
              key={ref}
              onClick={() => setCitation(map.citations[ref])}
            >
              {t('原文引用 {{v1}}', { v1: i + 1 })}
            </button>
          ),
      )}
    </aside>
  );
  const downloadSvg = () => {
    if (!map?.tree) return;
    const url = URL.createObjectURL(
      new Blob([mapSvg(map.tree.nodes, map.title)], { type: 'image/svg+xml' }),
    );
    const link = document.createElement('a');
    link.href = url;
    link.download = map.title.replace(/[\\/:*?"<>|\u0000-\u001f]/g, '_').slice(0, 120) + '.svg';
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  };
  return (
    <section className="mindmap-view" aria-label={t('思维导图')}>
      <button className="button ghost" onClick={onBack}>
        <ArrowLeft size={16} />
        {t('返回创作空间')}
      </button>
      {(error || loadError) && (
        <p className="error" role="alert">
          {t(error || loadError)}{' '}
          <button
            className="button ghost"
            onClick={() =>
              void refresh()
                .then(() => {
                  setError('');
                  setLoadError('');
                })
                .catch((e) => setError(e.message))
            }
          >
            {t('重试')}
          </button>
        </p>
      )}
      {!map ? (
        <p>{t('加载中…')}</p>
      ) : (
        <>
          <div className="podcast-heading">
            <div>
              <span className="badge">{t('思维导图')}</span>
              <h2>{map.title}</h2>
              <p className="help">
                {t(
                  mindmapStatus[map.job?.status === 'cancelled' ? 'paused' : map.status] ??
                    '等待生成',
                )}
                {active && map.job && ` · ${Math.round(map.job.progress * 100)}%`}
              </p>
            </div>
            <button
              className="button secondary"
              disabled={busy || active}
              onClick={() => {
                setTitle(map.title);
                setRenaming(true);
              }}
            >
              {t('重命名')}
            </button>
          </div>
          <div className="button-row">
            {active ? (
              <button
                className="button secondary"
                disabled={busy}
                onClick={() => void action('/stop')}
              >
                {t('停止生成')}
              </button>
            ) : (
              map.status !== 'completed' && (
                <button
                  className="button primary"
                  disabled={busy}
                  onClick={() => void action('/resume')}
                >
                  {t('继续生成')}
                </button>
              )
            )}
            {map.download_available && (
              <>
                <button className="button secondary" onClick={downloadSvg}>
                  <Download size={16} />
                  {t('下载 SVG')}
                </button>
                <a className="button secondary" href={`/api/mindmaps/${id}/download`}>
                  {t('下载大纲')}
                </a>
                <a className="button ghost" href={`/api/mindmaps/${id}/download?format=json`}>
                  {t('下载 JSON')}
                </a>
              </>
            )}
            <button
              className="button ghost danger-text"
              disabled={busy}
              onClick={() => setDeleting(true)}
            >
              {t('删除')}
            </button>
          </div>
          {map.job?.status === 'failed' && (
            <p className="error" role="alert">
              {errorText(map.job)}
            </p>
          )}
          <ArtifactInstructionDetails instruction={map.input.instruction} />
          <DeckSources
            id={id}
            kind="mindmap"
            onOpenSource={onOpenSource}
            onOpenKnowledge={onOpenKnowledge}
          />
          <DeckDiagnostics deckId={id} kind="mindmap" failed={map.job?.status === 'failed'} />
          {map.tree ? (
            <>
              <div className="button-row">
                <button
                  className={`button ${outline ? 'secondary' : 'primary'}`}
                  aria-pressed={!outline}
                  onClick={() => setOutline(false)}
                >
                  {t('导图')}
                </button>
                <button
                  className={`button ${outline ? 'primary' : 'secondary'}`}
                  aria-pressed={outline}
                  onClick={() => setOutline(true)}
                >
                  {t('文字大纲')}
                </button>
                <button className="button secondary" onClick={() => setFocus(true)}>
                  <Maximize size={16} />
                  {t('专注预览')}
                </button>
              </div>
              {outline ? (
                <div className="mindmap-outline">
                  {mapLayout(map.tree.nodes).nodes.map((n) => (
                    <div
                      key={n.node.id}
                      style={{ paddingInlineStart: `${Math.min(5, (n.x - 28) / 280) * 16}px` }}
                    >
                      <button
                        className="button ghost"
                        aria-pressed={node?.id === n.node.id}
                        onClick={() => onSelectNode(n.node.id)}
                      >
                        {n.node.label}
                      </button>
                      <p dir="auto">{n.node.detail}</p>
                      {n.node.evidence_ids.map(
                        (ref, i) =>
                          map.citations[ref] && (
                            <button
                              className="button ghost"
                              key={ref}
                              onClick={() => setCitation(map.citations[ref])}
                            >
                              {t('原文引用 {{v1}}', { v1: i + 1 })}
                            </button>
                          ),
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <div className="mindmap-workbench">
                  <Canvas nodes={map.tree.nodes} selected={node?.id} onSelect={onSelectNode} />
                  {detail}
                </div>
              )}
            </>
          ) : (
            <p className="empty-panel">{t('导图生成后会显示在这里；可以先离开，稍后回来查看。')}</p>
          )}
          {focus && map.tree && (
            <Modal onClose={() => setFocus(false)}>
              <section
                className="mindmap-focus"
                role="dialog"
                aria-modal="true"
                aria-label={t('思维导图专注预览')}
              >
                <div className="dialog-top">
                  <h2>{map.title}</h2>
                  <button
                    className="icon-button"
                    aria-label={t('关闭专注预览')}
                    onClick={() => setFocus(false)}
                  >
                    <X />
                  </button>
                </div>
                <div className="mindmap-workbench">
                  <Canvas nodes={map.tree.nodes} selected={node?.id} onSelect={onSelectNode} />
                  {detail}
                </div>
              </section>
            </Modal>
          )}
          {renaming && (
            <Modal onClose={() => setRenaming(false)} busy={busy}>
              <form
                className="small-dialog"
                role="dialog"
                aria-modal="true"
                aria-label={t('重命名思维导图')}
                onSubmit={async (e) => {
                  e.preventDefault();
                  if (
                    await action('', {
                      method: 'PATCH',
                      body: JSON.stringify({ title: title.trim() }),
                    })
                  )
                    setRenaming(false);
                }}
              >
                <h2>{t('重命名思维导图')}</h2>
                <label>
                  {t('思维导图名称')}
                  <input
                    value={title}
                    maxLength={1000}
                    disabled={busy}
                    onChange={(e) => setTitle(e.target.value)}
                  />
                </label>
                {(error || loadError) && (
                  <p className="error" role="alert">
                    {t(error || loadError)}
                  </p>
                )}
                <div className="dialog-actions">
                  <button
                    type="button"
                    className="button secondary"
                    onClick={() => setRenaming(false)}
                    disabled={busy}
                  >
                    {t('取消')}
                  </button>
                  <button className="button primary" disabled={busy || !title.trim()}>
                    {t('保存名称')}
                  </button>
                </div>
              </form>
            </Modal>
          )}
          {deleting && (
            <ArtifactDeleteDialog
              kind="mindmap"
              id={id}
              title={map.title}
              onClose={() => setDeleting(false)}
              onDeleted={onDeleted}
            />
          )}
        </>
      )}
      {citation && (
        <CitationPreview
          id={citation}
          onClose={() => setCitation(undefined)}
          onOpen={onOpenSource}
        />
      )}
    </section>
  );
}
