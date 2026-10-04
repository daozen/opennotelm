import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from 'react';
import { Languages } from 'lucide-react';
import { api } from './api';
import { languages, applyLanguage, isUiLanguage, t, useI18n, type UiLanguage } from './i18n';
import { detectBrowserLanguage } from './languages';

type Preferences = { ui_language: UiLanguage | null; telemetry_enabled: boolean };
const LanguageContext = createContext({ busy: false, error: '', change: (_: UiLanguage) => {} });

export function LanguagePreferencesProvider({ children }: { children: ReactNode }) {
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState('');
  const saving = useRef(false);
  useEffect(() => {
    let active = true;
    api<Preferences>('/settings/preferences')
      .then(async (preferences) => {
        if (active) {
          if (isUiLanguage(preferences.ui_language)) await applyLanguage(preferences.ui_language);
          else await applyLanguage(detectBrowserLanguage(), false);
        }
      })
      .catch(() => {
        if (active) setError('无法读取语言设置，可重新选择语言重试。');
      })
      .finally(() => {
        if (active) setBusy(false);
      });
    return () => {
      active = false;
    };
  }, []);
  async function change(language: UiLanguage) {
    if (saving.current || !isUiLanguage(language)) return;
    saving.current = true;
    setBusy(true);
    setError('');
    try {
      const preferences = await api<Preferences>('/settings/preferences', {
        method: 'PUT',
        body: JSON.stringify({ ui_language: language }),
      });
      if (isUiLanguage(preferences.ui_language)) await applyLanguage(preferences.ui_language);
    } catch {
      setError('语言保存失败，请重试。');
    } finally {
      saving.current = false;
      setBusy(false);
    }
  }
  return (
    <LanguageContext.Provider value={{ busy, error, change }}>{children}</LanguageContext.Provider>
  );
}

export default function LanguageSettings() {
  const language = useI18n();
  const { busy, error, change } = useContext(LanguageContext);
  return (
    <div className="language-settings">
      <label className="language-picker" title={t('界面语言')}>
        <Languages size={16} aria-hidden="true" />
        <select
          aria-label={t('界面语言')}
          value={language}
          disabled={busy}
          onChange={(event) => change(event.target.value as UiLanguage)}
        >
          {languages.map((item) => (
            <option key={item.code} value={item.code} lang={item.code}>
              {item.name}
            </option>
          ))}
        </select>
      </label>
      {error && (
        <span className="language-error" role="alert">
          {t(error)}
        </span>
      )}
    </div>
  );
}
