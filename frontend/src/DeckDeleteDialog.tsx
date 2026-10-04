import Modal from './Modal';
import { useState } from 'react';
import { api } from './api';
import { t, useI18n } from './i18n';

export default function DeckDeleteDialog({
  id,
  title,
  onClose,
  onDeleted,
}: {
  id: string;
  title: string;
  onClose: () => void;
  onDeleted: () => void;
}) {
  useI18n();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  return (
    <Modal onClose={onClose} busy={busy}>
      <div
        className="small-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="delete-deck-title"
      >
        <h2 id="delete-deck-title">{t('删除 Deck？')}</h2>
        <p className="delete-deck-name">{title}</p>
        <p>
          {t(
            '将停止相关任务，并删除这份 Deck 的页面、图片和 PDF。原始资料会保留，删除后无法恢复。',
          )}
        </p>
        {error && (
          <p className="error" role="alert">
            {t(error)}
          </p>
        )}
        <div className="dialog-actions">
          <button className="button secondary" disabled={busy} onClick={onClose}>
            {t('取消')}
          </button>
          <button
            className="button danger"
            disabled={busy}
            onClick={async () => {
              setBusy(true);
              setError('');
              try {
                await api(`/decks/${id}`, { method: 'DELETE' });
                onDeleted();
              } catch (e) {
                setError((e as Error).message);
                setBusy(false);
              }
            }}
          >
            {t(busy ? '正在删除…' : '确认删除 Deck')}
          </button>
        </div>
      </div>
    </Modal>
  );
}
