import { useCallback, useEffect, useRef, useState } from 'react';
import { ArrowLeft, ArrowRight, Check, RotateCcw } from 'lucide-react';
import { api, type StudyArtifact, type StudyKind } from './api';
import { t, useI18n, errorText } from './i18n';
import { CitationPreview } from './Citations';
import Modal from './Modal';
import ArtifactInstructionDetails from './ArtifactInstructionDetails';
import DeckSources from './DeckSources';
import DeckDiagnostics from './DeckDiagnostics';
import ArtifactDeleteDialog, { artifactPath } from './ArtifactDeleteDialog';
import { kindLabel } from './ArtifactStudio';
import { useUnsavedChanges } from './NavigationGuard';

export const studyStatus: Record<string, string> = {
  queued: '等待生成',
  quiz_reading: '理解资料',
  flashcards_reading: '理解资料',
  quiz_writing: '编写测试题',
  flashcards_writing: '编写闪卡',
  quiz_exporting: '准备导出',
  flashcards_exporting: '准备导出',
  completed: '已完成',
  failed: '生成失败',
  paused: '已停止',
};
export default function StudyView({
  id,
  kind,
  selectedItemId,
  onSelectItem,
  onBack,
  onChanged,
  onDeleted,
  onOpenSource,
  onOpenKnowledge,
}: {
  id: string;
  kind: StudyKind;
  selectedItemId?: string;
  onSelectItem: (id: string) => void;
  onBack: () => void;
  onChanged: () => void;
  onDeleted: () => void;
  onOpenSource: (sourceId: string, blockId: string) => Promise<void>;
  onOpenKnowledge: (id: string) => void;
}) {
  useI18n();
  const [value, setValue] = useState<StudyArtifact>();
  const [error, setError] = useState('');
  const [loadError, setLoadError] = useState('');
  const [busy, setBusy] = useState(false);
  const busyRef = useRef(false),
    requestVersion = useRef(0);
  const [choices, setChoices] = useState<Record<string, string>>({});
  const [flipped, setFlipped] = useState(false);
  const [review, setReview] = useState(false),
    [deleting, setDeleting] = useState(false);
  const [renaming, setRenaming] = useState(false),
    [resetting, setResetting] = useState(false);
  const [title, setTitle] = useState(''),
    [citation, setCitation] = useState<string>();
  const endpoint = `/${artifactPath(kind)}/${id}`;
  const quiz = kind === 'quiz';
  const responses = value?.progress.responses ?? {};
  const allItems = value?.content?.items ?? [];
  const items = review
    ? allItems.filter((i) =>
        quiz ? responses[i.id]?.correct === false : responses[i.id]?.choice !== 'known',
      )
    : allItems;
  const item = items.find((i) => i.id === selectedItemId) ?? items[0];
  const index = items.findIndex((i) => i.id === item?.id);
  const response = item ? responses[item.id] : undefined;
  const choice = item ? (choices[item.id] ?? '') : '';
  const setChoice = (text: string) => {
    if (item) setChoices((old) => ({ ...old, [item.id]: text }));
  };
  const active = !!value?.job && ['queued', 'running'].includes(value.job.status);
  const done = allItems.filter((i) => responses[i.id]).length;
  const correct = allItems.filter((i) =>
    quiz ? responses[i.id]?.correct : responses[i.id]?.choice === 'known',
  ).length;
  useUnsavedChanges(
    Object.entries(choices).some(([id, text]) => text && !responses[id]) ||
      (renaming && title !== value?.title),
  );
  useEffect(() => {
    setFlipped(false);
  }, [item?.id]);
  const load = useCallback(async () => {
    if (busyRef.current) return;
    const version = ++requestVersion.current;
    try {
      const saved = await api<StudyArtifact>(endpoint);
      if (version === requestVersion.current) {
        setValue(saved);
        setLoadError('');
      }
    } catch (e) {
      if (version === requestVersion.current) setLoadError((e as Error).message);
    }
  }, [endpoint]);
  useEffect(() => {
    void load();
    const timer = setInterval(() => void load(), 2000);
    return () => {
      clearInterval(timer);
      requestVersion.current++;
    };
  }, [load]);
  const action = async (path: string, payload?: unknown, method = 'POST') => {
    if (busyRef.current) return false;
    busyRef.current = true;
    setBusy(true);
    setError('');
    requestVersion.current++;
    try {
      const result = await api<StudyArtifact>(endpoint + path, {
        method,
        ...(payload ? { body: JSON.stringify(payload) } : {}),
      });
      setValue(result);
      onChanged();
      return true;
    } catch (e) {
      setError((e as Error).message);
      // A stale tab must reload progress before another submit; keep its selected choice.
      try {
        setValue(await api<StudyArtifact>(endpoint));
      } catch {
        /* retain current view */
      }
      return false;
    } finally {
      busyRef.current = false;
      setBusy(false);
    }
  };
  const select = (id: string) => {
    setFlipped(false);
    onSelectItem(id);
  };
  const step = (delta: number) => {
    if (items[index + delta]) select(items[index + delta].id);
  };
  const references = item?.evidence_ids.map(
    (ref, i) =>
      value?.citations[ref] && (
        <button
          key={ref}
          className="button ghost"
          onClick={() => setCitation(value.citations[ref])}
        >
          {t('原文引用 {{v1}}', { v1: i + 1 })}
        </button>
      ),
  );
  return (
    <section className="study-view" aria-label={kindLabel(kind)}>
      <button className="button ghost" onClick={onBack}>
        <ArrowLeft size={16} />
        {t('返回创作空间')}
      </button>
      {(error || loadError) && (
        <p className="error" role="alert">
          {t(error || loadError)}{' '}
          <button className="button ghost" onClick={() => void load()}>
            {t('重试')}
          </button>
        </p>
      )}
      {!value ? (
        <p role="status">{t('加载中…')}</p>
      ) : (
        <>
          <div className="podcast-heading">
            <div>
              <span className="badge">{kindLabel(kind)}</span>
              <h2 dir="auto">{value.title}</h2>
              <p className="help">
                {t(
                  studyStatus[value.job?.status === 'cancelled' ? 'paused' : value.status] ??
                    '等待生成',
                )}
                {active && value.job && ` · ${Math.round(value.job.progress * 100)}%`}
              </p>
            </div>
            <button
              className="button secondary"
              disabled={active || busy}
              onClick={() => {
                setTitle(value.title);
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
              ['failed', 'cancelled'].includes(value.job?.status ?? '') && (
                <button
                  className="button primary"
                  disabled={busy}
                  onClick={() => void action('/resume')}
                >
                  {t(value.job?.status === 'failed' ? '重试' : '继续生成')}
                </button>
              )
            )}
            {value.download_available && (
              <>
                <a className="button secondary" href={`/api${endpoint}/download`}>
                  {t('下载学习资料')}
                </a>
                <a className="button ghost" href={`/api${endpoint}/download?format=json`}>
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
          {value.download_available && (
            <p className="help">{t('下载文件包含答案，便于离线学习。')}</p>
          )}
          {value.job?.status === 'failed' && (
            <p className="error" role="alert">
              {errorText(value.job)}
            </p>
          )}
          <ArtifactInstructionDetails instruction={value.input.instruction} />
          <DeckSources
            id={id}
            kind={kind}
            onOpenSource={onOpenSource}
            onOpenKnowledge={onOpenKnowledge}
          />
          <DeckDiagnostics deckId={id} kind={kind} failed={value.job?.status === 'failed'} />
          {value.content ? (
            <div className="study-workbench">
              <div className="study-progress" role="status">
                <strong>
                  {t(
                    quiz
                      ? '已答 {{done}} / {{total}} 题 · 答对 {{correct}} 题'
                      : '已复习 {{done}} / {{total}} 张 · 已掌握 {{correct}} 张',
                    { done, total: allItems.length, correct },
                  )}
                </strong>
                <progress max={allItems.length} value={done} aria-label={t('学习进度')} />
              </div>
              <div className="button-row">
                <button
                  className={`button ${review ? 'secondary' : 'primary'}`}
                  aria-pressed={!review}
                  onClick={() => {
                    setReview(false);
                    setFlipped(false);
                  }}
                >
                  {t(quiz ? '全部题目' : '全部闪卡')}
                </button>
                <button
                  className={`button ${review ? 'primary' : 'secondary'}`}
                  aria-pressed={review}
                  disabled={quiz && !allItems.some((i) => responses[i.id]?.correct === false)}
                  onClick={() => {
                    setReview(true);
                    setFlipped(false);
                  }}
                >
                  {t(quiz ? '查看错题' : '复习未掌握')}
                </button>
                <button
                  className="button ghost"
                  disabled={!done || busy}
                  onClick={() => setResetting(true)}
                >
                  <RotateCcw size={16} />
                  {t('重新开始')}
                </button>
              </div>
              {item ? (
                <>
                  <div className="study-pagination">
                    <button
                      className="button secondary"
                      disabled={busy || index <= 0}
                      onClick={() => step(-1)}
                    >
                      <ArrowLeft size={16} />
                      {t('上一项')}
                    </button>
                    <span>
                      {t('{{current}} / {{total}}', { current: index + 1, total: items.length })}
                    </span>
                    <button
                      className="button secondary"
                      disabled={busy || index === items.length - 1}
                      onClick={() => step(1)}
                    >
                      {t('下一项')}
                      <ArrowRight size={16} />
                    </button>
                  </div>
                  {quiz ? (
                    <form
                      className="quiz-question"
                      key={item.id}
                      onSubmit={async (e) => {
                        e.preventDefault();
                        if (
                          choice &&
                          (await action('/responses', {
                            item_id: item.id,
                            choice,
                            revision: value.progress.revision,
                          }))
                        )
                          setChoice('');
                      }}
                    >
                      <fieldset disabled={busy || !!response}>
                        <legend dir="auto">{item.question}</legend>
                        <div className="quiz-options">
                          {item.options?.map((option) => (
                            <label
                              key={option.id}
                              className={`quiz-option${response?.correct_option_id === option.id ? ' correct' : response?.choice === option.id ? ' incorrect' : ''}`}
                            >
                              <input
                                type="radio"
                                name={item.id}
                                value={option.id}
                                checked={(response?.choice ?? choice) === option.id}
                                onChange={() => setChoice(option.id)}
                              />
                              <span dir="auto">
                                <b>{option.id}.</b> {option.text}
                              </span>
                            </label>
                          ))}
                        </div>
                      </fieldset>
                      {!response ? (
                        <button className="button primary" disabled={!choice || busy}>
                          {t('提交答案')}
                        </button>
                      ) : (
                        <div className="quiz-feedback" role="status">
                          <strong>
                            {t(response.correct ? '回答正确' : '再想一想')}
                            {' · '}
                            {t('正确答案：{{answer}}', { answer: response.correct_option_id })}
                          </strong>
                          <p dir="auto">{response.explanation}</p>
                          {references}
                        </div>
                      )}
                    </form>
                  ) : (
                    <div className="flashcard-study">
                      <button
                        className={`flashcard${flipped ? ' flipped' : ''}`}
                        aria-label={t(flipped ? '查看问题' : '显示答案')}
                        onClick={() => setFlipped((v) => !v)}
                      >
                        <small>{t(flipped ? '答案' : '问题')}</small>
                        <span dir="auto">{flipped ? item.back : item.front}</span>
                        <small>{t('点击卡片或按空格翻面')}</small>
                      </button>
                      {response && (
                        <p className="help" role="status">
                          <Check size={14} />
                          {t(response.choice === 'known' ? '已掌握' : '需要复习')}
                        </p>
                      )}
                      {flipped && <div className="study-citations">{references}</div>}
                      <div className="button-row study-rating">
                        <button
                          className="button secondary"
                          disabled={!flipped || busy}
                          onClick={async () => {
                            if (
                              await action('/responses', {
                                item_id: item.id,
                                choice: 'review',
                                revision: value.progress.revision,
                              })
                            )
                              step(1);
                          }}
                        >
                          {t('还需复习')}
                        </button>
                        <button
                          className="button primary"
                          disabled={!flipped || busy}
                          onClick={async () => {
                            if (
                              await action('/responses', {
                                item_id: item.id,
                                choice: 'known',
                                revision: value.progress.revision,
                              })
                            )
                              step(1);
                          }}
                        >
                          {t('已掌握')}
                        </button>
                      </div>
                    </div>
                  )}
                  <nav className="study-item-list" aria-label={t(quiz ? '题目导航' : '闪卡导航')}>
                    {items.map((i, n) => (
                      <button
                        key={i.id}
                        className={`button ${i.id === item.id ? 'primary' : 'secondary'}`}
                        disabled={busy}
                        aria-label={t('第 {{number}} 项', { number: n + 1 })}
                        aria-current={item.id === i.id ? 'step' : undefined}
                        onClick={() => select(i.id)}
                      >
                        {n + 1}
                        {responses[i.id] && <Check size={12} />}
                      </button>
                    ))}
                  </nav>
                </>
              ) : (
                <p className="empty-panel">
                  {t(quiz ? '没有错题，继续保持！' : '全部闪卡已掌握！')}
                </p>
              )}
              {done === allItems.length && quiz && (
                <p className="study-complete" role="status">
                  {t('本次得分：{{correct}} / {{total}}', { correct, total: allItems.length })}
                </p>
              )}
            </div>
          ) : (
            <p className="empty-panel">{t('生成完成后可在这里学习；可以先离开，稍后回来查看。')}</p>
          )}
          {renaming && (
            <Modal busy={busy} onClose={() => setRenaming(false)}>
              <form
                className="small-dialog"
                role="dialog"
                aria-modal="true"
                aria-label={t('重命名产物')}
                onSubmit={async (e) => {
                  e.preventDefault();
                  if (await action('', { title: title.trim() }, 'PATCH')) setRenaming(false);
                }}
              >
                <h2>{t('重命名产物')}</h2>
                <label>
                  {t('名称')}
                  <input
                    value={title}
                    maxLength={1000}
                    disabled={busy}
                    onChange={(e) => setTitle(e.target.value)}
                  />
                </label>
                {error && (
                  <p className="error" role="alert">
                    {t(error)}
                  </p>
                )}
                <div className="dialog-actions">
                  <button
                    type="button"
                    className="button secondary"
                    disabled={busy}
                    onClick={() => setRenaming(false)}
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
          {resetting && (
            <Modal busy={busy} onClose={() => setResetting(false)}>
              <section
                className="small-dialog"
                role="alertdialog"
                aria-modal="true"
                aria-label={t('重置学习进度？')}
              >
                <h2>{t('重置学习进度？')}</h2>
                <p>{t('将清空本份产物的作答和掌握记录，题目与内容保持不变。')}</p>
                {error && (
                  <p className="error" role="alert">
                    {t(error)}
                  </p>
                )}
                <div className="dialog-actions">
                  <button
                    className="button secondary"
                    disabled={busy}
                    onClick={() => setResetting(false)}
                  >
                    {t('取消')}
                  </button>
                  <button
                    className="button primary"
                    disabled={busy}
                    onClick={async () => {
                      if (await action('/reset', { revision: value.progress.revision })) {
                        setChoices({});
                        setFlipped(false);
                        setReview(false);
                        setResetting(false);
                        if (allItems[0]) onSelectItem(allItems[0].id);
                      }
                    }}
                  >
                    {t('重新开始')}
                  </button>
                </div>
              </section>
            </Modal>
          )}
          {deleting && (
            <ArtifactDeleteDialog
              kind={kind}
              id={id}
              title={value.title}
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
