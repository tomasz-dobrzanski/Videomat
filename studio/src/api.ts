import type { Assets, Film, Job, ProjectRow, Resolved } from './types'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init)
  if (!response.ok) {
    let detail = `HTTP ${response.status}`
    try {
      const body = await response.json()
      detail = body?.detail ?? detail
    } catch {
      /* odpowiedź nie jest JSON-em */
    }
    throw new Error(detail)
  }
  return (await response.json()) as T
}

const json = (body: unknown): RequestInit => ({
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
})

export const api = {
  status: () => request<{ encoder: string; keys: Record<string, boolean>; features: Record<string, boolean>; notes: Record<string, string> }>('/api/status'),
  projects: () => request<ProjectRow[]>('/api/projects'),
  createProject: (name: string) => request<ProjectRow>('/api/projects', json({ name })),

  film: (pid: string) => request<Film>(`/api/projects/${pid}/film`),
  saveFilm: (pid: string, film: Film) =>
    request<{ ok: boolean }>(`/api/projects/${pid}/film`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(film),
    }),
  timeline: (pid: string) => request<Resolved>(`/api/projects/${pid}/timeline`),
  assets: (pid: string) => request<Assets>(`/api/projects/${pid}/assets`),
  history: (pid: string) => request<{ file: string; updated: number }[]>(`/api/projects/${pid}/history`),
  restore: (pid: string, file: string) => request<Film>(`/api/projects/${pid}/restore`, json({ file })),

  upload: async (pid: string, file: File, transcribe = true) => {
    const form = new FormData()
    form.append('file', file)
    form.append('transcribe', String(transcribe))
    const response = await fetch(`/api/projects/${pid}/assets`, { method: 'POST', body: form })
    if (!response.ok) throw new Error((await response.json())?.detail ?? `HTTP ${response.status}`)
    return response.json()
  },
  transcribe: (pid: string, key: string) =>
    request<{ job: string }>(`/api/projects/${pid}/transcribe/${key}`, json({ language: 'pl' })),

  render: (pid: string, quality: 'proxy' | 'final', scene?: string) =>
    request<{ job: string }>(`/api/projects/${pid}/render`, json({ quality, scene: scene ?? null })),
  frameUrl: (pid: string, t: number, quality = 'final') =>
    `/api/projects/${pid}/frame?t=${t.toFixed(3)}&quality=${quality}`,

  tts: (pid: string, ids?: string[], regenerate = false) =>
    request<{ job: string }>(`/api/projects/${pid}/tts`, json({ ids: ids ?? null, regenerate })),

  prompt: (pid: string, instruction: string) =>
    request<{ job: string }>(`/api/projects/${pid}/prompt`, json({ instruction })),
  applyProposal: (pid: string, proposal: string) =>
    request<{ ok: boolean }>(`/api/projects/${pid}/apply`, json({ proposal })),

  jobs: () => request<Job[]>('/api/jobs'),
  job: (id: string) => request<Job>(`/api/jobs/${id}`),
  cancel: (id: string) => request<{ cancelled: boolean }>(`/api/jobs/${id}/cancel`, { method: 'POST' }),
}
