import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, expect, it, vi } from 'vitest';
import { NavigationProvider, parseRoute, routeUrl, useNavigation } from './Navigation';
import { NavigationGuardProvider, useUnsavedChanges } from './NavigationGuard';

beforeEach(() => window.history.replaceState(null, '', '/'));

it('round trips document locations, library selection and scoped chat without source content', () => {
  for (const path of [
    '/notebooks/book',
    '/notebooks/book?tab=knowledge&scopeSource=source&scopeNode=chapter',
    '/notebooks/book?scopeSource=source&scopeNodes=chapter1&scopeNodes=chapter2',
    '/notebooks/book/sources/source?node=page2&block=glyph',
    '/notebooks/book/knowledge/note?tab=sources',
    '/notebooks/book/decks/deck?slide=slide2',
  ]) {
    const route = parseRoute(new URL(path, window.location.origin));
    expect(routeUrl(route)).toBe(path);
  }
  expect(
    parseRoute(new URL('/notebooks/book?scopeSource=source&scopeNode=node', window.location.origin))
      .scope,
  ).toEqual({ kind: 'node', source_id: 'source', node_id: 'node' });
});

it('rejects unknown or malformed paths and ignores malformed navigation parameters', () => {
  for (const path of [
    '/unknown',
    '/notebooks',
    '/notebooks/%2F',
    '/notebooks/book/unknown/id',
    '/notebooks/book/constructor/id',
    '/notebooks/book/decks/id/more',
  ]) {
    expect(parseRoute(new URL(path, window.location.origin)).view).toBe('missing');
  }
  expect(
    parseRoute(
      new URL('/notebooks/book/sources/source?node=%2F&block=%3Cscript%3E', window.location.origin),
    ).nodeId,
  ).toBeUndefined();
});

function Views({ dirty = false }: { dirty?: boolean }) {
  useUnsavedChanges(dirty);
  const { route, go } = useNavigation();
  return (
    <>
      <output>
        {route.view}:{route.notebookId}:{route.itemId}
      </output>
      <button onClick={() => go({ view: 'knowledge', notebookId: 'book', itemId: 'note' })}>
        Note
      </button>
      <button onClick={() => go({ view: 'home' })}>Home</button>
      <button onClick={() => go({ ...route, library: 'sources' })}>Sources tab</button>
    </>
  );
}
const application = (dirty = false) => (
  <NavigationGuardProvider>
    <NavigationProvider>
      <Views dirty={dirty} />
    </NavigationProvider>
  </NavigationGuardProvider>
);

it('opens initial deep links, does not duplicate identical URLs, and follows popstate', () => {
  window.history.replaceState(null, '', '/notebooks/book');
  render(application());
  expect(screen.getByRole('status')).toHaveTextContent('chat:book:');
  fireEvent.click(screen.getByText('Note'));
  expect(window.location.pathname).toBe('/notebooks/book/knowledge/note');
  const push = vi.spyOn(window.history, 'pushState');
  fireEvent.click(screen.getByText('Note'));
  expect(push).not.toHaveBeenCalled();
  window.history.replaceState({ opennotelmNavigation: 0 }, '', '/notebooks/book');
  fireEvent.popState(window);
  expect(screen.getByRole('status')).toHaveTextContent('chat:book:');
});

it('keeps drafts and restores rejected browser history; library-only changes do not discard edits', () => {
  window.history.replaceState({ opennotelmNavigation: 1 }, '', '/notebooks/book/knowledge/note');
  const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false);
  const restore = vi.spyOn(window.history, 'go').mockImplementation(() => {});
  render(application(true));
  fireEvent.click(screen.getByText('Sources tab'));
  expect(confirm).not.toHaveBeenCalled();
  expect(window.location.search).toBe('?tab=sources');
  fireEvent.click(screen.getByText('Home'));
  expect(window.location.pathname).toBe('/notebooks/book/knowledge/note');
  window.history.replaceState({ opennotelmNavigation: 0 }, '', '/notebooks/book');
  fireEvent.popState(window);
  expect(restore).toHaveBeenCalledWith(2);
  expect(screen.getByRole('status')).toHaveTextContent('knowledge:book:note');
  window.history.replaceState(
    { opennotelmNavigation: 2 },
    '',
    '/notebooks/book/knowledge/note?tab=sources',
  );
  fireEvent.popState(window); // rollback event is ignored
  confirm.mockReturnValue(true);
  fireEvent.click(screen.getByText('Home'));
  expect(window.location.pathname).toBe('/');
});

it('artifact library filters and mind map nodes remain addressable', () => {
  const library = {
    view: 'artifacts' as const,
    notebookId: 'book',
    artifactKind: 'mindmap' as const,
  };
  expect(parseRoute(new URL(routeUrl(library), 'http://localhost'))).toMatchObject(library);
  const map = {
    view: 'mindmap' as const,
    notebookId: 'book',
    itemId: 'map',
    mapNodeId: 'N4',
    artifactKind: 'mindmap' as const,
  };
  expect(routeUrl(map)).toBe('/notebooks/book/mindmaps/map?type=mindmap&node=N4');
  expect(parseRoute(new URL(routeUrl(map), 'http://localhost'))).toMatchObject(map);
  expect(
    parseRoute(new URL('http://localhost/notebooks/book/artifacts?type=bad')),
  ).not.toHaveProperty('artifactKind', 'bad');
});
