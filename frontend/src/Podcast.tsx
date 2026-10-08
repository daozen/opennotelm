import { useEffect, useRef, useState } from 'react';
import { ArrowLeft, Play, Trash2 } from 'lucide-react';
import { api, type Podcast, type PodcastSegment, type PodcastTurn } from './api';
import { CitationPreview } from './Citations';
import DeckSources from './DeckSources';
import ArtifactInstructionDetails from './ArtifactInstructionDetails';
import Modal from './Modal';
import { errorText, t, useI18n } from './i18n';
import { useUnsavedChanges } from './NavigationGuard';
import { usePodcastPlayer } from './PodcastPlayer';

export const podcastStatus: Record<string, string> = {
  queued: '等待生成',
  podcast_reading: '正在阅读资料',
  podcast_planning: '正在规划节目',
  podcast_writing: '正在编写台词',
  podcast_speech: '正在合成语音',
  podcast_assembling: '正在合成音频',
  completed: '已完成',
  script_ready: '台词已就绪',
  edited: '台词已更新，音频待生成',
  paused: '已停止',
  failed: '生成失败',
};
const time = (value: number) =>
  `${Math.floor(value / 60)}:${Math.floor(value % 60)
    .toString()
    .padStart(2, '0')}`;

export default function PodcastView({
  id,
  onBack,
  backLabel,
  onChanged,
  onDeleted,
  onOpenSource,
  onOpenKnowledge,
}: {
  id: string;
  onBack: () => void;
  backLabel?: string;
  onChanged: () => void;
  onDeleted: () => void;
  onOpenSource: (sourceId: string, blockId: string) => Promise<void>;
  onOpenKnowledge: (id: string) => void;
}) {
  useI18n();
  const player = usePodcastPlayer();
  const [episode, setEpisode] = useState<Podcast>();
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [citation, setCitation] = useState<string>();
  const [editing, setEditing] = useState<{ segment: PodcastSegment; turns: PodcastTurn[] }>();
  const [renaming, setRenaming] = useState(false);
  const [title, setTitle] = useState('');
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState('');
  const requestVersion = useRef(0);
  const dirty =
    !!editing && JSON.stringify(editing.turns) !== JSON.stringify(editing.segment.script?.turns);
  useUnsavedChanges(dirty || (renaming && title !== episode?.title));
  useEffect(() => {
    let active = true;
    const load = () => {
      const version = ++requestVersion.current;
      return api<Podcast>(`/podcasts/${id}`)
        .then((value) => {
          if (active && version === requestVersion.current) setEpisode(value);
        })
        .catch((e) => {
          if (active && version === requestVersion.current) setError(e.message);
        });
    };
    void load();
    const timer = setInterval(() => void load(), 1500);
    return () => {
      active = false;
      requestVersion.current++;
      clearInterval(timer);
    };
  }, [id]);
  async function action(path: string, init: RequestInit = { method: 'POST' }) {
    ++requestVersion.current;
    setBusy(true);
    setError('');
    try {
      const value = await api<Podcast>(`/podcasts/${id}${path}`, init);
      ++requestVersion.current;
      setEpisode(value);
      onChanged();
      return true;
    } catch (e) {
      setError((e as Error).message);
      return false;
    } finally {
      setBusy(false);
    }
  }
  const active = !!episode?.job && ['queued', 'running'].includes(episode.job.status);
  const stopped = episode?.job?.status === 'cancelled';
  return (
    <section className="podcast-view" aria-label="Podcast">
      <button className="button ghost" onClick={onBack}>
        <ArrowLeft size={16} />
        {backLabel ?? t('返回对话')}
      </button>
      {error && (
        <p role="alert" className="error">
          {t(error)}
        </p>
      )}
      {!episode ? (
        <p>{t('加载中…')}</p>
      ) : (
        <>
          <div className="podcast-heading">
            <div>
              <span className="badge">Podcast</span>
              <h2>{episode.title}</h2>
              <p className="help">
                {t('目标约 {{minutes}} 分钟', { minutes: episode.input.target_minutes })} ·{' '}
                {t(podcastStatus[stopped ? 'paused' : episode.status] ?? '等待生成')}
                {episode.audio && ` · ${time(episode.audio.duration_seconds)}`}
              </p>
            </div>
            <button
              className="button secondary"
              disabled={busy || active}
              onClick={() => {
                setTitle(episode.title);
                setRenaming(true);
              }}
            >
              {t('重命名')}
            </button>
          </div>
          <div className="podcast-actions">
            {episode.audio && (
              <button className="button primary" onClick={() => player.play(episode)}>
                <Play size={16} />
                {t('播放音频')}
              </button>
            )}
            {episode.download_available && (
              <a className="button secondary" href={`/api/podcasts/${id}/audio?download=true`}>
                {t('下载音频')}
              </a>
            )}
            <a className="button secondary" href={`/api/podcasts/${id}/transcript`}>
              {t('下载台词')}
            </a>
            {active ? (
              <button
                className="button secondary"
                disabled={busy}
                onClick={() => void action('/stop')}
              >
                {t('停止生成')}
              </button>
            ) : (
              episode.status !== 'completed' && (
                <button
                  className="button primary"
                  disabled={busy || !!editing}
                  onClick={() => void action('/resume')}
                >
                  {t(['script_ready', 'edited'].includes(episode.status) ? '生成音频' : '继续生成')}
                </button>
              )
            )}
            <button
              className="button ghost danger-text"
              disabled={busy}
              onClick={() => {
                setDeleteError('');
                setDeleting(true);
              }}
            >
              <Trash2 size={15} />
              {t('删除')}
            </button>
          </div>
          {active && (
            <div className="podcast-progress">
              <progress aria-label={t('生成进度')} value={episode.job?.progress ?? 0} max={1} />
              <span>{t('已保存 {{count}} 段音频', { count: episode.saved_audio_chunks })}</span>
            </div>
          )}
          {episode.job?.status === 'failed' && (
            <div className="error" role="alert">
              <p>{errorText(episode.job)}</p>
              <a href={`/api/podcasts/${id}/diagnostics`}>{t('下载失败详情')}</a>
            </div>
          )}
          {episode.audio && episode.audio.revision !== episode.revision && (
            <p className="help">{t('当前播放的是上一次音频；生成新音频后将与已修改台词同步。')}</p>
          )}
          <ArtifactInstructionDetails instruction={episode.input.instruction} />
          <DeckSources
            kind="podcast"
            id={id}
            onOpenSource={onOpenSource}
            onOpenKnowledge={onOpenKnowledge}
          />
          <nav className="podcast-sections" aria-label={t('节目章节')}>
            {episode.audio?.timeline.map((item) => (
              <button
                className="button secondary"
                key={item.segment_id}
                onClick={() => player.play(episode, item.start)}
              >
                {time(item.start)} · {episode.segments.find((s) => s.id === item.segment_id)?.title}
              </button>
            ))}
          </nav>
          <h3>{t('节目台词')}</h3>
          {!episode.segments.length && (
            <p className="help">{t('节目规划完成后会显示逐段台词。')}</p>
          )}
          {episode.segments.map((segment) => (
            <article className="podcast-segment" key={segment.id}>
              <div className="podcast-heading">
                <h4>
                  {segment.ordinal + 1}. {segment.title}
                </h4>
                <button
                  className="button secondary"
                  disabled={busy || active || !segment.script || !!editing}
                  onClick={() =>
                    setEditing({ segment, turns: structuredClone(segment.script!.turns) })
                  }
                >
                  {t('编辑台词')}
                </button>
              </div>
              {!segment.script && <p className="help">{t('等待生成')}</p>}
              {editing?.segment.id === segment.id ? (
                <form
                  onSubmit={async (e) => {
                    e.preventDefault();
                    if (
                      await action(`/segments/${segment.id}`, {
                        method: 'PATCH',
                        body: JSON.stringify({
                          turns: editing.turns,
                          revision: editing.segment.revision,
                        }),
                      })
                    )
                      setEditing(undefined);
                  }}
                >
                  {editing.turns.map((turn, index) => (
                    <label key={index}>
                      {t('声音 {{speaker}}', { speaker: turn.speaker })}
                      <textarea
                        required
                        maxLength={3500}
                        rows={4}
                        value={turn.text}
                        onChange={(e) =>
                          setEditing({
                            ...editing,
                            turns: editing.turns.map((t, i) =>
                              i === index ? { ...t, text: e.target.value } : t,
                            ),
                          })
                        }
                      />
                    </label>
                  ))}
                  <div className="dialog-actions">
                    <button
                      type="button"
                      className="button secondary"
                      disabled={busy}
                      onClick={() => {
                        if (
                          !dirty ||
                          window.confirm(t('有未保存的修改。离开将丢弃这些修改，是否继续？'))
                        )
                          setEditing(undefined);
                      }}
                    >
                      {t('取消')}
                    </button>
                    <button className="button primary" disabled={busy || !dirty}>
                      {t('保存台词')}
                    </button>
                  </div>
                </form>
              ) : (
                segment.script?.turns.map((turn, index) => (
                  <div className="podcast-turn" key={index}>
                    <span className="badge">
                      {t('声音 {{speaker}}', { speaker: turn.speaker })}
                    </span>
                    <p>{turn.text}</p>
                    <div className="podcast-citations">
                      {turn.evidence_ids.map(
                        (ref) =>
                          segment.citations[ref] && (
                            <button
                              key={ref}
                              className="citation-marker"
                              aria-label={t('查看引用 {{v1}}', {
                                v1: Object.keys(segment.citations).indexOf(ref) + 1,
                              })}
                              onClick={() => setCitation(segment.citations[ref])}
                            >
                              {Object.keys(segment.citations).indexOf(ref) + 1}
                            </button>
                          ),
                      )}
                    </div>
                  </div>
                ))
              )}
            </article>
          ))}
          {renaming && (
            <Modal onClose={() => setRenaming(false)} busy={busy}>
              <form
                className="small-dialog"
                role="dialog"
                aria-modal="true"
                aria-labelledby="podcast-rename-title"
                onSubmit={async (e) => {
                  e.preventDefault();
                  if (await action('', { method: 'PATCH', body: JSON.stringify({ title }) }))
                    setRenaming(false);
                }}
              >
                <h3 id="podcast-rename-title">{t('重命名')}</h3>
                <label>
                  {t('Podcast 名称')}
                  <input
                    required
                    maxLength={300}
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                  />
                </label>
                {error && (
                  <p className="error" role="alert">
                    {t(error)}
                  </p>
                )}
                <div className="dialog-actions">
                  <button
                    type="button"
                    className="button secondary"
                    disabled={busy}
                    onClick={() => setRenaming(false)}
                  >
                    {t('取消')}
                  </button>
                  <button className="button primary" disabled={busy || !title.trim()}>
                    {t('保存')}
                  </button>
                </div>
              </form>
            </Modal>
          )}
          {deleting && (
            <Modal onClose={() => setDeleting(false)} busy={busy}>
              <section
                className="small-dialog"
                role="alertdialog"
                aria-modal="true"
                aria-label={t('删除 Podcast')}
              >
                <h3>{t('删除 Podcast')}</h3>
                <p>{episode.title}</p>
                <p>{t('将删除节目、台词和音频；原始资料会保留。')}</p>
                {deleteError && (
                  <p className="error" role="alert">
                    {t(deleteError)}
                  </p>
                )}
                <div className="dialog-actions">
                  <button
                    className="button secondary"
                    disabled={busy}
                    onClick={() => setDeleting(false)}
                  >
                    {t('取消')}
                  </button>
                  <button
                    className="button danger"
                    disabled={busy}
                    onClick={async () => {
                      ++requestVersion.current;
                      setBusy(true);
                      setDeleteError('');
                      try {
                        // DELETE returns no episode. Keep the view until navigation succeeds.
                        await api<void>(`/podcasts/${id}`, { method: 'DELETE' });
                        ++requestVersion.current;
                        player.stop(id);
                        onDeleted();
                      } catch (e) {
                        setDeleteError((e as Error).message);
                      } finally {
                        setBusy(false);
                      }
                    }}
                  >
                    {t('删除')}
                  </button>
                </div>
              </section>
            </Modal>
          )}
        </>
      )}
      {citation && (
        <CitationPreview
          id={citation}
          onClose={() => setCitation(undefined)}
          onOpen={onOpenSource}
        />
      )}
    </section>
  );
}
