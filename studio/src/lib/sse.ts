/**
 * Parser strumienia Server-Sent Events — czysta funkcja, bez Reacta, żeby dało się ją przetestować
 * na nagranych transkryptach. Zwraca rozpoznane zdarzenia i resztę bufora (niedokończoną linię).
 */
export type SseResult<T = unknown> = {
  events: T[]
  rest: string
  errors: string[]
}

export function parseSseChunk<T = unknown>(buffer: string, chunk: string): SseResult<T> {
  const text = buffer + chunk
  const blocks = text.split('\n\n')
  const rest = blocks.pop() ?? ''
  const events: T[] = []
  const errors: string[] = []

  for (const block of blocks) {
    const payload = block
      .split('\n')
      .filter((line) => line.startsWith('data:'))
      .map((line) => line.slice(5).trim())
      .join('\n')
    if (!payload) continue
    try {
      events.push(JSON.parse(payload) as T)
    } catch {
      errors.push(payload.slice(0, 200))
    }
  }
  return { events, rest, errors }
}

/** Nasłuch zdarzeń serwera z automatycznym wznawianiem połączenia. */
export function listen<T = unknown>(url: string, onEvent: (event: T) => void): () => void {
  let source: EventSource | null = null
  let stopped = false
  let retry = 500

  const connect = () => {
    if (stopped) return
    source = new EventSource(url)
    source.onmessage = (message) => {
      retry = 500
      try {
        onEvent(JSON.parse(message.data) as T)
      } catch {
        /* pomijamy uszkodzoną ramkę */
      }
    }
    source.onerror = () => {
      source?.close()
      if (stopped) return
      retry = Math.min(retry * 2, 8000)
      setTimeout(connect, retry)
    }
  }
  connect()
  return () => {
    stopped = true
    source?.close()
  }
}
