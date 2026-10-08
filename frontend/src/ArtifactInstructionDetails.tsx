import { t, useI18n } from './i18n';

export default function ArtifactInstructionDetails({ instruction }: { instruction?: string }) {
  useI18n();
  return (
    <details className="artifact-instruction-details">
      <summary>{t('生成时的自定义说明')}</summary>
      {instruction?.trim() ? (
        <p className="artifact-instruction-text" dir="auto">
          {instruction}
        </p>
      ) : (
        <p className="help">{t('生成时未填写自定义说明。')}</p>
      )}
    </details>
  );
}
