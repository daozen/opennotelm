import { useEffect, useId, useState } from 'react';
import { api } from './api';
import { t, useI18n } from './i18n';

type History = { items: { instruction: string }[] };

export default function ArtifactInstructions({
  kind,
  value,
  onChange,
  disabled,
}: {
  kind: 'deck' | 'podcast' | 'mindmap';
  value: string;
  onChange: (value: string) => void;
  disabled: boolean;
}) {
  useI18n();
  const hintId = useId();
  const [items, setItems] = useState<History['items']>([]);
  const [status, setStatus] = useState<'loading' | 'ready' | 'failed'>('loading');
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let current = true;
    setStatus('loading');
    setItems([]);
    void api<History>(`/artifacts/instruction-history?kind=${kind}`).then(
      (history) => {
        if (!current) return;
        setItems(history.items);
        setStatus('ready');
      },
      () => {
        if (current) setStatus('failed');
      },
    );
    return () => {
      current = false;
    };
  }, [kind, attempt]);

  return (
    <div className="artifact-instructions">
      <label>
        {t('历史说明')}
        <select
          value=""
          disabled={disabled || status !== 'ready' || !items.length}
          aria-describedby={hintId}
          onChange={(event) => {
            if (!event.target.value) return;
            const item = items[Number(event.target.value)];
            if (item) onChange(item.instruction);
          }}
        >
          <option value="">
            {status === 'loading'
              ? t('加载中…')
              : status === 'failed'
                ? t('历史说明暂时无法加载')
                : items.length
                  ? t('选择历史说明…')
                  : t('暂无历史说明')}
          </option>
          {items.map((item, index) => (
            <option key={index} value={index} dir="auto" title={item.instruction}>
              {`${index + 1}. ${item.instruction.replace(/\s+/g, ' ').slice(0, 100)}${item.instruction.length > 100 ? '…' : ''}`}
            </option>
          ))}
        </select>
      </label>
      <p className="help" id={hintId}>
        {t('最近使用的说明。选择后会替换下方文字，仍可修改。')}
        {status === 'failed' && (
          <button
            type="button"
            className="link-button"
            disabled={disabled}
            onClick={() => setAttempt((previous) => previous + 1)}
          >
            {t('重试')}
          </button>
        )}
      </p>
      <label>
        {t('补充说明（可选）')}
        <textarea
          aria-label={
            kind === 'deck'
              ? t('Deck 补充说明')
              : kind === 'mindmap'
                ? t('思维导图补充说明')
                : t('Podcast 补充说明')
          }
          disabled={disabled}
          value={value}
          maxLength={4000}
          dir="auto"
          onChange={(event) => onChange(event.target.value)}
          placeholder={t('例如：重点解释长期积累，让初学者也容易理解。')}
          rows={3}
        />
      </label>
    </div>
  );
}
