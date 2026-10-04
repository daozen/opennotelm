import { useState } from 'react';
import Modal from './Modal';
import { api, type Deck } from './api';
import { t, useI18n } from './i18n';
import { useUnsavedChanges } from './NavigationGuard';

export default function DeckRenameDialog({
  id,
  title,
  onClose,
  onSaved,
}: {
  id: string;
  title: string;
  onClose: () => void;
  onSaved: (deck: Deck) => void;
}) {
  useI18n();
  const [name, setName] = useState(title);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  useUnsavedChanges(name !== title);
  return (
    <Modal onClose={onClose} busy={busy}>
      <form
        className="small-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="rename-deck-title"
        onSubmit={async (event) => {
          event.preventDefault();
          if (!name.trim()) return;
          setBusy(true);
          setError('');
          try {
            onSaved(
              await api<Deck>(`/decks/${id}`, {
                method: 'PATCH',
                body: JSON.stringify({ title: name.trim() }),
              }),
            );
          } catch (e) {
            setError((e as Error).message);
            setBusy(false);
          }
        }}
      >
        <h2 id="rename-deck-title">{t('重命名 Deck')}</h2>
        <label>
          {t('Deck 名称')}
          <input
            autoFocus
            value={name}
            maxLength={1000}
            disabled={busy}
            onChange={(event) => setName(event.target.value)}
          />
        </label>
        <p className="help">{t('名称会用于 PDF 文件名，已生成页面中的文字保持原样。')}</p>
        {error && (
          <p className="error" role="alert">
            {t(error)}
          </p>
        )}
        <div className="dialog-actions">
          <button type="button" className="button secondary" onClick={onClose} disabled={busy}>
            {t('取消')}
          </button>
          <button className="button primary" disabled={busy || !name.trim()}>
            {t('保存名称')}
          </button>
        </div>
      </form>
    </Modal>
  );
}
