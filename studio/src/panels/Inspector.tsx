import { Plus, Trash2 } from 'lucide-react'
import { sceneById, useStore } from '../store'
import { Button, Field, Num, Text } from '../ui'
import type { Layer, LayerType } from '../types'

const LAYER_TYPES: LayerType[] = ['title', 'subtitle', 'headline', 'stamp', 'counter',
                                  'board', 'panel', 'shape', 'word_list', 'grid']

const TEXTY: LayerType[] = ['title', 'subtitle', 'headline', 'stamp', 'counter', 'board']

export function Inspector() {
  const { film, selected, selectedLayer, select, edit, assets } = useStore()
  const scene = sceneById(film, selected)
  if (!film || !scene) return <p className="text-muted">Zaznacz scenę na osi czasu.</p>

  const patchScene = (patch: Partial<typeof scene>) =>
    edit((draft) => {
      const target = draft.scenes.find((s) => s.id === scene.id)
      if (target) Object.assign(target, patch)
    })

  const patchLayer = (index: number, patch: Partial<Layer>) =>
    edit((draft) => {
      const target = draft.scenes.find((s) => s.id === scene.id)
      if (target) Object.assign(target.layers[index], patch)
    })

  const clipKeys = Object.keys(film.assets.clips)

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-2">
        <Field label="Identyfikator"><Text value={scene.id} onChange={(v) => patchScene({ id: v })} /></Field>
        <Field label="Typ">
          <select value={scene.type} onChange={(e) => patchScene({ type: e.target.value as typeof scene.type })}>
            {['black', 'clip', 'freeze', 'still'].map((t) => <option key={t}>{t}</option>)}
          </select>
        </Field>
      </div>

      {scene.type !== 'black' && (
        <div className="grid grid-cols-2 gap-2">
          <Field label="Klip">
            <select value={scene.clip ?? ''} onChange={(e) => patchScene({ clip: e.target.value })}>
              <option value="">—</option>
              {clipKeys.map((k) => <option key={k}>{k}</option>)}
            </select>
          </Field>
          {scene.type === 'clip' ? (
            <Field label="Zakres (s)">
              <div className="flex gap-1">
                <Num value={scene.start} onChange={(v) => patchScene({ start: v })} />
                <Num value={scene.end} onChange={(v) => patchScene({ end: v })} />
              </div>
            </Field>
          ) : (
            <Field label="Klatka (s)"><Num value={scene.at} onChange={(v) => patchScene({ at: v })} /></Field>
          )}
        </div>
      )}

      <div className="grid grid-cols-3 gap-2">
        <Field label="Długość" hint="puste = z lektora"><Num value={scene.duration} onChange={(v) => patchScene({ duration: v })} /></Field>
        <Field label="Minimum"><Num value={scene.min_duration ?? 0} onChange={(v) => patchScene({ min_duration: v ?? 0 })} /></Field>
        <Field label="Ogon"><Num value={scene.tail ?? 0} onChange={(v) => patchScene({ tail: v ?? 0 })} /></Field>
      </div>

      {scene.type === 'clip' && (
        <div className="grid grid-cols-2 gap-2">
          <Field label="Napisy z transkrypcji">
            <label className="flex items-center gap-2 py-1 text-[13px]">
              <input type="checkbox" checked={scene.captions ?? true}
                     onChange={(e) => patchScene({ captions: e.target.checked })} />
              pokazuj cytat
            </label>
          </Field>
          <Field label="Wysokość napisów"><Num value={scene.caption_y ?? 1560} step={10} onChange={(v) => patchScene({ caption_y: v ?? 1560 })} /></Field>
        </div>
      )}
      {(scene.type === 'still' || scene.type === 'freeze') && (
        <label className="flex items-center gap-2 text-[13px]">
          <input type="checkbox" checked={scene.zoom ?? false} onChange={(e) => patchScene({ zoom: e.target.checked })} />
          powolny najazd
        </label>
      )}

      <div>
        <div className="mb-1 flex items-center justify-between">
          <h3 className="font-display text-[12px] tracking-widest text-muted uppercase">Lektor w scenie</h3>
          <select
            className="w-auto text-[12px]"
            value=""
            onChange={(e) => {
              if (!e.target.value) return
              const ref = e.target.value
              patchScene({ narration: [...scene.narration, { ref, at: 0.3, captions: true, y: 1500 }] })
            }}
          >
            <option value="">dodaj…</option>
            {film.narration.filter((n) => !scene.narration.some((p) => p.ref === n.id))
              .map((n) => <option key={n.id} value={n.id}>{n.id}</option>)}
          </select>
        </div>
        {scene.narration.length === 0 && <p className="text-[12px] text-muted">brak</p>}
        {scene.narration.map((placement, i) => (
          <div key={placement.ref} className="mb-1 grid grid-cols-[3rem_1fr_4.5rem_2rem] items-center gap-1 rounded border border-line bg-ink-2 p-1.5">
            <span className="truncate font-mono text-[12px] text-cyan">{placement.ref}</span>
            <input
              className="min-w-0"
              value={String(placement.at)}
              onChange={(e) =>
                edit((draft) => {
                  const target = draft.scenes.find((s) => s.id === scene.id)!
                  const raw = e.target.value
                  target.narration[i].at = raw === '' || Number.isNaN(Number(raw)) ? raw : Number(raw)
                })
              }
              title="Czas w scenie: liczba albo vo3.end+0.25"
            />
            <Num value={placement.y} step={10} onChange={(v) =>
              edit((draft) => {
                const target = draft.scenes.find((s) => s.id === scene.id)!
                target.narration[i].y = v ?? 1500
              })} />
            <Button tone="danger" onClick={() =>
              patchScene({ narration: scene.narration.filter((_, k) => k !== i) })}>
              <Trash2 size={12} />
            </Button>
          </div>
        ))}
      </div>

      <div>
        <div className="mb-1 flex items-center justify-between">
          <h3 className="font-display text-[12px] tracking-widest text-muted uppercase">Warstwy</h3>
          <select
            className="w-auto text-[12px]"
            value=""
            onChange={(e) => {
              if (!e.target.value) return
              const type = e.target.value as LayerType
              patchScene({ layers: [...scene.layers, { type, text: type === 'headline' ? 'NAGŁÓWEK' : 'tekst', y: 900, size: type === 'headline' ? 150 : 64, start: 0, fade_in: 150, fade_out: 200 }] })
            }}
          >
            <option value="">dodaj…</option>
            {LAYER_TYPES.map((t) => <option key={t}>{t}</option>)}
          </select>
        </div>
        {scene.layers.map((layer, i) => {
          const open = selectedLayer === i
          return (
            <div key={i} className={`mb-1 rounded border ${open ? 'border-cyan' : 'border-line'} bg-ink-2`}>
              <button
                type="button"
                onClick={() => select(scene.id, open ? null : i)}
                className="flex w-full items-center justify-between px-2 py-1.5 text-left text-[13px]"
              >
                <span className="truncate">
                  <span className="font-mono text-cyan">{layer.type}</span>{' '}
                  <span className="text-muted">{(layer.text ?? layer.items?.join(' / ') ?? '').slice(0, 34)}</span>
                </span>
                <span className="text-[11px] text-muted">{String(layer.start ?? 0)}s</span>
              </button>
              {open && (
                <div className="space-y-2 border-t border-line p-2">
                  {TEXTY.includes(layer.type) && (
                    <Field label="Tekst" hint="[c:accent] [c:grey] [fs:60] [b:0] [/]">
                      <Text rows={2} value={layer.text} onChange={(v) => patchLayer(i, { text: v })} />
                    </Field>
                  )}
                  {layer.type === 'word_list' && (
                    <Field label="Słowa (jedno na linię)">
                      <Text rows={3} value={(layer.items ?? []).join('\n')}
                            onChange={(v) => patchLayer(i, { items: v.split('\n').filter(Boolean) })} />
                    </Field>
                  )}
                  <div className="grid grid-cols-4 gap-1.5">
                    <Field label="X"><Num value={layer.x} step={10} onChange={(v) => patchLayer(i, { x: v })} /></Field>
                    <Field label="Y"><Num value={layer.y} step={10} onChange={(v) => patchLayer(i, { y: v })} /></Field>
                    <Field label="Rozmiar"><Num value={layer.size} step={2} onChange={(v) => patchLayer(i, { size: v })} /></Field>
                    <Field label="Wyrów."><Num value={layer.align} step={1} onChange={(v) => patchLayer(i, { align: v })} /></Field>
                  </div>
                  <div className="grid grid-cols-4 gap-1.5">
                    <Field label="Start">
                      <input value={String(layer.start ?? 0)}
                             onChange={(e) => {
                               const raw = e.target.value
                               patchLayer(i, { start: raw === '' || Number.isNaN(Number(raw)) ? raw : Number(raw) })
                             }} />
                    </Field>
                    <Field label="Pojawia"><Num value={layer.fade_in ?? 0} step={10} onChange={(v) => patchLayer(i, { fade_in: v ?? 0 })} /></Field>
                    <Field label="Znika"><Num value={layer.fade_out ?? 0} step={10} onChange={(v) => patchLayer(i, { fade_out: v ?? 0 })} /></Field>
                    <Field label="Kolor"><Text value={layer.color} onChange={(v) => patchLayer(i, { color: v || null })} /></Field>
                  </div>
                  <div className="flex justify-between">
                    <label className="flex items-center gap-2 text-[12px]">
                      <input type="checkbox" checked={!!layer.pop} onChange={(e) => patchLayer(i, { pop: e.target.checked })} />
                      wejście ze skokiem
                    </label>
                    <Button tone="danger" onClick={() => {
                      patchScene({ layers: scene.layers.filter((_, k) => k !== i) })
                      select(scene.id, null)
                    }}>
                      <Trash2 size={12} /> usuń warstwę
                    </Button>
                  </div>
                </div>
              )}
            </div>
          )
        })}
      </div>

      <div className="flex gap-2 border-t border-line pt-3">
        <Button onClick={() =>
          edit((draft) => {
            const index = draft.scenes.findIndex((s) => s.id === scene.id)
            const copy = JSON.parse(JSON.stringify(scene))
            copy.id = `${scene.id}-kopia`
            draft.scenes.splice(index + 1, 0, copy)
          })}>
          <Plus size={13} /> Powiel scenę
        </Button>
        <Button tone="danger" onClick={() => {
          edit((draft) => { draft.scenes = draft.scenes.filter((s) => s.id !== scene.id) })
          select(null)
        }}>
          <Trash2 size={13} /> Usuń scenę
        </Button>
      </div>
      {assets && scene.clip && (
        <p className="text-[11px] text-muted">
          Klip {scene.clip}: {assets.clips.find((c) => c.key === scene.clip)?.duration ?? '?'} s
        </p>
      )}
    </div>
  )
}
