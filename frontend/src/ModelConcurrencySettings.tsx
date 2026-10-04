import { useEffect, useRef, useState } from 'react';
import { api, type ModelConcurrencySettings as Settings } from './api';
import { t, useI18n } from './i18n';

type Props = {
  endpoint: string;
  sectionLabel: string;
  label: string;
  help: string;
  saveLabel: string;
  defaultValue: number;
};

export default function ModelConcurrencySettings({
  endpoint,
  sectionLabel,
  label,
  help,
  saveLabel,
  defaultValue,
}: Props) {
  useI18n();
  const [saved, setSaved] = useState<Settings>();
  const [draft, setDraft] = useState(defaultValue);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState('');
  const [message, setMessage] = useState(false);
  const loadVersion = useRef(0);

  async function load() {
    const version = ++loadVersion.current;
    setBusy(true);
    setError('');
    try {
      const value = await api<Settings>(endpoint);
      if (version !== loadVersion.current) return;
      setSaved(value);
      setDraft(value.concurrency);
    } catch (e) {
      if (version === loadVersion.current) setError((e as Error).message);
    } finally {
      if (version === loadVersion.current) setBusy(false);
    }
  }
  useEffect(() => {
    void load();
    return () => {
      loadVersion.current += 1;
    };
  }, [endpoint]);

  async function save() {
    setBusy(true);
    setError('');
    setMessage(false);
    try {
      const value = await api<Settings>(endpoint, {
        method: 'PUT',
        body: JSON.stringify({ concurrency: draft }),
      });
      setSaved(value);
      setDraft(value.concurrency);
      setMessage(true);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="image-concurrency-settings" aria-label={t(sectionLabel)}>
      <label>
        {t(label)}
        <select
          value={draft}
          disabled={busy || !saved}
          onChange={(e) => {
            setDraft(Number(e.target.value));
            setMessage(false);
          }}
        >
          {Array.from({ length: saved?.max_concurrency ?? 20 }, (_, index) => index + 1).map(
            (value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ),
          )}
        </select>
      </label>
      <p className="help">{t(help)}</p>
      {error && (
        <p className="error" role="alert">
          {t(error)}
        </p>
      )}
      {message && (
        <p className="help" role="status">
          {t('并发设置已保存。')}
        </p>
      )}
      {!saved && !busy ? (
        <button type="button" className="button secondary" onClick={() => void load()}>
          {t('重试')}
        </button>
      ) : (
        <button
          type="button"
          className="button secondary"
          disabled={busy || !saved || saved.concurrency === draft}
          onClick={() => void save()}
        >
          {t(saveLabel)}
        </button>
      )}
    </section>
  );
}
