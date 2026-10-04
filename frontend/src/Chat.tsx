import { t, useI18n, errorText, type UiLanguage } from './i18n';
import { useCallback, useEffect, useRef, useState } from 'react';
import { ArrowUp, BookOpen, LoaderCircle, RotateCcw, Sparkles, X } from 'lucide-react';
import { api, type ChatMessage, type Scope } from './api';
import { CitedText, CitationPreview } from './Citations';
import { useUnsavedChanges } from './NavigationGuard';

const stages: Record<string, string> = {
  queued: '等待处理',
  retrieving: '查找相关原文',
  answering: '正在组织回答',
  verifying_citations: '核对原文引用',
  resuming: '恢复任务',
};

export default function Chat({
  notebookId,
  selectedCount,
  scope,
  scopeLabel,
  onResetScope,
  onOpenSource,
  onSaveKnowledge,
  language,
}: {
  notebookId: string;
  selectedCount: number;
  scope: Scope;
  scopeLabel?: string;
  onResetScope: () => void;
  onOpenSource: (sourceId: string, blockId: string) => Promise<void>;
  onSaveKnowledge: (messageId: string) => Promise<void>;
  language?: UiLanguage;
}) {
  const uiLanguage = useI18n();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [question, setQuestion] = useState('');
  useUnsavedChanges(!!question.trim());
  const [error, setError] = useState('');
  const [loadError, setLoadError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [citation, setCitation] = useState<string | null>(null);
  const history = useRef<HTMLDivElement>(null);
  const follow = useRef(true);
  const refresh = useCallback(async () => {
    const result = await api<{ messages: ChatMessage[] }>(`/notebooks/${notebookId}/chat`);
    setMessages(result.messages);
    setLoadError('');
  }, [notebookId]);
  useEffect(() => {
    void refresh().catch((e) => setLoadError(e.message));
    const timer = setInterval(() => {
      void refresh().catch((e) => setLoadError(e.message));
    }, 1000);
    return () => clearInterval(timer);
  }, [refresh]);
  useEffect(() => {
    const container = history.current;
    if (container && follow.current) container.scrollTop = container.scrollHeight;
  }, [messages.length, messages.at(-1)?.content]);
  const pending = messages.find(
    (message) => message.job && ['queued', 'running'].includes(message.job.status),
  );
  const busy = submitting || !!pending;
  const emptyScope = scope.kind === 'selected' && !selectedCount;
  async function send(event: React.FormEvent) {
    event.preventDefault();
    if (!question.trim() || busy || emptyScope) return;
    setSubmitting(true);
    setError('');
    try {
      await api(`/notebooks/${notebookId}/chat`, {
        method: 'POST',
        body: JSON.stringify({ question, scope, language: language ?? uiLanguage }),
      });
      setQuestion('');
      follow.current = true;
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSubmitting(false);
    }
  }
  return (
    <section className="chat-view" aria-label={t('资料对话')}>
      <div className="panel-title">
        <Sparkles size={18} />
        <h3>{t('对话')}</h3>
        <span className="scope-label">
          {scopeLabel ?? t('{{v1}} 份资料已选', { v1: selectedCount })}
        </span>
      </div>
      <div
        ref={history}
        className="chat-messages"
        aria-live="polite"
        onScroll={() => {
          const el = history.current;
          if (el) follow.current = el.scrollHeight - el.scrollTop - el.clientHeight < 96;
        }}
      >
        {!messages.length && (
          <div className="empty-panel">
            <BookOpen size={36} />
            <h3>{t('让理解发生')}</h3>
            <p>{t('选择资料，提出问题。每个回答都可以追溯到原文。')}</p>
          </div>
        )}
        {messages.map((message) => (
          <div className={`chat-message message-${message.role}`} key={message.id}>
            <span className="message-author">
              {message.role === 'user' ? t('你') : 'OpenNoteLM'}
            </span>
            <div className="message-content" dir="auto">
              {message.role === 'assistant' &&
              message.metadata?.answer_status === 'insufficient_evidence' ? (
                <p>{t('所选资料中没有足够的信息来回答这个问题。')}</p>
              ) : message.role === 'assistant' ? (
                <CitedText
                  text={message.content}
                  citations={message.citations}
                  onCitation={setCitation}
                />
              ) : (
                message.content
              )}
            </div>
            {message.role === 'assistant' && Object.keys(message.citations).length > 0 && (
              <button
                className="button ghost"
                disabled={submitting}
                onClick={async () => {
                  setSubmitting(true);
                  try {
                    await onSaveKnowledge(message.id);
                  } catch (e) {
                    setError((e as Error).message);
                  } finally {
                    setSubmitting(false);
                  }
                }}
              >
                {t('保存为知识页')}
              </button>
            )}
            {message.job?.status === 'failed' && (
              <div className="error">
                <p>{errorText(message.job)}</p>
                <small>{message.job.error_code}</small>
                <button
                  disabled={busy}
                  className="button ghost"
                  onClick={async () => {
                    setSubmitting(true);
                    try {
                      await api(`/jobs/${message.job!.id}/retry`, { method: 'POST' });
                      await refresh();
                    } catch (e) {
                      setError((e as Error).message);
                    } finally {
                      setSubmitting(false);
                    }
                  }}
                >
                  <RotateCcw size={13} /> {t('重试问题')}
                </button>
              </div>
            )}
          </div>
        ))}
        {pending && (
          <p className="chat-progress" role="status">
            <LoaderCircle size={15} className="spin" />
            {t(stages[pending.job!.stage] ?? '正在处理')}…
          </p>
        )}
      </div>
      {(error || loadError) && (
        <p className="error" role="alert">
          {t(error || loadError)}
        </p>
      )}
      {scope.kind !== 'selected' && (
        <div className="active-scope">
          {t('仅使用：')}
          {scopeLabel}
          <button className="icon-button" aria-label={t('恢复所选资料范围')} onClick={onResetScope}>
            <X size={13} />
          </button>
        </div>
      )}
      {emptyScope && (
        <p className="help" role="status">
          {t('先选择至少一份资料。')}
        </p>
      )}
      <form className="chat-composer" onSubmit={send}>
        <textarea
          aria-label={t('向资料提问')}
          placeholder={t('向你的资料提一个问题…')}
          value={question}
          maxLength={8000}
          rows={2}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
              e.preventDefault();
              e.currentTarget.form?.requestSubmit();
            }
          }}
        />
        <button
          className="button primary send-question"
          aria-label={t('发送问题')}
          disabled={busy || emptyScope || !question.trim()}
        >
          <ArrowUp size={18} />
        </button>
      </form>
      <p className="chat-footnote">
        {t('Enter 发送，Shift + Enter 换行')} · {t('回答仅依据所选资料。请通过引用核对重要信息。')}
      </p>
      {citation && (
        <CitationPreview id={citation} onClose={() => setCitation(null)} onOpen={onOpenSource} />
      )}
    </section>
  );
}
