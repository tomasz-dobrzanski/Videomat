import { create } from 'zustand'
import { api } from './api'
import type { Assets, Film, Job, ProjectRow, Resolved, Scene } from './types'

type State = {
  projects: ProjectRow[]
  pid: string | null
  film: Film | null
  resolved: Resolved | null
  assets: Assets | null
  jobs: Job[]
  selected: string | null
  selectedLayer: number | null
  playhead: number
  dirty: boolean
  saving: boolean
  error: string | null
  past: Film[]
  future: Film[]

  loadProjects: () => Promise<void>
  open: (pid: string) => Promise<void>
  refreshTimeline: () => Promise<void>
  refreshAssets: () => Promise<void>
  edit: (recipe: (film: Film) => void) => void
  undo: () => void
  redo: () => void
  save: () => Promise<void>
  setFilm: (film: Film) => void
  select: (sceneId: string | null, layer?: number | null) => void
  setPlayhead: (t: number) => void
  pushJob: (job: Job) => void
  setJobs: (jobs: Job[]) => void
  fail: (message: string | null) => void
}

const clone = (film: Film): Film => JSON.parse(JSON.stringify(film))

export const useStore = create<State>((set, get) => ({
  projects: [],
  pid: null,
  film: null,
  resolved: null,
  assets: null,
  jobs: [],
  selected: null,
  selectedLayer: null,
  playhead: 0,
  dirty: false,
  saving: false,
  error: null,
  past: [],
  future: [],

  loadProjects: async () => {
    try {
      const projects = await api.projects()
      set({ projects })
      if (!get().pid && projects.length) await get().open(projects[0].id)
    } catch (e) {
      set({ error: String(e) })
    }
  },

  open: async (pid) => {
    try {
      const film = await api.film(pid)
      set({ pid, film, past: [], future: [], dirty: false, selected: film.scenes[0]?.id ?? null,
            selectedLayer: null, playhead: 0 })
      await Promise.all([get().refreshTimeline(), get().refreshAssets()])
    } catch (e) {
      set({ error: String(e) })
    }
  },

  refreshTimeline: async () => {
    const pid = get().pid
    if (!pid) return
    try {
      set({ resolved: await api.timeline(pid) })
    } catch (e) {
      set({ error: String(e) })
    }
  },

  refreshAssets: async () => {
    const pid = get().pid
    if (!pid) return
    try {
      set({ assets: await api.assets(pid) })
    } catch (e) {
      set({ error: String(e) })
    }
  },

  edit: (recipe) => {
    const film = get().film
    if (!film) return
    const next = clone(film)
    recipe(next)
    set({ film: next, past: [...get().past, film].slice(-60), future: [], dirty: true })
  },

  undo: () => {
    const { past, film, future } = get()
    if (!past.length || !film) return
    set({ film: past[past.length - 1], past: past.slice(0, -1), future: [film, ...future], dirty: true })
  },

  redo: () => {
    const { past, film, future } = get()
    if (!future.length || !film) return
    set({ film: future[0], future: future.slice(1), past: [...past, film], dirty: true })
  },

  save: async () => {
    const { pid, film } = get()
    if (!pid || !film) return
    set({ saving: true })
    try {
      await api.saveFilm(pid, film)
      set({ dirty: false, error: null })
      await get().refreshTimeline()
    } catch (e) {
      set({ error: String(e) })
    } finally {
      set({ saving: false })
    }
  },

  setFilm: (film) => set({ film, dirty: true, past: [...get().past, get().film!].filter(Boolean).slice(-60) }),
  select: (sceneId, layer = null) => set({ selected: sceneId, selectedLayer: layer }),
  setPlayhead: (t) => set({ playhead: Math.max(0, t) }),
  pushJob: (job) =>
    set((state) => {
      const rest = state.jobs.filter((j) => j.id !== job.id)
      return { jobs: [job, ...rest].slice(0, 40) }
    }),
  setJobs: (jobs) => set({ jobs }),
  fail: (message) => set({ error: message }),
}))

export const sceneById = (film: Film | null, id: string | null): Scene | null =>
  film?.scenes.find((s) => s.id === id) ?? null
