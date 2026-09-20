import { useEffect, useState } from 'react'
import { Check, Loader2, Sparkles, X } from 'lucide-react'
import { api } from '../api'
import { useStore } from '../store'
import { Button } from '../ui'

/** Pasek promptu: instrukcja → propozycja zmian → podgląd różnicy → zastosuj albo odrzuć. */
export function PromptBar({ enabled }: { enabled: boolean }) {
  const { pid, jobs, fail } = useStore()
  const [text, setText] = useState('')
  const [jobId, setJobId] = useState<string | null>(null)
  const [proposal, setProposal] = useState<{ token: string; changes: string[]; notes: string } | null>(null)

  const job = jobs.find((j) => j.id === jobId)
  const busy = job?.status === 'running' || job?.status === 'queued'

  useEffect(() => {
    if (job?.status === 'done' && job.result?.proposal) {
      setProposal({ token: job.result.proposal, changes: job.result.changes ?? [], notes: job.result.notes ?? '' })
      setJobId(null)
    }
    if (job?.status === 'error') {
      fail(job.error ?? 'Model nie odpowiedział.')
      setJobId(null)
    }
  }, [job?.status])

  const send = async () => {
    if (!pid || !text.trim()) return
    try {
      const { job: id } = await api.prompt(pid, text.trim())
      setJobId(id)
    } catch (e) {
      fail(String(e))
    }
  }

  const apply = async () => {
    if (!pid || !proposal) return
    try {
      await api.applyProposal(pid, proposal.token)
      setProposal(null)
      setText('')
      await useStore.getState().open(pid)
    } catch (e) {
      fail(String(e))
    }
  }

  return (
    <div className="shrink-0 rounded-lg border border-line bg-ink-1 p-2">
      {proposal && (
        <div className="mb-2 rounded border border-cyan/50 bg-ink-2 p-2">
          <p className="mb-1 font-display text-[12px] tracking-widest text-cyan uppercase">Propozycja zmian</p>
          {proposal.notes && <p className="mb-1 text-[12px] text-muted">{proposal.notes}</p>}
          <ul className="mb-2 list-inside list-disc text-[13px]">
            {proposal.changes.map((c, i) => <li key={i}>{c}</li>)}
          </ul>
          <div className="flex gap-2">
            <Button tone="primary" onClick={apply}><Check size={13} /> Zastosuj</Button>
            <Button tone="ghost" onClick={() => setProposal(null)}><X size={13} /> Odrzuć</Button>
          </div>
        </div>
      )}
      <div className="flex gap-2">
        <input
          value={text}
          disabled={!enabled}
          placeholder={enabled
            ? 'np. skróć intro o sekundę i dodaj nagłówek PRZECIW przy planszy głosowania'
            : 'Brak OPENAI_API_KEY w .env — prompt wyłączony'}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter' && !busy) send() }}
        />
        <Button tone="primary" disabled={!enabled || busy || !text.trim()} onClick={send}>
          {busy ? <Loader2 size={14} className="animate-spin" /> : <Sparkles size={14} />}
          {busy ? 'Myślę…' : 'Wyślij'}
        </Button>
      </div>
    </div>
  )
}
