import Modal from './Modal';
import { t, useI18n } from './i18n';
import { useEffect, useState } from 'react';
import { ArrowUpRight, X } from 'lucide-react';
import { api, type Citation } from './api';

export function CitedText({
  text,
  citations,
  onCitation,
}: {
  text: string;
  citations: Record<string, string>;
  onCitation: (id: string) => void;
}) {
  useI18n();
  const labels = Object.keys(citations);
  const parts = text.split(/(\[\[[^\[\]\n]+\]\])/g);
  return (
    <>
      {parts.map((part, index) => {
        const match = /^\[\[([^\[\]\n]+)\]\]$/.exec(part);
        if (!match) return <span key={index}>{part}</span>;
        const id = citations[match[1]];
        return id ? (
          <button
            key={index}
            className="citation-marker"
            aria-label={t('查看引用 {{v1}}', { v1: labels.indexOf(match[1]) + 1 })}
            onClick={() => onCitation(id)}
          >
            {labels.indexOf(match[1]) + 1}
          </button>
        ) : null;
      })}
    </>
  );
}

export function CitationPreview({
  id,
  onClose,
  onOpen,
}: {
  id: string;
  onClose: () => void;
  onOpen: (sourceId: string, blockId: string) => Promise<void>;
}) {
  useI18n();
  const [citation, setCitation] = useState<Citation | null>(null);
  const [error, setError] = useState('');
  useEffect(() => {
    let active = true;
    api<Citation>(`/citations/${id}`)
      .then((value) => {
        if (active) setCitation(value);
      })
      .catch((e) => {
        if (active) setError(e.message);
      });
    return () => {
      active = false;
    };
  }, [id]);
  const passages =
    citation?.passages ??
    citation?.spans.map((span) => ({
      ...span,
      text: span.quote,
      anchor_block_id: span.block_id,
    })) ??
    [];
  return (
    <Modal onClose={onClose}>
      <section
        className="small-dialog citation-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="citation-title"
      >
        <div className="dialog-top">
          <h2 id="citation-title">{t('原文引用')}</h2>
          <button className="icon-button" aria-label={t('关闭引用')} onClick={onClose}>
            <X size={19} />
          </button>
        </div>
        {error && (
          <p className="error" role="alert">
            {t(error)}
          </p>
        )}
        {!citation && !error && <p role="status">{t('正在打开引用…')}</p>}
        {passages.map((span, index) => (
          <div className="citation-span" key={index}>
            {span.available ? (
              <>
                <h3>{span.source_title}</h3>
                <p className="citation-location">
                  {span.page ? t('第 {{v1}} 页', { v1: span.page }) : span.node_title}
                </p>
                <blockquote>{span.text}</blockquote>
                {span.image_url && (
                  <>
                    <p className="help">{t('图片识别内容（AI），请结合原图核对。')}</p>
                    <a href={span.image_url} target="_blank" rel="noreferrer">
                      <img src={span.image_url} alt={t('原始文档图片')} />
                    </a>
                  </>
                )}
                <button
                  className="button secondary"
                  onClick={async () => {
                    try {
                      await onOpen(span.source_id, span.anchor_block_id);
                      onClose();
                    } catch (e) {
                      setError((e as Error).message);
                    }
                  }}
                >
                  {t('打开原文')}
                  <ArrowUpRight size={15} />
                </button>
              </>
            ) : (
              <p>{t('原始资料已不可用（Original source unavailable）。')}</p>
            )}
          </div>
        ))}
      </section>
    </Modal>
  );
}
