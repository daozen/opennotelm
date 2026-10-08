import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { test, expect, vi } from 'vitest';
import { CreateMindMap } from './CreatePodcast';
import { applyLanguage } from './i18n';
import { api, type Source } from './api';
vi.mock('./api', () => ({ api: vi.fn() }));
const sources = [
  { id: 's', title: 'Learning', enabled: true, parser_version: 'text', type: 'txt' },
] as Source[];
test('mind maps use common scope, language, title, batch and history without speech settings', async () => {
  await applyLanguage('en');
  const mock = vi.mocked(api);
  mock.mockImplementation(async (path) =>
    path.includes('instruction-history')
      ? { items: [{ instruction: 'Explain simply.\nUse examples.' }] }
      : { mindmaps: [{ id: 'm' }] },
  );
  const created = vi.fn();
  render(
    <CreateMindMap
      notebookId="n"
      initialScope={{ kind: 'selected' }}
      initialLabel="Learning"
      initialLanguage="ja"
      sources={sources}
      pages={[]}
      onClose={vi.fn()}
      onCreated={created}
    />,
  );
  expect(screen.queryByText('Target duration')).toBeNull();
  expect(screen.queryByLabelText('Write the script first, generate audio later')).toBeNull();
  await waitFor(() => expect(screen.getByLabelText('Previous instructions')).toBeEnabled());
  fireEvent.change(screen.getByLabelText('Previous instructions'), { target: { value: '0' } });
  fireEvent.click(
    screen.getByRole('radio', { name: 'Generate separately for each source / chapter' }),
  );
  fireEvent.click(screen.getByRole('button', { name: 'Start generating' }));
  await waitFor(() => expect(created).toHaveBeenCalledWith({ id: 'm' }, 1));
  const call = mock.mock.calls.find(
    ([path, init]) => path.endsWith('/mindmaps/batch') && init?.method === 'POST',
  )!;
  const payload = JSON.parse(call[1]!.body as string);
  expect(payload).toMatchObject({
    language: 'ja',
    instruction: 'Explain simply.\nUse examples.',
    scope: { kind: 'selected', source_ids: ['s'] },
  });
  expect(payload).not.toHaveProperty('target_minutes');
  expect(payload).not.toHaveProperty('script_only');
});
