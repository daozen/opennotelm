import { useState } from 'react';
import Modal from './Modal';
import { api } from './api';
import { t, useI18n } from './i18n';
export type ArtifactKind = 'deck' | 'podcast' | 'mindmap';
export const artifactPath = (kind: ArtifactKind) =>
  ({ deck: 'decks', podcast: 'podcasts', mindmap: 'mindmaps' })[kind];
export default function ArtifactDeleteDialog({
  kind,
  id,
  title,
  onClose,
  onDeleted,
}: {
  kind: ArtifactKind;
  id: string;
  title: string;
  onClose: () => void;
  onDeleted: () => void;
}) {
  useI18n();
  const [busy, setBusy] = useState(false),
    [error, setError] = useState('');
  return (
    <Modal busy={busy} onClose={onClose}>
      <section
        className="small-dialog"
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="artifact-delete-title"
      >
        <h2 id="artifact-delete-title">{t('删除产物？')}</h2>
        <p>{title}</p>
        <p>{t('将停止相关任务并删除此产物及其导出文件。原始资料会保留，删除后无法恢复。')}</p>
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
                await api(`/${artifactPath(kind)}/${id}`, { method: 'DELETE' });
                onDeleted();
              } catch (e) {
                setError((e as Error).message);
                setBusy(false);
              }
            }}
          >
            {t(busy ? '正在删除…' : '确认删除')}
          </button>
        </div>
      </section>
    </Modal>
  );
}
