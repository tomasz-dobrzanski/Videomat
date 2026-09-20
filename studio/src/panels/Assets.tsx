import { useRef, useState } from 'react'
import { AudioLines, FileText, Mic, Plus, Trash2, Upload } from 'lucide-react'
import { api } from '../api'
import { useStore } from '../store'
import { Button, Field, Text } from '../ui'

export function Assets() {
  const { pid, film, assets, edit, refreshAssets, select, setPlayhead, resolved, fail } = useStore()
  const picker = useRef<HTMLInputElement>(null)
  const [busy, setBusy] = useState(false)
  const [open, setOpen] = useState<string | null>(null)

  if (!film) return <p className="text-muted">Wybierz projekt.</p>

  const upload = async (files: FileList | null) => {
    if (!files?.length || !pid) return
    setBusy(true)
    try {
      for (const file of Array.from(files)) await api.upload(pid, file)
      await useStore.getState().open(pid)
    } catch (e) {
      fail(String(e))
    } finally {
      setBusy(false)
    }
  }

  /** Klik w słowo transkryptu ustawia punkt cięcia zaznaczonej sceny. */
  const useWordAsCut = (clipKey: string, time: number, edge: 'start' | 'end') => {
    const sceneId = useStore.getState().selected
    if (!sceneId) return fail('Najpierw zaznacz scenę na osi czasu.')
    edit((draft) => {
      const scene = draft.scenes.find((s) => s.id === sceneId)
      if (!scene) return
      scene.clip = clipKey
      if (scene.type === 'clip') scene[edge] = Number(time.toFixed(2))
      else scene.at = Number(time.toFixed(2))
    })
  }

  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        <Button onClick={() => picker.current?.click()} disabled={busy || !pid}>
          <Upload size={13} /> {busy ? 'Wgrywam…' : 'Wgraj materiał'}
        </Button>
        <input ref={picker} type="file" multiple hidden accept="video/*,audio/*,image/*"
               onChange={(e) => upload(e.target.files)} />
      </div>

      <section>
        <h3 className="mb-1 font-display text-[12px] tracking-widest text-muted uppercase">Nagrania</h3>
        {assets?.clips.length === 0 && <p className="text-[12px] text-muted">brak — wgraj plik wideo</p>}
        {assets?.clips.map((clip) => (
          <div key={clip.key} className="mb-1.5 rounded border border-line bg-ink-2">
            <button type="button" onClick={() => setOpen(open === clip.key ? null : clip.key)}
                    className="flex w-full items-center justify-between px-2 py-1.5 text-left text-[13px]">
              <span className="truncate">
                <span className="font-mono text-cyan">{clip.key}</span>{' '}
                <span className="text-muted">{clip.path.split('/').pop()}</span>
              </span>
              <span className="shrink-0 text-[11px] text-muted">
                {clip.duration ?? '?'}s · {clip.segments.length ? `${clip.segments.length} segm.` : 'bez transkrypcji'}
              </span>
            </button>
            {open === clip.key && (
              <div className="space-y-2 border-t border-line p-2">
                {!clip.segments.length && (
                  <Button onClick={() => pid && api.transcribe(pid, clip.key).catch((e) => fail(String(e)))}>
                    <FileText size={13} /> Transkrybuj
                  </Button>
                )}
                <Field label="Kadrowanie (filtr ffmpeg)" hint="np. crop=250:150:180:40 — usuwa logo stacji">
                  <Text value={clip.crop}
                        onChange={(v) => edit((draft) => { draft.assets.clips[clip.key].crop = v || null })} />
                </Field>
                {clip.segments.length > 0 && (
                  <div className="max-h-56 overflow-auto rounded border border-line bg-ink-1 p-1.5">
                    <p className="mb-1 text-[11px] text-muted">
                      Klik w słowo = początek ujęcia, klik z Shift = koniec.
                    </p>
                    {clip.segments.map((segment, si) => (
                      <p key={si} className="mb-1 leading-6">
                        {segment.words.map((word, wi) => (
                          <button
                            key={wi}
                            type="button"
                            onClick={(e) => useWordAsCut(clip.key, e.shiftKey ? word.end : word.start,
                                                         e.shiftKey ? 'end' : 'start')}
                            className="mr-1 rounded px-1 text-[13px] hover:bg-cyan-dim/40"
                            title={`${word.start.toFixed(2)}–${word.end.toFixed(2)} s`}
                          >
                            {word.w}
                          </button>
                        ))}
                      </p>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        ))}
      </section>

      <section>
        <div className="mb-1 flex items-center justify-between">
          <h3 className="font-display text-[12px] tracking-widest text-muted uppercase">Lektor</h3>
          <Button tone="ghost" onClick={() =>
            edit((draft) => {
              let n = draft.narration.length + 1
              while (draft.narration.some((x) => x.id === `vo${n}`)) n += 1
              draft.narration.push({ id: `vo${n}`, text: 'Nowa linia lektora.', fallback: 3, gain_db: 3.5 })
            })}>
            <Plus size={13} /> linia
          </Button>
        </div>
        {film.narration.map((line, i) => {
          const info = assets?.narration.find((n) => n.id === line.id)
          return (
            <div key={line.id} className="mb-1.5 rounded border border-line bg-ink-2 p-2">
              <div className="mb-1 flex items-center gap-2 text-[12px]">
                <span className="font-mono text-cyan">{line.id}</span>
                <span className={info?.audio ? 'text-ok' : 'text-muted'}>
                  {info?.audio ? `${info.duration}s` : `podgląd ${line.fallback}s`}
                </span>
                <span className="flex-1" />
                <Button tone="ghost" title="Wygeneruj tę linię"
                        onClick={() => pid && api.tts(pid, [line.id], true).catch((e) => fail(String(e)))}>
                  <Mic size={13} />
                </Button>
                <Button tone="danger" onClick={() =>
                  edit((draft) => {
                    draft.narration = draft.narration.filter((n) => n.id !== line.id)
                    draft.scenes.forEach((s) => { s.narration = s.narration.filter((p) => p.ref !== line.id) })
                  })}>
                  <Trash2 size={12} />
                </Button>
              </div>
              <Text rows={2} value={line.text}
                    onChange={(v) => edit((draft) => { draft.narration[i].text = v })} />
              {resolved && (
                <button type="button"
                        className="mt-1 text-[11px] text-muted hover:text-cyan"
                        onClick={() => {
                          const entry = resolved.narration.find((n) => n.id === line.id)
                          if (entry) { select(entry.scene); setPlayhead(entry.start + 0.2) }
                        }}>
                  pokaż na osi czasu
                </button>
              )}
            </div>
          )
        })}
        <Button onClick={() => pid && api.tts(pid).catch((e) => fail(String(e)))}>
          <AudioLines size={13} /> Dogeneruj brakujące
        </Button>
      </section>

      <section>
        <h3 className="mb-1 font-display text-[12px] tracking-widest text-muted uppercase">Muzyka</h3>
        {assets?.music.map((m) => (
          <div key={m.key} className="mb-1 flex items-center gap-2 rounded border border-line bg-ink-2 px-2 py-1.5 text-[12px]">
            <span className="font-mono text-cyan">{m.key}</span>
            <span className="min-w-0 flex-1 truncate text-muted">{m.path.split('/').pop()}</span>
            <span className="shrink-0 text-muted">{m.duration ?? '?'}s</span>
          </div>
        ))}
        {!assets?.music.length && <p className="text-[12px] text-muted">brak — wgraj plik audio</p>}
      </section>
    </div>
  )
}
