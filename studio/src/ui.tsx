import type { ReactNode } from 'react'

export function Panel({ title, right, children, className = '' }:
  { title: string; right?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={`flex min-h-0 flex-col rounded-lg border border-line bg-ink-1 ${className}`}>
      <header className="flex shrink-0 items-center justify-between gap-2 border-b border-line px-3 py-2">
        <h2 className="font-display text-[13px] tracking-widest text-cyan uppercase">{title}</h2>
        {right}
      </header>
      <div className="min-h-0 flex-1 overflow-auto p-3">{children}</div>
    </section>
  )
}

export function Button({ children, onClick, tone = 'normal', disabled, title, className = '' }: {
  children: ReactNode
  onClick?: () => void
  tone?: 'normal' | 'primary' | 'ghost' | 'danger'
  disabled?: boolean
  title?: string
  className?: string
}) {
  const tones = {
    normal: 'bg-ink-3 hover:bg-ink-2 text-paper border-line',
    primary: 'bg-cyan text-ink-0 hover:brightness-110 border-cyan font-semibold',
    ghost: 'bg-transparent hover:bg-ink-2 text-muted border-transparent',
    danger: 'bg-transparent hover:bg-ink-2 text-danger border-line',
  }
  return (
    <button
      type="button"
      title={title}
      disabled={disabled}
      onClick={onClick}
      className={`inline-flex items-center gap-1.5 rounded border px-2.5 py-1 text-[13px] transition
        disabled:cursor-not-allowed disabled:opacity-40 ${tones[tone]} ${className}`}
    >
      {children}
    </button>
  )
}

export function Field({ label, children, hint }: { label: string; children: ReactNode; hint?: string }) {
  return (
    <label className="block">
      <span className="mb-0.5 block text-[11px] tracking-wide text-muted uppercase">{label}</span>
      {children}
      {hint && <span className="mt-0.5 block text-[11px] text-muted/70">{hint}</span>}
    </label>
  )
}

export function Num({ value, onChange, step = 0.05, placeholder }: {
  value: number | null | undefined
  onChange: (v: number | null) => void
  step?: number
  placeholder?: string
}) {
  return (
    <input
      type="number"
      step={step}
      placeholder={placeholder ?? 'auto'}
      value={value ?? ''}
      onChange={(e) => onChange(e.target.value === '' ? null : Number(e.target.value))}
    />
  )
}

export function Text({ value, onChange, rows }: {
  value: string | null | undefined
  onChange: (v: string) => void
  rows?: number
}) {
  if (rows) {
    return <textarea rows={rows} value={value ?? ''} onChange={(e) => onChange(e.target.value)} />
  }
  return <input value={value ?? ''} onChange={(e) => onChange(e.target.value)} />
}

export const fmt = (seconds: number) => {
  const s = Math.max(0, seconds)
  const m = Math.floor(s / 60)
  const rest = s - m * 60
  return `${m}:${rest.toFixed(2).padStart(5, '0')}`
}
