import { useRef } from 'react'
import { Film, Music, Image as ImageIcon, Square, Type } from 'lucide-react'
import { useStore } from '../store'
import { fmt } from '../ui'
import type { SceneType } from '../types'

const ICON: Record<SceneType, typeof Square> = {
  black: Type,
  clip: Film,
  freeze: ImageIcon,
  still: ImageIcon,
}

const TONE: Record<SceneType, string> = {
  black: 'bg-ink-3',
  clip: 'bg-cyan-dim/50',
  freeze: 'bg-gold/25',
  still: 'bg-gold/25',
}

export function Timeline() {
  const { film, resolved, selected, playhead, select, setPlayhead, edit } = useStore()
  const dragged = useRef<string | null>(null)
  const track = useRef<HTMLDivElement>(null)

  if (!film || !resolved) return <div className="p-3 text-muted">Wczytywanie osi czasu…</div>
  const total = resolved.total || 1

  const seek = (event: React.MouseEvent) => {
    const box = track.current?.getBoundingClientRect()
    if (!box) return
    setPlayhead(((event.clientX - box.left) / box.width) * total)
  }

  const reorder = (targetId: string) => {
    const from = dragged.current
    dragged.current = null
    if (!from || from === targetId) return
    edit((draft) => {
      const order = draft.scenes.map((s) => s.id)
      const a = order.indexOf(from)
      const b = order.indexOf(targetId)
      const [moved] = draft.scenes.splice(a, 1)
      draft.scenes.splice(b, 0, moved)
    })
  }

  return (
    <div className="flex h-full flex-col gap-1.5">
      <div
        ref={track}
        onClick={seek}
        className="relative h-6 shrink-0 cursor-col-resize rounded border border-line bg-ink-2"
        title="Kliknij, żeby przestawić głowicę"
      >
        {resolved.scenes.map((s) => (
          <div key={s.id} className="absolute top-0 h-full border-l border-line/60"
               style={{ left: `${(s.start / total) * 100}%` }} />
        ))}
        <div className="absolute top-0 z-10 h-full w-0.5 bg-gold"
             style={{ left: `${(playhead / total) * 100}%` }} />
        <span className="absolute right-2 top-0.5 text-[11px] text-muted">
          {fmt(playhead)} / {fmt(total)}
        </span>
      </div>

      <div className="flex min-h-0 flex-1 gap-1 overflow-x-auto pb-1">
        {resolved.scenes.map((entry) => {
          const scene = film.scenes.find((s) => s.id === entry.id)
          if (!scene) return null
          const Icon = ICON[scene.type]
          const active = selected === scene.id
          return (
            <div
              key={entry.id}
              draggable
              onDragStart={() => (dragged.current = entry.id)}
              onDragOver={(e) => e.preventDefault()}
              onDrop={() => reorder(entry.id)}
              onClick={() => {
                select(entry.id)
                setPlayhead(entry.start + 0.1)
              }}
              style={{ flexBasis: `${Math.max((entry.duration / total) * 100, 4)}%` }}
              className={`group relative flex min-w-[76px] shrink-0 grow-0 cursor-pointer flex-col justify-between
                overflow-hidden rounded border p-1.5 text-left transition
                ${TONE[scene.type]} ${active ? 'border-cyan ring-1 ring-cyan' : 'border-line hover:border-cyan-dim'}`}
              title={`${scene.id} — ${entry.duration.toFixed(2)} s`}
            >
              <div className="flex items-center gap-1 truncate text-[12px]">
                <Icon size={12} className="shrink-0" />
                <span className="truncate font-display tracking-wide">{scene.id}</span>
              </div>
              <div className="flex items-center gap-1 text-[10px] text-paper/70">
                {scene.narration.length > 0 && <Music size={10} />}
                <span>{entry.duration.toFixed(2)}s</span>
              </div>
              {playhead >= entry.start && playhead < entry.end && (
                <div className="absolute inset-x-0 bottom-0 h-0.5 bg-gold" />
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
