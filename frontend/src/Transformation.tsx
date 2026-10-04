import Modal from './Modal';
import { t, useI18n, errorText } from './i18n';
import { useEffect, useState } from 'react';
import { LoaderCircle, X } from 'lucide-react';
import { api, type KnowledgePage } from './api';
import { KnowledgeMarkdown } from './Knowledge';
import { CitationPreview } from './Citations';

export default function Transformation({
  id,
  onClose,
  onSaved,
  onOpenSource,
}: {
  id: string;
  onClose: () => void;
  onSaved: (page: KnowledgePage) => void;
  onOpenSource: (sourceId: string, blockId: string) => Promise<void>;
}) {
  useI18n();
  const [result, setResult] = useState<KnowledgePage & { kind: string }>();
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);
  const [citation, setCitation] = useState<string>();
  useEffect(() => {
    let active = true;
    const load = async () => {
      try {
        const value = await api<KnowledgePage & { kind: string }>(`/transformations/${id}`);
        if (active) setResult(value);
      } catch (e) {
        if (active) setError((e as Error).message);
      }
    };
    void load();
    const timer = setInterval(() => void load(), 1000);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [id]);
  async function close() {
    try {
      await api(`/transformations/${id}`, { method: 'DELETE' });
      onClose();
    } catch (e) {
      setError((e as Error).message);
    }
  }
  return (
    <Modal onClose={() => void close()} busy={saving}>
      <section
        className="small-dialog transformation-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="transformation-title"
      >
        <div className="dialog-top">
          <h2 id="transformation-title">
            {result?.kind === 'outline' ? t('资料提纲') : t('资料摘要')}
          </h2>
          <button
            className="icon-button"
            aria-label={t('关闭临时结果')}
            disabled={saving}
            onClick={() => void close()}
          >
            <X size={19} />
          </button>
        </div>
        <p className="help">{t('临时预览 · 仅在主动保存后加入知识库')}</p>
        {error && (
          <p className="error" role="alert">
            {t(error)}
          </p>
        )}
        {(!result || (result.job && ['queued', 'running'].includes(result.job.status))) && (
          <p className="chat-progress" role="status">
            <LoaderCircle className="spin" size={15} /> {t('正在理解完整范围…')}
          </p>
        )}
        {result?.job?.status === 'failed' && (
          <div className="error">
            <p>{errorText(result.job)}</p>
            <button
              className="button ghost"
              onClick={async () => {
                try {
                  await api(`/jobs/${result.job!.id}/retry`, { method: 'POST' });
                } catch (e) {
                  setError((e as Error).message);
                }
              }}
            >
              {t('重试摘要或提纲')}
            </button>
          </div>
        )}
        {result?.content_markdown && (
          <>
            <article className="knowledge-content transformation-content">
              <KnowledgeMarkdown page={result} onCitation={setCitation} />
            </article>
            <div className="dialog-actions">
              <button
                className="button primary"
                disabled={saving}
                onClick={async () => {
                  setSaving(true);
                  try {
                    const page = await api<KnowledgePage>(`/transformations/${id}/save`, {
                      method: 'POST',
                    });
                    await api(`/transformations/${id}`, { method: 'DELETE' });
                    onSaved(page);
                  } catch (e) {
                    setError((e as Error).message);
                  } finally {
                    setSaving(false);
                  }
                }}
              >
                {t('保存为知识页')}
              </button>
            </div>
          </>
        )}
        {citation && (
          <CitationPreview
            id={citation}
            onClose={() => setCitation(undefined)}
            onOpen={async (sourceId, blockId) => {
              await onOpenSource(sourceId, blockId);
              await close();
            }}
          />
        )}
      </section>
    </Modal>
  );
}
