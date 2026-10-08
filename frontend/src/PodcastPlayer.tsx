import { createContext, useContext, useRef, useState, type ReactNode } from 'react';
import { X } from 'lucide-react';
import type { PodcastSummary } from './api';
import { t, useI18n } from './i18n';

type Player = {
  episodeId?: string;
  notebookId?: string;
  play: (episode: PodcastSummary, start?: number) => void;
  stop: (id?: string) => void;
};
const Context = createContext<Player>({ play: () => {}, stop: () => {} });
export const usePodcastPlayer = () => useContext(Context);

export function PodcastPlayerProvider({ children }: { children: ReactNode }) {
  useI18n();
  const [episode, setEpisode] = useState<PodcastSummary>();
  const [error, setError] = useState(false);
  const [rate, setRate] = useState(1);
  const audio = useRef<HTMLAudioElement>(null);
  const stop = (id?: string) => {
    if (id && id !== episode?.id) return;
    audio.current?.pause();
    audio.current?.removeAttribute('src');
    audio.current?.load();
    setEpisode(undefined);
    setError(false);
  };
  const play = (next: PodcastSummary, start?: number) => {
    if (!next.audio || !audio.current) return;
    const element = audio.current;
    const url = `/api/podcasts/${next.id}/audio?version=${next.audio.signature}`;
    if (element.getAttribute('src') !== url) {
      element.src = url;
      element.load();
    }
    if (start !== undefined) element.currentTime = start;
    element.playbackRate = rate;
    setEpisode(next);
    setError(false);
    void element.play().catch(() => setError(true));
  };
  return (
    <Context.Provider
      value={{
        episodeId: episode?.id,
        notebookId: episode && 'notebook_id' in episode ? String(episode.notebook_id) : undefined,
        play,
        stop,
      }}
    >
      {children}
      <section
        className={`podcast-player${episode ? ' visible' : ''}`}
        aria-label={t('音频播放器')}
        hidden={!episode}
      >
        <strong>{episode?.title}</strong>
        <audio ref={audio} controls preload="metadata" onError={() => setError(true)} />
        <div className="podcast-player-actions">
          <button
            className="button ghost"
            onClick={() => {
              if (audio.current)
                audio.current.currentTime = Math.max(0, audio.current.currentTime - 15);
            }}
          >
            {t('后退 15 秒')}
          </button>
          <button
            className="button ghost"
            onClick={() => {
              if (audio.current)
                audio.current.currentTime = Math.min(
                  audio.current.duration || 0,
                  audio.current.currentTime + 15,
                );
            }}
          >
            {t('前进 15 秒')}
          </button>
          <label>
            {t('播放速度')}
            <select
              value={rate}
              onChange={(e) => {
                const value = Number(e.target.value);
                setRate(value);
                if (audio.current) audio.current.playbackRate = value;
              }}
            >
              {[0.75, 1, 1.25, 1.5, 2].map((value) => (
                <option key={value} value={value}>
                  {value}×
                </option>
              ))}
            </select>
          </label>
          <button className="icon-button" aria-label={t('关闭播放器')} onClick={() => stop()}>
            <X size={18} />
          </button>
        </div>
        {error && (
          <p className="error" role="alert">
            {t('音频无法播放，请重新打开节目或检查服务。')}
          </p>
        )}
      </section>
    </Context.Provider>
  );
}
