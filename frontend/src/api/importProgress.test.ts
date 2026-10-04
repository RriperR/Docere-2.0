import { afterEach, describe, expect, it, vi } from 'vitest'
import { AxiosError } from 'axios'
import api from './api'
import { readEvents, watchImport } from './importProgress'
import type { UploadJob } from '../stores/uploadStore'

function stream(text: string): ReadableStream<Uint8Array> {
  const bytes = new TextEncoder().encode(text)
  return new ReadableStream({
    start(controller) {
      for (const byte of bytes) controller.enqueue(new Uint8Array([byte]))
      controller.close()
    },
  })
}

const job = (status: UploadJob['status']): UploadJob => ({
  id: 'job-1', status, original_filename: 'test.zip', archive_storage_key: null,
  size_bytes: 42, report_json: {}, review_decisions: [], review_updated_at: null,
  created_at: '2026-10-04', finished_at: null,
})

afterEach(() => { vi.restoreAllMocks(); vi.useRealTimers() })

describe('import status SSE', () => {
  it('decodes split UTF-8 and CRLF and ignores heartbeats', async () => {
    const frames = []
    for await (const event of readEvents(stream(': heartbeat\r\n\r\nid: 3\r\nevent: status\r\ndata: Готово\r\n\r\n'))) {
      frames.push(event)
    }
    expect(frames).toEqual([{ id: '3', event: 'status', data: 'Готово' }])
  })

  it('refreshes report on status changes and stops at review', async () => {
    const get = vi.spyOn(api, 'get')
      .mockResolvedValueOnce({ data: job('queued') })
      .mockResolvedValueOnce({ data: stream('id: 3\nevent: status\ndata: {}\n\n') })
      .mockResolvedValueOnce({ data: job('needs_review') })
    const snapshot = vi.fn()
    const unavailable = vi.fn()
    await watchImport('job-1', new AbortController().signal, snapshot, unavailable)
    expect(snapshot.mock.calls.map(([job]) => job.status)).toEqual(['queued', 'needs_review'])
    expect(get.mock.calls[1][1]).toMatchObject({ adapter: 'fetch', responseType: 'stream' })
    expect(unavailable).not.toHaveBeenCalled()
  })

  it('reconnects with the last reconciled event id and aborts on unmount', async () => {
    vi.useFakeTimers()
    const controller = new AbortController()
    const get = vi.spyOn(api, 'get')
      .mockResolvedValueOnce({ data: job('queued') })
      .mockResolvedValueOnce({ data: stream('id: 2\nevent: status\ndata: {}\n\n') })
      .mockResolvedValueOnce({ data: job('running') })
      .mockResolvedValueOnce({ data: job('running') })
      .mockImplementationOnce(async () => { controller.abort(); return { data: stream('') } })
    const watching = watchImport('job-1', controller.signal, vi.fn(), vi.fn())
    await vi.advanceTimersByTimeAsync(1000)
    await watching
    expect(get.mock.calls[4][1]?.headers).toMatchObject({ 'Last-Event-ID': '2' })
    expect(vi.getTimerCount()).toBe(0)
  })

  it('clears inaccessible state without endlessly retrying', async () => {
    const error = new AxiosError('forbidden')
    Object.assign(error, { response: { status: 404 } })
    vi.spyOn(api, 'get').mockRejectedValue(error)
    const unavailable = vi.fn()
    await watchImport('job-1', new AbortController().signal, vi.fn(), unavailable)
    expect(unavailable).toHaveBeenCalledOnce()
  })

  it('falls back to an authenticated snapshot after SSE fails', async () => {
    vi.useFakeTimers()
    vi.spyOn(api, 'get')
      .mockResolvedValueOnce({ data: job('queued') })
      .mockRejectedValueOnce(new Error('proxy disconnected'))
      .mockResolvedValueOnce({ data: job('needs_review') })
    const snapshot = vi.fn()
    const watching = watchImport('job-1', new AbortController().signal, snapshot, vi.fn())
    await vi.advanceTimersByTimeAsync(1000)
    await watching
    expect(snapshot).toHaveBeenLastCalledWith(job('needs_review'))
  })
})
