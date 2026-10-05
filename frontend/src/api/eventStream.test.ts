import { expect, it } from 'vitest'
import { readEvents } from './eventStream'

function stream(...chunks: Uint8Array[]): ReadableStream<Uint8Array> {
  return new ReadableStream({ start(controller) { chunks.forEach(chunk => controller.enqueue(chunk)); controller.close() } })
}

it('parses split UTF-8 and CRLF delimiters without losing data', async () => {
  const bytes = new TextEncoder().encode('id: 3\r\nevent: changed\r\ndata: Привет\r\ndata: мир\r\n\r\n')
  const events = []
  for await (const event of readEvents(stream(...Array.from(bytes, byte => new Uint8Array([byte]))))) events.push(event)
  expect(events).toEqual([{ id: '3', event: 'changed', data: 'Привет\nмир' }])
})

it('limits individual frames rather than the TCP chunk containing many frames', async () => {
  const frame = `event: changed\ndata: ${'x'.repeat(20_000)}\n\n`
  let count = 0
  for await (const event of readEvents(stream(new TextEncoder().encode(frame.repeat(4))))) {
    expect(event.data).toHaveLength(20_000)
    count += 1
  }
  expect(count).toBe(4)
})

it.each(['', '\n\n'])('rejects an oversized frame even when its delimiter is %j', async delimiter => {
  const consume = async () => {
    for await (const event of readEvents(stream(new TextEncoder().encode(`data: ${'x'.repeat(65_537)}${delimiter}`)))) void event
  }
  await expect(consume()).rejects.toThrow('SSE frame exceeds size limit')
})
