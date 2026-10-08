import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { useState } from 'react';
import { beforeEach, expect, test, vi } from 'vitest';
import ArtifactInstructions from './ArtifactInstructions';
import { api } from './api';
import { applyLanguage } from './i18n';

vi.mock('./api', async (original) => ({
  ...(await original<typeof import('./api')>()),
  api: vi.fn(),
}));
beforeEach(() => vi.mocked(api).mockReset());

function Form({ kind = 'deck' }: { kind?: 'deck' | 'podcast' }) {
  const [value, setValue] = useState('Unsaved draft');
  return <ArtifactInstructions kind={kind} value={value} onChange={setValue} disabled={false} />;
}

test('loading history preserves a draft; selection fills the entire multiline instruction and remains editable', async () => {
  const text = `Use clear examples.\n${'Keep diagrams and explain the context. '.repeat(8)}`;
  vi.mocked(api).mockResolvedValue({ items: [{ instruction: text }] });
  render(<Form />);
  const picker = screen.getByLabelText('历史说明');
  await waitFor(() => expect(picker).toBeEnabled());
  const input = screen.getByLabelText('Deck 补充说明');
  expect(input).toHaveValue('Unsaved draft');
  fireEvent.change(picker, { target: { value: '0' } });
  expect(input).toHaveValue(text);
  fireEvent.change(input, { target: { value: 'My edits' } });
  await act(() => applyLanguage('en'));
  expect(screen.getByLabelText('Deck instructions')).toHaveValue('My edits');
  fireEvent.change(screen.getByLabelText('Previous instructions'), { target: { value: '0' } });
  expect(input).toHaveValue(text);
  expect(api).toHaveBeenCalledOnce();
});

test('a failed history request never blocks manual input and can be retried', async () => {
  vi.mocked(api)
    .mockRejectedValueOnce(new Error('Unavailable'))
    .mockResolvedValueOnce({ items: [] });
  render(<Form kind="podcast" />);
  await screen.findByText('历史说明暂时无法加载');
  const input = screen.getByLabelText('Podcast 补充说明');
  expect(input).toBeEnabled();
  fireEvent.change(input, { target: { value: 'Keep my work' } });
  fireEvent.click(screen.getByRole('button', { name: '重试' }));
  await screen.findByText('暂无历史说明');
  expect(input).toHaveValue('Keep my work');
  expect(api).toHaveBeenCalledWith('/artifacts/instruction-history?kind=podcast');
});

test('generation disables history and text together', async () => {
  vi.mocked(api).mockResolvedValue({ items: [{ instruction: 'Saved request' }] });
  render(<ArtifactInstructions kind="deck" value="Draft" onChange={vi.fn()} disabled />);
  await screen.findByText('1. Saved request');
  expect(screen.getByLabelText('历史说明')).toBeDisabled();
  expect(screen.getByLabelText('Deck 补充说明')).toBeDisabled();
});
