import { describe, expect, it } from 'vitest'
import { parseSseChunk } from './sse'

describe('parseSseChunk', () => {
  it('czyta pojedyncze zdarzenie', () => {
    const r = parseSseChunk('', 'data: {"type":"ping"}\n\n')
    expect(r.events).toEqual([{ type: 'ping' }])
    expect(r.rest).toBe('')
  })

  it('trzyma niedokończoną ramkę w reszcie i skleja ją z następnym kawałkiem', () => {
    const first = parseSseChunk('', 'data: {"type":"job","id":"a')
    expect(first.events).toHaveLength(0)
    const second = parseSseChunk<{ type: string; id: string }>(first.rest, 'bc"}\n\n')
    expect(second.events[0].id).toBe('abc')
  })

  it('czyta kilka zdarzeń z jednego kawałka', () => {
    const r = parseSseChunk('', 'data: {"n":1}\n\ndata: {"n":2}\n\n')
    expect(r.events).toEqual([{ n: 1 }, { n: 2 }])
  })

  it('zgłasza uszkodzoną ramkę zamiast wywracać parser', () => {
    const r = parseSseChunk('', 'data: {niepoprawny}\n\ndata: {"ok":true}\n\n')
    expect(r.errors).toHaveLength(1)
    expect(r.events).toEqual([{ ok: true }])
  })
})
