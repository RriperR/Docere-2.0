import axios from 'axios'
import api from './api'
import type { UploadJob } from '../stores/uploadStore'

import { readEvents } from './eventStream'
export { readEvents } from './eventStream'
export type { ServerEvent } from './eventStream'

const terminal = new Set<UploadJob['status']>(['needs_review', 'completed', 'completed_with_warnings', 'failed'])

function pause(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve) => {
    const finish = () => {
      clearTimeout(timer)
      signal.removeEventListener('abort', finish)
      resolve()
    }
    const timer = setTimeout(finish, ms)
    signal.addEventListener('abort', finish, { once: true })
    if (signal.aborted) finish()
  })
}

/** Authenticated status subscription. A current snapshot repairs gaps on reconnect. */
export async function watchImport(
  jobId: string,
  signal: AbortSignal,
  onSnapshot: (job: UploadJob) => void,
  onUnavailable: () => void,
): Promise<void> {
  let cursor = ''
  let retryMs = 1000
  let finished = false
  const snapshot = async () => {
    const { data } = await api.get<UploadJob>(`/archives/imports/${jobId}`, { signal, timeout: 15_000 })
    if (signal.aborted) return
    onSnapshot(data)
    finished = terminal.has(data.status)
  }

  while (!signal.aborted && !finished) {
    // Renew every 75s even if a proxy stops forwarding heartbeat/EOF.
    const connection = new AbortController()
    const abort = () => connection.abort()
    signal.addEventListener('abort', abort, { once: true })
    const timeout = setTimeout(abort, 75_000)
    try {
      await snapshot()
      if (finished || signal.aborted) return
      const { data } = await api.get<ReadableStream<Uint8Array>>(`/archives/imports/${jobId}/events`, {
        adapter: 'fetch', responseType: 'stream', signal: connection.signal,
        headers: { Accept: 'text/event-stream', ...(cursor ? { 'Last-Event-ID': cursor } : {}) },
      })
      // The shared Axios interceptor supplies Authorization and refreshes expired tokens.
      for await (const event of readEvents(data)) {
        if (signal.aborted) return
        if (event.event === 'access-revoked') {
          onUnavailable()
          return
        }
        if (event.event === 'auth-expired' || event.event === 'retry') break
        if (event.event === 'status') {
          await snapshot()
          cursor = event.id // Advance only after successful reconciliation.
          retryMs = 1000
          if (finished) return
        }
        if (event.event === 'done') {
          await snapshot()
          if (finished) return
        }
      }
    } catch (error) {
      if (signal.aborted) return
      if (axios.isAxiosError(error) && [401, 403, 404].includes(error.response?.status ?? 0)) {
        onUnavailable()
        return
      }
      // Reconnect with bounded backoff; the GET above also provides a polling fallback.
    } finally {
      clearTimeout(timeout)
      signal.removeEventListener('abort', abort)
      connection.abort()
    }
    await pause(retryMs, signal)
    retryMs = Math.min(retryMs * 2, 30_000)
  }
}
