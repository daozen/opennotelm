import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { expect, test, vi } from 'vitest';
import Chat from './Chat';
import { applyLanguage, languages, t } from './i18n';
import { NavigationGuardProvider } from './NavigationGuard';

const props = {
  notebookId: 'book',
  selectedCount: 1,
  scope: { kind: 'selected' as const },
  onResetScope: vi.fn(),
  onOpenSource: vi.fn(),
  onSaveKnowledge: vi.fn(),
};
const fallback = 'The selected sources do not contain enough information to answer this question.';

test('localizes system fallback in all twelve languages while keeping user text and drafts', async () => {
  vi.spyOn(globalThis, 'fetch').mockResolvedValue(
    new Response(
      JSON.stringify({
        messages: [
          { id: 'u', role: 'user', content: fallback, citations: {} },
          {
            id: 'a',
            role: 'assistant',
            content: fallback,
            citations: {},
            metadata: { answer_status: 'insufficient_evidence' },
          },
        ],
      }),
    ),
  );
  render(
    <NavigationGuardProvider>
      <Chat {...props} />
    </NavigationGuardProvider>,
  );
  await screen.findByText('所选资料中没有足够的信息来回答这个问题。');
  fireEvent.change(screen.getByLabelText('向资料提问'), { target: { value: 'KEEP_DRAFT' } });
  for (const language of languages) {
    await act(() => applyLanguage(language.code));
    expect(
      screen.getByText(t('所选资料中没有足够的信息来回答这个问题。'), {
        selector: '.message-assistant p',
      }),
    ).toBeVisible();
    expect(screen.getByLabelText(t('向资料提问'))).toHaveValue('KEEP_DRAFT');
    // Never translate user text, even if it happens to equal the system fallback.
    expect(
      screen.getByText(fallback, { selector: '.message-user .message-content' }),
    ).toBeVisible();
  }
});

test('sends an explicit language override and defaults to the interface for new requests', async () => {
  const fetch = vi
    .spyOn(globalThis, 'fetch')
    .mockImplementation(async () => new Response(JSON.stringify({ messages: [] })));
  const view = render(
    <NavigationGuardProvider>
      <Chat {...props} language="fr" />
    </NavigationGuardProvider>,
  );
  await waitFor(() => expect(fetch).toHaveBeenCalled());
  fireEvent.change(screen.getByLabelText('向资料提问'), { target: { value: '原文问题' } });
  fireEvent.click(screen.getByRole('button', { name: '发送问题' }));
  await waitFor(() =>
    expect(fetch.mock.calls.some(([, init]) => init?.method === 'POST')).toBe(true),
  );
  expect(
    JSON.parse(String(fetch.mock.calls.find(([, init]) => init?.method === 'POST')![1]!.body))
      .language,
  ).toBe('fr');
  view.rerender(
    <NavigationGuardProvider>
      <Chat {...props} />
    </NavigationGuardProvider>,
  );
  await act(() => applyLanguage('ar'));
  fireEvent.change(screen.getByLabelText(t('向资料提问')), { target: { value: 'Question' } });
  await waitFor(() =>
    expect(screen.getByRole('button', { name: t('发送问题') })).not.toBeDisabled(),
  );
  fireEvent.click(screen.getByRole('button', { name: t('发送问题') }));
  await waitFor(() =>
    expect(fetch.mock.calls.filter(([, init]) => init?.method === 'POST')).toHaveLength(2),
  );
  expect(
    JSON.parse(
      String(fetch.mock.calls.filter(([, init]) => init?.method === 'POST').at(-1)![1]!.body),
    ).language,
  ).toBe('ar');
});
