import { useEffect, useRef, useState } from 'react'
import { ChevronLeft, ChevronRight, Loader2, Play, Sparkles } from 'lucide-react'
import { api } from '../api'
import { useStore } from '../store'
import { Button, fmt } from '../ui'

/** Podgląd: klatka spod głowicy odświeżana z opóźnieniem, obok gotowe wideo proxy. */
export function Preview() {
  const { pid, film, resolved, playhead, setPlayhead, jobs } = useStore()
  const [src, setSrc] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [video, setVideo] = useState<string | null>(null)
  const timer = useRef<number | null>(null)

  useEffect(() => {
    if (!pid) return
    if (timer.current) window.clearTimeout(timer.current)
    setLoading(true)
    timer.current = window.setTimeout(() => {
      setSrc(`${api.frameUrl(pid, playhead)}&_=${Date.now()}`)
    }, 180)
    return () => {
      if (timer.current) window.clearTimeout(timer.current)
    }
  }, [pid, playhead, film])

  useEffect(() => {
    const done = jobs.find((j) => j.kind === 'render' && j.status === 'done' && j.result?.video)
    if (done) setVideo(done.result.video as string)
  }, [jobs])

  const rendering = jobs.find((j) => j.kind === 'render' && (j.status === 'running' || j.status === 'queued'))
  const total = resolved?.total ?? 0
  const step = (delta: number) => setPlayhead(Math.min(Math.max(playhead + delta, 0), Math.max(total - 0.05, 0)))

  return (
    <div className="flex h-full flex-col gap-2">
      <div className="relative flex min-h-0 flex-1 items-center justify-center rounded border border-line bg-black">
        {video ? (
          <video src={video} controls className="max-h-full max-w-full" />
        ) : src ? (
          <img
            src={src}
            alt="podgląd klatki"
            onLoad={() => setLoading(false)}
            onError={() => setLoading(false)}
            className="max-h-full max-w-full object-contain"
          />
        ) : (
          <span className="text-muted">Brak podglądu</span>
        )}
        {loading && !video && (
          <Loader2 size={16} className="absolute right-2 top-2 animate-spin text-cyan" />
        )}
      </div>

      <div className="flex shrink-0 flex-wrap items-center gap-1.5">
        <Button onClick={() => step(-1 / 30)} title="Klatka wstecz"><ChevronLeft size={14} /></Button>
        <Button onClick={() => step(1 / 30)} title="Klatka naprzód"><ChevronRight size={14} /></Button>
        <span className="px-1 font-mono text-[12px] text-muted">{fmt(playhead)}</span>
        <input
          type="range"
          min={0}
          max={Math.max(total, 0.1)}
          step={0.01}
          value={Math.min(playhead, total)}
          onChange={(e) => setPlayhead(Number(e.target.value))}
          className="mx-1 min-w-[80px] flex-1"
        />
        {video && <Button tone="ghost" onClick={() => setVideo(null)}>Wróć do klatki</Button>}
        <Button
          tone="primary"
          disabled={!pid || !!rendering}
          onClick={() => pid && api.render(pid, 'proxy').catch((e) => useStore.getState().fail(String(e)))}
        >
          {rendering ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />} Podgląd
        </Button>
        <Button
          disabled={!pid || !!rendering}
          onClick={() => pid && api.render(pid, 'final').catch((e) => useStore.getState().fail(String(e)))}
        >
          <Sparkles size={14} /> Render
        </Button>
      </div>
    </div>
  )
}
