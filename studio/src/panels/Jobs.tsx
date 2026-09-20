import { CircleSlash, Loader2 } from 'lucide-react'
import { api } from '../api'
import { useStore } from '../store'
import { Button } from '../ui'

const LABEL: Record<string, string> = {
  render: 'render', transcribe: 'transkrypcja', tts: 'lektor', prompt: 'prompt',
}
const COLOR: Record<string, string> = {
  queued: 'text-muted', running: 'text-gold', done: 'text-ok', error: 'text-danger', cancelled: 'text-muted',
}

export function Jobs() {
  const jobs = useStore((s) => s.jobs)
  if (!jobs.length) return <p className="text-[12px] text-muted">Brak zadań.</p>
  return (
    <div className="space-y-1.5">
      {jobs.slice(0, 12).map((job) => (
        <div key={job.id} className="rounded border border-line bg-ink-2 px-2 py-1.5">
          <div className="flex items-center gap-2 text-[12px]">
            {job.status === 'running' && <Loader2 size={12} className="animate-spin text-gold" />}
            <span className={COLOR[job.status]}>{job.status}</span>
            <span className="text-paper">{LABEL[job.kind] ?? job.kind}</span>
            <span className="min-w-0 flex-1 truncate text-muted">{job.message}</span>
            {(job.status === 'running' || job.status === 'queued') && (
              <Button tone="ghost" onClick={() => api.cancel(job.id)} title="Przerwij">
                <CircleSlash size={12} />
              </Button>
            )}
          </div>
          {job.status === 'running' && (
            <div className="mt-1 h-1 overflow-hidden rounded bg-ink-0">
              <div className="h-full bg-cyan transition-all" style={{ width: `${job.progress * 100}%` }} />
            </div>
          )}
          {job.error && <p className="mt-1 text-[11px] text-danger">{job.error}</p>}
        </div>
      ))}
    </div>
  )
}
