export interface ServerEvent {
  event: string
  id: string
  data: string
}

// A frame may span TCP chunks, including a split UTF-8 character or CRLF pair.
export async function* readEvents(stream: ReadableStream<Uint8Array>): AsyncGenerator<ServerEvent> {
  const reader = stream.getReader()
  const decoder = new TextDecoder()
  let pending = ''
  try {
    while (true) {
      const { value, done } = await reader.read()
      if (done) return
      pending += decoder.decode(value, { stream: true })
      let delimiter: RegExpExecArray | null
      while ((delimiter = /\r?\n\r?\n/.exec(pending))) {
        if (delimiter.index > 64 * 1024) throw new Error('SSE frame exceeds size limit')
        const frame = pending.slice(0, delimiter.index)
        pending = pending.slice(delimiter.index + delimiter[0].length)
        const event: ServerEvent = { event: 'message', id: '', data: '' }
        const data: string[] = []
        for (const line of frame.split(/\r?\n/)) {
          const separator = line.indexOf(':')
          const name = separator < 0 ? line : line.slice(0, separator)
          const value = separator < 0 ? '' : line.slice(separator + 1).replace(/^ /, '')
          if (name === 'event') event.event = value
          if (name === 'id') event.id = value
          if (name === 'data') data.push(value)
        }
        if (data.length) yield { ...event, data: data.join('\n') }
      }
      if (pending.length > 64 * 1024) throw new Error('SSE frame exceeds size limit')
    }
  } finally {
    await reader.cancel().catch(() => undefined)
    reader.releaseLock()
  }
}
