import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { test, expect, vi } from 'vitest';
import StudyView from './Study';
import { CreateStudy } from './CreatePodcast';
import { applyLanguage } from './i18n';
import { api, type StudyArtifact, type Source } from './api';
vi.mock('./api', () => ({ api: vi.fn() }));
const common = {
  id: 's',
  notebook_id: 'n',
  title: 'Practice',
  status: 'completed',
  input: {
    scope: { kind: 'selected' },
    language: 'en',
    instruction: 'Explain clearly.',
    count: 5,
    difficulty: 'mixed',
  },
  progress: { revision: 0, responses: {} },
  citations: { E1: 'cite' },
  job: null,
  download_available: true,
};
const quiz = {
  ...common,
  kind: 'quiz',
  content: {
    title: 'Practice',
    items: [
      {
        id: 'q',
        question: 'What supports learning?',
        options: [
          { id: 'A', text: 'Practice' },
          { id: 'B', text: 'Ignoring feedback' },
        ],
        evidence_ids: ['E1'],
      },
    ],
  },
} as StudyArtifact;
const props = {
  id: 's',
  kind: 'quiz' as const,
  onSelectItem: vi.fn(),
  onBack: vi.fn(),
  onChanged: vi.fn(),
  onDeleted: vi.fn(),
  onOpenSource: vi.fn(),
  onOpenKnowledge: vi.fn(),
};
test('quiz hides feedback until submit, sends the saved revision, and persists feedback on reload', async () => {
  await applyLanguage('en');
  let saved = structuredClone(quiz);
  vi.mocked(api).mockImplementation(async (path, init) => {
    if (path.endsWith('/responses')) {
      expect(JSON.parse(init!.body as string)).toEqual({ item_id: 'q', choice: 'B', revision: 0 });
      saved = {
        ...saved,
        progress: {
          revision: 1,
          responses: {
            q: {
              choice: 'B',
              correct: false,
              correct_option_id: 'A',
              explanation: 'Practice strengthens learning.',
            },
          },
        },
      };
    }
    return saved;
  });
  const view = render(<StudyView {...props} />);
  expect(await screen.findByText('What supports learning?')).toBeInTheDocument();
  expect(screen.queryByText('Practice strengthens learning.')).toBeNull();
  expect(screen.getByRole('button', { name: 'Submit answer' })).toBeDisabled();
  fireEvent.click(screen.getByRole('radio', { name: 'B. Ignoring feedback' }));
  fireEvent.click(screen.getByRole('button', { name: 'Submit answer' }));
  expect(await screen.findByText('Practice strengthens learning.')).toBeInTheDocument();
  expect(screen.getByRole('radio', { name: 'A. Practice' })).toBeDisabled();
  view.unmount();
  render(<StudyView {...props} />);
  expect(await screen.findByText('Practice strengthens learning.')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Start again' }));
  expect(screen.getByRole('alertdialog', { name: 'Reset study progress?' })).toBeInTheDocument();
  expect(vi.mocked(api).mock.calls.filter(([path]) => path.endsWith('/reset'))).toHaveLength(0);
});
test('flashcards require revealing an answer before self-rating; review shows only unmastered cards', async () => {
  await applyLanguage('en');
  let saved = {
    ...common,
    kind: 'flashcards',
    content: {
      title: 'Cards',
      items: [
        { id: 'f', front: 'What helps?', back: 'Practice and reflection.', evidence_ids: ['E1'] },
      ],
    },
  } as StudyArtifact;
  vi.mocked(api).mockImplementation(async (path, init) => {
    if (path.endsWith('/responses')) {
      expect(JSON.parse(init!.body as string)).toEqual({
        item_id: 'f',
        choice: 'known',
        revision: 0,
      });
      saved = { ...saved, progress: { revision: 1, responses: { f: { choice: 'known' } } } };
    }
    return saved;
  });
  render(<StudyView {...props} kind="flashcards" />);
  const flip = await screen.findByRole('button', { name: 'Show answer' });
  expect(screen.getByRole('button', { name: 'Mastered' })).toBeDisabled();
  expect(screen.queryByText('Practice and reflection.')).toBeNull();
  fireEvent.click(flip);
  expect(screen.getByText('Practice and reflection.')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Mastered' }));
  await waitFor(() => expect(screen.getByText('Reviewed 1 / 1 · Mastered 1')).toBeInTheDocument());
  fireEvent.click(screen.getByRole('button', { name: 'Review unmastered cards' }));
  expect(screen.getByText('All cards mastered!')).toBeInTheDocument();
});
test('study creation shares source scopes, instructions and batch keys without speech options', async () => {
  await applyLanguage('en');
  vi.mocked(api).mockImplementation(async (path) =>
    path.includes('instruction-history')
      ? { items: [{ instruction: 'Explain simply.' }] }
      : { quizzes: [quiz] },
  );
  const onCreated = vi.fn();
  render(
    <CreateStudy
      notebookId="n"
      kind="quiz"
      initialScope={{ kind: 'selected' }}
      initialLabel="Learning"
      initialLanguage="de"
      sources={[
        {
          id: 'src',
          title: 'Learning',
          enabled: true,
          parser_version: 'text',
          type: 'txt',
        } as Source,
      ]}
      pages={[]}
      onClose={vi.fn()}
      onCreated={onCreated}
    />,
  );
  expect(screen.getByLabelText('Quiz language')).toHaveValue('de');
  expect(screen.queryByText('Target duration')).toBeNull();
  await waitFor(() => expect(screen.getByLabelText('Previous instructions')).toBeEnabled());
  fireEvent.change(screen.getByLabelText('Previous instructions'), { target: { value: '0' } });
  fireEvent.change(screen.getByLabelText('Maximum items'), { target: { value: '20' } });
  fireEvent.change(screen.getByLabelText('Difficulty'), { target: { value: 'hard' } });
  fireEvent.click(
    screen.getByRole('radio', { name: 'Generate separately for each source / chapter' }),
  );
  fireEvent.click(screen.getByRole('button', { name: 'Start generating' }));
  await waitFor(() => expect(onCreated).toHaveBeenCalledWith(quiz, 1));
  const call = vi.mocked(api).mock.calls.find(([path]) => path.endsWith('/quizzes/batch'))!;
  expect(JSON.parse(call[1]!.body as string)).toMatchObject({
    count: 20,
    difficulty: 'hard',
    language: 'de',
    instruction: 'Explain simply.',
    scope: { kind: 'selected', source_ids: ['src'] },
  });
});
