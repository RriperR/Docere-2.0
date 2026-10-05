import axios from 'axios'
import api from './api'
import { readEvents } from './eventStream'

function pause(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise(resolve => {
    const finish = () => { clearTimeout(timer); signal.removeEventListener('abort', finish); resolve() }
    const timer = setTimeout(finish, ms)
    signal.addEventListener('abort', finish, { once: true })
    if (signal.aborted) finish()
  })
}

/** Bearer via shared Axios interceptors; only protected GETs supply clinical content. */
export async function watchChanges(path: string, signal: AbortSignal, refresh: () => Promise<void>,
  unavailable: () => Promise<void>): Promise<void> {
  let cursor = ''
  let retryMs = 1000
  while (!signal.aborted) {
    const connection = new AbortController()
    const abort = () => connection.abort()
    signal.addEventListener('abort', abort, { once: true })
    if (signal.aborted) connection.abort()
    const timeout = setTimeout(abort, 75_000)
    try {
      await refresh() // Repairs any gap on reconnect, including access changes without a case event.
      if (signal.aborted) return
      const result = await api.get<ReadableStream<Uint8Array>>(path, { adapter: 'fetch', responseType: 'stream',
        signal: connection.signal, headers: { Accept: 'text/event-stream', ...(cursor ? { 'Last-Event-ID': cursor } : {}) } })
      for await (const event of readEvents(result.data)) {
        if (signal.aborted) return
        if (event.event === 'access-revoked') { await unavailable(); return }
        if (['auth-expired', 'retry'].includes(event.event)) break
        if (event.event === 'changed') { await refresh(); cursor = event.id; retryMs = 1000 }
      }
    } catch (e) {
      if (signal.aborted) return
      if (axios.isAxiosError(e) && [401, 403, 404].includes(e.response?.status ?? 0)) { await unavailable(); return }
    } finally { clearTimeout(timeout); signal.removeEventListener('abort', abort); connection.abort() }
    await pause(retryMs, signal)
    retryMs = Math.min(retryMs * 2, 30_000)
  }
}
