import { afterEach, expect, it, vi } from 'vitest'
import { AxiosError } from 'axios'
import api from './api'
import { watchChanges } from './caseUpdates'

function stream(text: string): ReadableStream<Uint8Array> {
  return new ReadableStream({ start(c) { c.enqueue(new TextEncoder().encode(text)); c.close() } })
}
afterEach(() => { vi.restoreAllMocks(); vi.useRealTimers() })

it('reconciles protected state on reconnect and resumes after a successful refresh', async () => {
  vi.useFakeTimers()
  const controller = new AbortController()
  const refresh = vi.fn().mockResolvedValue(undefined)
  const get = vi.spyOn(api, 'get')
    .mockResolvedValueOnce({ data: stream('id: 7\nevent: changed\ndata: {"id":"case","version":3}\n\n') })
    .mockImplementationOnce(async () => { controller.abort(); return { data: stream('') } })
  const watching = watchChanges('/cases/case/events', controller.signal, refresh, vi.fn())
  await vi.advanceTimersByTimeAsync(1000)
  await watching
  expect(refresh).toHaveBeenCalledTimes(3)
  expect(get.mock.calls[1][1]?.headers).toMatchObject({ 'Last-Event-ID': '7' })
  expect(get.mock.calls[0][1]).toMatchObject({ adapter: 'fetch', responseType: 'stream' })
  expect(vi.getTimerCount()).toBe(0)
})

it('removes inaccessible clinical state and stops streaming after revocation', async () => {
  vi.spyOn(api, 'get').mockResolvedValue({ data: stream('event: access-revoked\ndata: {}\n\n') })
  const unavailable = vi.fn().mockResolvedValue(undefined)
  await watchChanges('/cases/case/events', new AbortController().signal, vi.fn(), unavailable)
  expect(unavailable).toHaveBeenCalledOnce()
})

it('reconnects after auth expiration so shared interceptors refresh Bearer tokens', async () => {
  vi.useFakeTimers()
  const controller = new AbortController()
  const refresh = vi.fn().mockResolvedValue(undefined)
  const get = vi.spyOn(api, 'get')
    .mockResolvedValueOnce({ data: stream('event: auth-expired\ndata: {}\n\n') })
    .mockImplementationOnce(async () => { controller.abort(); return { data: stream('') } })
  const watching = watchChanges('/notifications/events', controller.signal, refresh, vi.fn())
  await vi.advanceTimersByTimeAsync(1000)
  await watching
  expect(refresh).toHaveBeenCalledTimes(2)
  expect(get).toHaveBeenCalledTimes(2)
})

it('stops on terminal authorization errors without retrying', async () => {
  const error = new AxiosError('unauthorized')
  Object.assign(error, { response: { status: 401 } })
  vi.spyOn(api, 'get').mockRejectedValue(error)
  const unavailable = vi.fn().mockResolvedValue(undefined)
  await watchChanges('/notifications/events', new AbortController().signal, vi.fn(), unavailable)
  expect(unavailable).toHaveBeenCalledOnce()
})
