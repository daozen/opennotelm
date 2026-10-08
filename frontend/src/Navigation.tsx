import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import type { Scope } from './api';
import { useGuardedNavigation } from './NavigationGuard';

export type Route = {
  view:
    | 'home'
    | 'chat'
    | 'source'
    | 'knowledge'
    | 'deck'
    | 'podcast'
    | 'mindmap'
    | 'artifacts'
    | 'missing';
  artifactKind?: 'deck' | 'podcast' | 'mindmap';
  mapNodeId?: string;
  notebookId?: string;
  itemId?: string;
  library?: 'sources' | 'knowledge';
  nodeId?: string;
  blockId?: string;
  slideId?: string;
  scope?: Scope;
};
const validId = (value: string | null): value is string =>
  !!value && /^[A-Za-z0-9_-]+$/.test(value);

export function parseRoute(url: URL): Route {
  const pieces = url.pathname.split('/').filter(Boolean);
  if (!pieces.length) return { view: 'home' };
  if (pieces[0] !== 'notebooks' || !validId(pieces[1] ?? null)) return { view: 'missing' };
  const notebookId = pieces[1];
  const query = url.searchParams;
  const library =
    query.get('tab') === 'knowledge'
      ? 'knowledge'
      : query.get('tab') === 'sources'
        ? 'sources'
        : undefined;
  const source = query.get('scopeSource');
  const node = query.get('scopeNode');
  const nodes = query.getAll('scopeNodes').filter(validId);
  const scope: Scope = validId(source)
    ? nodes.length
      ? { kind: 'nodes', source_id: source, node_ids: [...new Set(nodes)] }
      : validId(node)
        ? { kind: 'node', source_id: source, node_id: node }
        : { kind: 'source', source_id: source }
    : { kind: 'selected' };
  const artifactKind = ['deck', 'podcast', 'mindmap'].includes(query.get('type') ?? '')
    ? (query.get('type') as Route['artifactKind'])
    : undefined;
  if (pieces.length === 3 && pieces[2] === 'artifacts')
    return { view: 'artifacts', notebookId, library: library ?? 'sources', scope, artifactKind };
  if (pieces.length === 2)
    return { view: 'chat', notebookId, library: library ?? 'sources', scope };
  const view =
    pieces[2] === 'sources'
      ? 'source'
      : pieces[2] === 'knowledge'
        ? 'knowledge'
        : pieces[2] === 'decks'
          ? 'deck'
          : pieces[2] === 'podcasts'
            ? 'podcast'
            : pieces[2] === 'mindmaps'
              ? 'mindmap'
              : undefined;
  if (pieces.length !== 4 || !view || !validId(pieces[3] ?? null))
    return { view: 'missing', notebookId };
  const id = (key: string) => (validId(query.get(key)) ? query.get(key)! : undefined);
  return {
    view,
    artifactKind,
    notebookId,
    itemId: pieces[3],
    scope,
    library: library ?? (view === 'knowledge' ? 'knowledge' : 'sources'),
    ...(view === 'source' ? { nodeId: id('node'), blockId: id('block') } : {}),
    ...(view === 'deck' ? { slideId: id('slide') } : {}),
    ...(view === 'mindmap' ? { mapNodeId: id('node') } : {}),
  };
}

export function routeUrl(route: Route): string {
  if (!route.notebookId || route.view === 'home') return '/';
  let path = `/notebooks/${encodeURIComponent(route.notebookId)}`;
  if (route.view === 'artifacts') path += '/artifacts';
  const segment = {
    mindmap: 'mindmaps',
    source: 'sources',
    knowledge: 'knowledge',
    deck: 'decks',
    podcast: 'podcasts',
  }[route.view as 'source' | 'knowledge' | 'deck' | 'podcast' | 'mindmap'];
  if (segment && route.itemId) path += `/${segment}/${encodeURIComponent(route.itemId)}`;
  const query = new URLSearchParams();
  if (route.artifactKind) query.set('type', route.artifactKind);
  if (route.view === 'mindmap' && route.mapNodeId) query.set('node', route.mapNodeId);
  if (route.library && route.library !== (route.view === 'knowledge' ? 'knowledge' : 'sources'))
    query.set('tab', route.library);
  if (route.view === 'source') {
    if (route.nodeId) query.set('node', route.nodeId);
    if (route.blockId) query.set('block', route.blockId);
  }
  if (route.view === 'deck' && route.slideId) query.set('slide', route.slideId);
  if (route.scope?.kind !== 'selected' && route.scope?.source_id) {
    query.set('scopeSource', route.scope.source_id);
    if (route.scope.kind === 'node' && route.scope.node_id)
      query.set('scopeNode', route.scope.node_id);
    if (route.scope.kind === 'nodes')
      for (const id of route.scope.node_ids ?? []) query.append('scopeNodes', id);
  }
  return path + (query.size ? `?${query}` : '');
}

type Navigation = {
  route: Route;
  go: (route: Route, options?: { replace?: boolean; guarded?: boolean }) => boolean;
};
const Context = createContext<Navigation | null>(null);
const stateKey = 'opennotelmNavigation';
const readIndex = () => {
  const value = window.history.state?.[stateKey];
  return Number.isInteger(value) ? (value as number) : 0;
};
const locationRoute = () => parseRoute(new URL(window.location.href));
const leavesView = (from: Route, to: Route) =>
  from.notebookId !== to.notebookId ||
  from.view !== to.view ||
  from.itemId !== to.itemId ||
  (from.view === 'deck' && from.slideId !== to.slideId);

export function NavigationProvider({ children }: { children: ReactNode }) {
  const guard = useGuardedNavigation();
  const [route, setRoute] = useState(locationRoute);
  const current = useRef(route);
  const position = useRef(readIndex());
  const restoring = useRef(false);
  useEffect(() => {
    window.history.replaceState(
      { ...window.history.state, [stateKey]: position.current },
      '',
      window.location.href,
    );
    const pop = () => {
      if (restoring.current) {
        restoring.current = false;
        return;
      }
      const nextIndex = readIndex();
      const next = locationRoute();
      const action = () => {
        position.current = nextIndex;
        current.current = next;
        setRoute(next);
      };
      let approved = true;
      if (leavesView(current.current, next)) approved = guard(action);
      else action();
      if (!approved) {
        // Keep the mounted editor and restore the same history entry/URL.
        const delta = position.current - nextIndex;
        if (delta) {
          restoring.current = true;
          window.history.go(delta);
        } else {
          window.history.replaceState(
            { ...window.history.state, [stateKey]: position.current },
            '',
            routeUrl(current.current),
          );
        }
      }
    };
    window.addEventListener('popstate', pop);
    return () => window.removeEventListener('popstate', pop);
  }, [guard]);
  const go = useCallback(
    (next: Route, options: { replace?: boolean; guarded?: boolean } = {}) => {
      if (restoring.current) return false;
      const url = routeUrl(next);
      if (url === window.location.pathname + window.location.search) return true;
      const action = () => {
        const index = position.current + (options.replace ? 0 : 1);
        window.history[options.replace ? 'replaceState' : 'pushState'](
          { ...window.history.state, [stateKey]: index },
          '',
          url,
        );
        position.current = index;
        current.current = locationRoute();
        setRoute(current.current);
      };
      if (options.guarded === false || !leavesView(current.current, next)) {
        action();
        return true;
      }
      return guard(action);
    },
    [guard],
  );
  return <Context.Provider value={{ route, go }}>{children}</Context.Provider>;
}

export function useNavigation(): Navigation {
  const navigation = useContext(Context);
  if (!navigation) throw new Error('NavigationProvider is required');
  return navigation;
}
