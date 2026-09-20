export type SceneType = 'black' | 'clip' | 'freeze' | 'still'
export type LayerType =
  | 'title' | 'subtitle' | 'headline' | 'stamp' | 'counter'
  | 'panel' | 'shape' | 'board' | 'word_list' | 'grid'

export type Layer = {
  type: LayerType
  text?: string | null
  x?: number | null
  y?: number | null
  size?: number | null
  color?: string | null
  align?: number | null
  bold?: boolean | null
  spacing?: number | null
  border?: number | null
  pop?: boolean
  start?: number | string
  end?: number | string | null
  fade_in?: number
  fade_out?: number
  n?: number | null
  width?: number | null
  height?: number | null
  opacity?: number | null
  count?: number | null
  columns?: number | null
  step?: number | null
  gap?: number | null
  cell?: number | null
  items?: string[]
  line_height?: number | null
}

export type NarrationPlacement = {
  ref: string
  at: number | string
  captions: boolean
  y: number
}

export type Scene = {
  id: string
  type: SceneType
  duration?: number | null
  min_duration?: number
  tail?: number
  clip?: string | null
  start?: number | null
  end?: number | null
  at?: number | null
  zoom?: boolean
  captions?: boolean
  caption_y?: number
  layers: Layer[]
  narration: NarrationPlacement[]
  sfx: { ref: string; at: number | string; gain_db: number }[]
}

export type NarrationLine = { id: string; text: string; fallback: number; gain_db: number }

export type Film = {
  version: number
  name: string
  format: { width: number; height: number; fps: number }
  theme: Record<string, unknown>
  assets: {
    clips: Record<string, { path: string; crop: string | null; transcript: string | null; fixes: Record<string, string> }>
    music: Record<string, { path: string; gain_db: number }>
    sfx: Record<string, { path: string | null; prompt: string | null; duration: number | null; loop: boolean }>
    voice: Record<string, unknown>
  }
  narration: NarrationLine[]
  scenes: Scene[]
  music: { asset: string; gain_db: number | null; events: { at: number | string; action: string; gain_db: number | null }[] } | null
}

export type Resolved = {
  total: number
  scenes: { id: string; index: number; start: number; duration: number; end: number }[]
  narration: { id: string; scene: string; start: number; end: number; duration: number }[]
  sfx: { ref: string; scene: string; start: number }[]
  music: { start: number; end: number; gain_db: number }[]
}

export type Job = {
  id: string
  kind: string
  slot: string | null
  status: 'queued' | 'running' | 'done' | 'error' | 'cancelled'
  progress: number
  message: string
  result: any
  error: string | null
  log: string[]
}

export type Assets = {
  clips: {
    key: string
    path: string
    exists: boolean
    duration: number | null
    crop: string | null
    transcript: string | null
    fixes: Record<string, string>
    segments: { start: number; end: number; text: string; words: { w: string; start: number; end: number }[] }[]
  }[]
  music: { key: string; path: string; exists: boolean; duration: number | null; gain_db: number }[]
  narration: { id: string; text: string; audio: boolean; duration: number }[]
  sfx: { key: string; prompt: string | null; path: string | null }[]
}

export type ProjectRow = { id: string; name: string; scenes: number; narration: number; updated: number }
