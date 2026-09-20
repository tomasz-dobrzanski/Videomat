import { useEffect, useState } from 'react'
import { FolderPlus, Redo2, Save, Undo2, X } from 'lucide-react'
import { api } from './api'
import { listen } from './lib/sse'
import { useStore } from './store'
import { Button, Panel } from './ui'
import { Assets } from './panels/Assets'
import { Inspector } from './panels/Inspector'
import { Jobs } from './panels/Jobs'
import { Preview } from './panels/Preview'
import { PromptBar } from './panels/PromptBar'
import { Timeline } from './panels/Timeline'

export default function App() {
  const store = useStore()
  const { pid, projects, film, dirty, saving, error } = store
  const [features, setFeatures] = useState<Record<string, boolean>>({})
  const [encoder, setEncoder] = useState('')

  useEffect(() => {
    store.loadProjects()
    api.status().then((s) => { setFeatures(s.features); setEncoder(s.encoder) }).catch(() => {})
    api.jobs().then(store.setJobs).catch(() => {})
    // ?nolive w adresie wyłącza strumień zdarzeń — przydatne przy zrzutach ekranu i diagnostyce.
    if (window.location.search.includes('nolive')) return
    return listen<{ type: string; job?: any; jobs?: any[] }>('/api/events', (event) => {
      if (event.type === 'job' && event.job) {
        useStore.getState().pushJob(event.job)
        if (event.job.status === 'done' && ['transcribe', 'tts'].includes(event.job.kind)) {
          useStore.getState().refreshAssets()
          useStore.getState().refreshTimeline()
        }
      }
      if (event.type === 'hello' && event.jobs) useStore.getState().setJobs(event.jobs)
    })
  }, [])

  // Zapis odświeża oś czasu, więc długości scen od razu uwzględniają nowy lektor.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const typing = ['INPUT', 'TEXTAREA', 'SELECT'].includes((e.target as HTMLElement)?.tagName)
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') { e.preventDefault(); store.save() }
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'z' && !e.shiftKey) { e.preventDefault(); store.undo() }
      if ((e.ctrlKey || e.metaKey) && (e.key.toLowerCase() === 'y' || (e.shiftKey && e.key.toLowerCase() === 'z'))) {
        e.preventDefault(); store.redo()
      }
      if (typing) return
      if (e.key === 'ArrowRight') store.setPlayhead(store.playhead + (e.shiftKey ? 1 : 1 / 30))
      if (e.key === 'ArrowLeft') store.setPlayhead(store.playhead - (e.shiftKey ? 1 : 1 / 30))
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [store.playhead, store.film])

  const newProject = async () => {
    const name = window.prompt('Nazwa nowego projektu')
    if (!name) return
    try {
      const row = await api.createProject(name)
      await store.loadProjects()
      await store.open(row.id)
    } catch (e) {
      store.fail(String(e))
    }
  }

  return (
    <div className="flex h-full flex-col gap-2 p-2">
      <header className="flex shrink-0 items-center gap-2">
        <h1 className="font-display text-lg tracking-[0.2em] text-paper uppercase">
          Video<span className="text-cyan">mat</span> Studio
        </h1>
        <select className="w-auto min-w-40" value={pid ?? ''} onChange={(e) => store.open(e.target.value)}>
          {projects.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
        </select>
        <Button tone="ghost" onClick={newProject} title="Nowy projekt"><FolderPlus size={14} /></Button>
        <span className="flex-1" />
        <Button tone="ghost" onClick={store.undo} title="Cofnij (Ctrl+Z)"><Undo2 size={14} /></Button>
        <Button tone="ghost" onClick={store.redo} title="Ponów (Ctrl+Y)"><Redo2 size={14} /></Button>
        <Button tone={dirty ? 'primary' : 'normal'} disabled={!dirty || saving} onClick={store.save}>
          <Save size={14} /> {saving ? 'Zapisuję…' : dirty ? 'Zapisz zmiany' : 'Zapisane'}
        </Button>
        <span className="font-mono text-[11px] text-muted">{encoder}</span>
      </header>

      {error && (
        <div className="flex shrink-0 items-center gap-2 rounded border border-danger/50 bg-danger/10 px-3 py-1.5 text-[13px] text-danger">
          <span className="flex-1">{error}</span>
          <button type="button" onClick={() => store.fail(null)}><X size={14} /></button>
        </div>
      )}

      <div className="grid min-h-0 flex-1 grid-cols-[minmax(260px,1fr)_minmax(320px,1.1fr)_minmax(280px,1fr)] gap-2">
        <div className="flex min-h-0 flex-col gap-2">
          <Panel title="Materiał" className="flex-1"><Assets /></Panel>
          <Panel title="Zadania" className="max-h-64 shrink-0"><Jobs /></Panel>
        </div>
        <Panel title="Podgląd"><Preview /></Panel>
        <Panel title="Scena"><Inspector /></Panel>
      </div>

      <div className="h-40 shrink-0">
        <Panel title={`Oś czasu${film ? ` — ${film.scenes.length} scen` : ''}`}>
          <Timeline />
        </Panel>
      </div>

      <PromptBar enabled={!!features.prompt} />
    </div>
  )
}
